from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from app.core.database import get_db
from app.core.permissions import UserRole, require_roles
from app.models.sales import Order, OrderItem
from app.models.user import User
from app.schemas.sales import OrderCreate, OrderItemRead, OrderRead, OrderRejectRequest, OrderUpdate
from app.services.order_service import approve_order, create_order, get_order, reject_order, update_order
from app.services.stock_service import get_fg_availability
from app.utils.calculations import round_qty

router = APIRouter(prefix="/api/orders", tags=["Sales & Orders"])


def _to_order_read(db: Session, order: Order, include_stock: bool = True) -> OrderRead:
    items_out: list[OrderItemRead] = []
    for it in order.items:
        avail = None
        shortage = None
        if include_stock:
            fg = get_fg_availability(db, it.product_id)
            avail = fg["available_stock"]
            if order.status == "submitted":
                shortage = max(Decimal("0.0000"), round_qty(it.quantity - avail))
        items_out.append(
            OrderItemRead(
                id=it.id,
                product_id=it.product_id,
                product_name=it.product.name if it.product else None,
                quantity=it.quantity,
                unit_price=it.unit_price,
                gst_rate=it.gst_rate,
                line_subtotal=it.line_subtotal,
                available_stock=avail,
                shortage_qty=shortage,
            )
        )
    return OrderRead(
        id=order.id,
        order_number=order.order_number,
        customer_id=order.customer_id,
        customer_name=order.customer.name if order.customer else None,
        customer_state=order.customer.state if order.customer else None,
        salesman_id=order.salesman_id,
        salesman_name=order.salesman.full_name if order.salesman else None,
        order_date=order.order_date,
        status=order.status,
        subtotal=order.subtotal,
        tax_amount=order.tax_amount,
        total_amount=order.total_amount,
        notes=order.notes,
        rejection_reason=order.rejection_reason,
        idempotency_key=order.idempotency_key,
        approved_at=order.approved_at,
        invoiced_at=order.invoiced_at,
        dispatched_at=order.dispatched_at,
        created_at=order.created_at,
        items=items_out,
        invoice_id=order.invoice.id if order.invoice else None,
        invoice_number=order.invoice.invoice_number if order.invoice else None,
    )


@router.get("", response_model=list[OrderRead], summary="List orders (Salesman sees own orders)")
def list_orders(
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SALESMAN, UserRole.ADMIN, UserRole.ACCOUNTANT, UserRole.OWNER)
    ),
):
    stmt = (
        select(Order)
        .options(
            joinedload(Order.customer),
            joinedload(Order.salesman),
            joinedload(Order.invoice),
            joinedload(Order.items).joinedload(OrderItem.product),
        )
        .order_by(Order.created_at.desc(), Order.id.desc())
    )
    if current_user.role == UserRole.SALESMAN.value:
        stmt = stmt.where(Order.salesman_id == current_user.id)
    if status_filter:
        stmt = stmt.where(Order.status == status_filter)
    orders = db.execute(stmt).unique().scalars().all()
    return [_to_order_read(db, o) for o in orders]


@router.get("/{order_id}", response_model=OrderRead, summary="Get order details with stock availability")
def read_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SALESMAN, UserRole.ADMIN, UserRole.ACCOUNTANT, UserRole.OWNER)
    ),
):
    order = get_order(db, order_id)
    if current_user.role == UserRole.SALESMAN.value and order.salesman_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot view another salesman's order")
    return _to_order_read(db, order)


@router.post("", response_model=OrderRead, status_code=status.HTTP_201_CREATED, summary="Submit order (Salesman/Admin)")
def create_order_endpoint(
    payload: OrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.SALESMAN, UserRole.ADMIN)),
):
    order = create_order(db, payload, current_user)
    return _to_order_read(db, order)


@router.patch("/{order_id}", response_model=OrderRead, summary="Edit order quantities/prices before approval (Admin)")
def update_order_endpoint(
    order_id: int,
    payload: OrderUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    order = update_order(db, order_id, payload, current_user)
    return _to_order_read(db, order)


@router.post("/{order_id}/approve", response_model=OrderRead, summary="Verify stock & approve order (Admin)")
def approve_order_endpoint(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    order = approve_order(db, order_id, current_user)
    return _to_order_read(db, order)


@router.post("/{order_id}/reject", response_model=OrderRead, summary="Reject order & release reservation (Admin)")
def reject_order_endpoint(
    order_id: int,
    payload: OrderRejectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    order = reject_order(db, order_id, payload.reason, current_user)
    return _to_order_read(db, order)
