from datetime import date, datetime, timezone
from decimal import Decimal
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload
from app.core.audit import log_audit
from app.models.inventory import StockReservation
from app.models.master import Customer, PriceList, Product
from app.models.sales import Order, OrderItem
from app.models.user import User
from app.schemas.sales import OrderCreate, OrderUpdate
from app.services.stock_service import ensure_and_lock_balance, get_fg_availability
from app.utils.calculations import round_money, round_qty, to_decimal


def resolve_product_price(db: Session, product: Product, customer_id: int, target_date: date) -> Decimal:
    cust_price = db.execute(
        select(PriceList)
        .where(
            PriceList.product_id == product.id,
            PriceList.customer_id == customer_id,
            PriceList.effective_date <= target_date,
        )
        .order_by(PriceList.effective_date.desc(), PriceList.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    if cust_price:
        return cust_price.price

    std_price = db.execute(
        select(PriceList)
        .where(
            PriceList.product_id == product.id,
            PriceList.customer_id.is_(None),
            PriceList.effective_date <= target_date,
        )
        .order_by(PriceList.effective_date.desc(), PriceList.id.desc())
        .limit(1)
    ).scalar_one_or_none()
    if std_price:
        return std_price.price

    return product.selling_price


def create_order(db: Session, payload: OrderCreate, current_user: User) -> Order:
    if payload.idempotency_key:
        existing = db.execute(
            select(Order).where(Order.idempotency_key == payload.idempotency_key)
        ).scalar_one_or_none()
        if existing is not None:
            return get_order(db, existing.id)

    customer = db.get(Customer, payload.customer_id)
    if not customer or not customer.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active customer not found")

    if (
        current_user.role == "salesman"
        and customer.assigned_salesman_id is not None
        and customer.assigned_salesman_id != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only submit orders for your assigned customers",
        )

    order_date = payload.order_date or date.today()
    next_seq = int(db.execute(select(func.coalesce(func.max(Order.id), 0))).scalar_one()) + 1
    order_number = f"ORD-{order_date.strftime('%Y%m')}-{next_seq:04d}"

    order = Order(
        order_number=order_number,
        customer_id=customer.id,
        salesman_id=current_user.id,
        order_date=order_date,
        status="submitted",
        notes=payload.notes,
        idempotency_key=payload.idempotency_key,
        offline_created_at=payload.offline_created_at,
    )
    db.add(order)
    db.flush()

    subtotal = Decimal("0.00")
    tax_amount = Decimal("0.00")

    for line in payload.items:
        product = db.get(Product, line.product_id)
        if not product or not product.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Active product #{line.product_id} not found",
            )
        qty = round_qty(line.quantity)
        unit_price = (
            round_money(line.unit_price)
            if (line.unit_price is not None and current_user.role == "admin")
            else resolve_product_price(db, product, customer.id, order_date)
        )
        line_sub = round_money(qty * unit_price)
        line_tax = round_money(line_sub * product.gst_rate / Decimal("100"))
        subtotal = round_money(subtotal + line_sub)
        tax_amount = round_money(tax_amount + line_tax)

        db.add(
            OrderItem(
                order_id=order.id,
                product_id=product.id,
                quantity=qty,
                unit_price=unit_price,
                gst_rate=product.gst_rate,
                line_subtotal=line_sub,
            )
        )

    order.subtotal = subtotal
    order.tax_amount = tax_amount
    order.total_amount = round_money(subtotal + tax_amount)

    log_audit(
        db,
        user_id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        action="CREATE",
        entity_type="order",
        entity_id=order.id,
        updated_values={
            "order_number": order.order_number,
            "customer_id": customer.id,
            "total_amount": order.total_amount,
        },
        remarks=payload.notes,
    )
    db.commit()
    return get_order(db, order.id)


def update_order(db: Session, order_id: int, payload: OrderUpdate, current_user: User) -> Order:
    order = db.execute(
        select(Order).options(joinedload(Order.items)).where(Order.id == order_id).with_for_update(of=Order)
    ).unique().scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if order.status != "submitted":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot edit order in '{order.status}' status",
        )

    prev = {"subtotal": order.subtotal, "total_amount": order.total_amount}
    order.items.clear()
    db.flush()

    subtotal = Decimal("0.00")
    tax_amount = Decimal("0.00")
    for line in payload.items:
        product = db.get(Product, line.product_id)
        if not product or not product.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Product #{line.product_id} not found")
        qty = round_qty(line.quantity)
        unit_price = (
            round_money(line.unit_price)
            if line.unit_price is not None
            else resolve_product_price(db, product, order.customer_id, order.order_date)
        )
        line_sub = round_money(qty * unit_price)
        line_tax = round_money(line_sub * product.gst_rate / Decimal("100"))
        subtotal = round_money(subtotal + line_sub)
        tax_amount = round_money(tax_amount + line_tax)
        order.items.append(
            OrderItem(
                order_id=order.id,
                product_id=product.id,
                quantity=qty,
                unit_price=unit_price,
                gst_rate=product.gst_rate,
                line_subtotal=line_sub,
            )
        )

    order.notes = payload.notes if payload.notes is not None else order.notes
    order.subtotal = subtotal
    order.tax_amount = tax_amount
    order.total_amount = round_money(subtotal + tax_amount)

    log_audit(
        db,
        user_id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        action="EDIT",
        entity_type="order",
        entity_id=order.id,
        previous_values=prev,
        updated_values={"subtotal": order.subtotal, "total_amount": order.total_amount},
        remarks="Admin verified and updated order items",
    )
    db.commit()
    return get_order(db, order.id)


def approve_order(db: Session, order_id: int, current_user: User) -> Order:
    order = db.execute(
        select(Order)
        .options(joinedload(Order.items).joinedload(OrderItem.product))
        .where(Order.id == order_id)
        .with_for_update(of=Order)
    ).unique().scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if order.status != "submitted":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Order must be in 'submitted' status to approve (current: '{order.status}')",
        )

    # Lock finished-goods stock rows in deterministic product_id order to prevent deadlocks
    shortages: list[dict] = []
    for item in sorted(order.items, key=lambda x: x.product_id):
        ensure_and_lock_balance(db, "finished_good", product_id=item.product_id)
        avail_info = get_fg_availability(db, item.product_id)
        avail = avail_info["available_stock"]
        if avail < item.quantity:
            shortage = round_qty(item.quantity - avail)
            shortages.append(
                {
                    "product_id": item.product_id,
                    "product_name": item.product.name,
                    "requested": str(item.quantity),
                    "available": str(avail),
                    "shortage": str(shortage),
                }
            )

    if shortages:
        first = shortages[0]
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": (
                    f"Insufficient finished goods stock for {first['product_name']}. "
                    f"Requested: {first['requested']} packets, Available: {first['available']} packets, "
                    f"Shortage: {first['shortage']} packets."
                ),
                "shortages": shortages,
            },
        )

    for item in order.items:
        db.add(
            StockReservation(
                order_id=order.id,
                order_item_id=item.id,
                product_id=item.product_id,
                reserved_qty=item.quantity,
                status="active",
            )
        )

    order.status = "approved"
    order.approved_by = current_user.id
    order.approved_at = datetime.now(timezone.utc)

    log_audit(
        db,
        user_id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        action="APPROVE",
        entity_type="order",
        entity_id=order.id,
        previous_values={"status": "submitted"},
        updated_values={"status": "approved"},
        remarks=f"Order {order.order_number} approved and stock reserved",
    )
    db.commit()
    return get_order(db, order.id)


def reject_order(db: Session, order_id: int, reason: str, current_user: User) -> Order:
    order = db.execute(
        select(Order).where(Order.id == order_id).with_for_update()
    ).scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if order.status in ("invoiced", "dispatched"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot reject an invoiced or dispatched order; issue a credit note instead",
        )

    prev_status = order.status
    if prev_status == "approved":
        reservations = db.execute(
            select(StockReservation).where(
                StockReservation.order_id == order.id,
                StockReservation.status == "active",
            )
        ).scalars().all()
        for res in reservations:
            res.status = "released"

    order.status = "rejected"
    order.rejection_reason = reason

    log_audit(
        db,
        user_id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        action="REJECT",
        entity_type="order",
        entity_id=order.id,
        previous_values={"status": prev_status},
        updated_values={"status": "rejected", "rejection_reason": reason},
        remarks=reason,
    )
    db.commit()
    return get_order(db, order.id)


def get_order(db: Session, order_id: int) -> Order:
    stmt = (
        select(Order)
        .options(
            joinedload(Order.customer),
            joinedload(Order.salesman),
            joinedload(Order.invoice),
            joinedload(Order.items).joinedload(OrderItem.product),
        )
        .where(Order.id == order_id)
    )
    order = db.execute(stmt).unique().scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order
