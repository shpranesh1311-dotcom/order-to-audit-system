from datetime import date, datetime, timezone
from decimal import Decimal
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload
from app.core.audit import log_audit
from app.models.inventory import StockReservation
from app.models.master import Product
from app.models.sales import CreditNote, Invoice, InvoiceItem, InvoiceSequence, Order, OrderItem, SalesReturn
from app.models.user import FactorySettings, User
from app.schemas.sales import CreditNoteCreate, SalesReturnCreate
from app.services.stock_service import (
    ensure_and_lock_balance,
    get_fefo_batches,
    get_ledger_balance,
    get_reserved_qty,
    record_stock_movement,
)
from app.utils.calculations import calc_gst_breakdown, get_financial_year, round_money, round_qty


def _next_sequence_number(db: Session, prefix: str, fy: str) -> str:
    seq_key = f"{prefix}:{fy}"
    seq = db.execute(
        select(InvoiceSequence).where(InvoiceSequence.seq_key == seq_key).with_for_update()
    ).scalar_one_or_none()
    if seq is None:
        seq = InvoiceSequence(seq_key=seq_key, last_number=0)
        db.add(seq)
        db.flush()
        seq = db.execute(
            select(InvoiceSequence).where(InvoiceSequence.seq_key == seq_key).with_for_update()
        ).scalar_one()
    seq.last_number += 1
    return f"{prefix}/{fy}/{seq.last_number:04d}"


def generate_invoice_for_order(
    db: Session,
    order_id: int,
    current_user: User,
    invoice_date: date | None = None,
) -> Invoice:
    order = db.execute(
        select(Order)
        .options(joinedload(Order.customer), joinedload(Order.items).joinedload(OrderItem.product))
        .where(Order.id == order_id)
        .with_for_update(of=Order)
    ).unique().scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    existing_inv = db.execute(select(Invoice).where(Invoice.order_id == order.id)).scalar_one_or_none()
    if existing_inv is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Invoice {existing_inv.invoice_number} already generated for this order",
        )
    if order.status != "approved":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Order must be approved before generating an invoice (current: '{order.status}')",
        )

    factory = db.execute(select(FactorySettings)).scalar_one_or_none()
    if not factory:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Factory settings not configured")

    inv_date = invoice_date or date.today()
    fy = get_financial_year(inv_date)
    invoice_number = _next_sequence_number(db, "INV", fy)
    customer = order.customer
    place_of_supply = customer.state

    total_taxable = Decimal("0.00")
    total_cgst = Decimal("0.00")
    total_sgst = Decimal("0.00")
    total_igst = Decimal("0.00")
    tax_type_overall = "CGST_SGST" if factory.state.strip().lower() == place_of_supply.strip().lower() else "IGST"

    invoice = Invoice(
        invoice_number=invoice_number,
        financial_year=fy,
        order_id=order.id,
        customer_id=customer.id,
        invoice_date=inv_date,
        seller_name=factory.factory_name,
        seller_gstin=factory.gstin,
        seller_address=factory.address,
        seller_state=factory.state,
        buyer_name=customer.name,
        buyer_gstin=customer.gstin,
        buyer_address=customer.address,
        buyer_state=customer.state,
        place_of_supply=place_of_supply,
        tax_type=tax_type_overall,
        taxable_value=Decimal("0.00"),
        cgst_amount=Decimal("0.00"),
        sgst_amount=Decimal("0.00"),
        igst_amount=Decimal("0.00"),
        total_tax=Decimal("0.00"),
        grand_total=Decimal("0.00"),
        status="posted",
        dispatch_status="pending",
        created_by=current_user.id,
    )
    db.add(invoice)
    db.flush()

    for item in order.items:
        line_taxable = round_money(item.quantity * item.unit_price)
        gst = calc_gst_breakdown(line_taxable, item.gst_rate, factory.state, place_of_supply)

        total_taxable = round_money(total_taxable + line_taxable)
        total_cgst = round_money(total_cgst + Decimal(gst["cgst_amount"]))
        total_sgst = round_money(total_sgst + Decimal(gst["sgst_amount"]))
        total_igst = round_money(total_igst + Decimal(gst["igst_amount"]))

        db.add(
            InvoiceItem(
                invoice_id=invoice.id,
                product_id=item.product_id,
                product_name=item.product.name,
                hsn_code=item.product.hsn_code,
                quantity=item.quantity,
                unit_price=item.unit_price,
                taxable_value=line_taxable,
                gst_rate=item.gst_rate,
                cgst_rate=Decimal(gst["cgst_rate"]),
                cgst_amount=Decimal(gst["cgst_amount"]),
                sgst_rate=Decimal(gst["sgst_rate"]),
                sgst_amount=Decimal(gst["sgst_amount"]),
                igst_rate=Decimal(gst["igst_rate"]),
                igst_amount=Decimal(gst["igst_amount"]),
                total_amount=Decimal(gst["grand_total"]),
            )
        )

    total_tax = round_money(total_cgst + total_sgst + total_igst)
    invoice.taxable_value = total_taxable
    invoice.cgst_amount = total_cgst
    invoice.sgst_amount = total_sgst
    invoice.igst_amount = total_igst
    invoice.total_tax = total_tax
    invoice.grand_total = round_money(total_taxable + total_tax)

    now = datetime.now(timezone.utc)
    order.status = "invoiced"
    order.invoiced_at = now

    log_audit(
        db,
        user_id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        action="INVOICE_GENERATE",
        entity_type="invoice",
        entity_id=invoice.id,
        updated_values={
            "invoice_number": invoice.invoice_number,
            "order_id": order.id,
            "tax_type": invoice.tax_type,
            "taxable_value": invoice.taxable_value,
            "cgst": invoice.cgst_amount,
            "sgst": invoice.sgst_amount,
            "igst": invoice.igst_amount,
            "grand_total": invoice.grand_total,
        },
        remarks=f"Generated GST invoice {invoice.invoice_number}",
    )
    db.commit()
    return get_invoice(db, invoice.id)


def dispatch_invoice(db: Session, invoice_id: int, current_user: User) -> Invoice:
    invoice = db.execute(
        select(Invoice)
        .options(joinedload(Invoice.items), joinedload(Invoice.order))
        .where(Invoice.id == invoice_id)
        .with_for_update(of=Invoice)
    ).unique().scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    if invoice.dispatch_status == "dispatched":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Invoice {invoice.invoice_number} has already been dispatched",
        )
    if invoice.status == "cancelled":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot dispatch a cancelled invoice")

    order = db.execute(select(Order).where(Order.id == invoice.order_id).with_for_update()).scalar_one()

    for item in sorted(invoice.items, key=lambda x: x.product_id):
        product = db.get(Product, item.product_id)
        ensure_and_lock_balance(db, "finished_good", product_id=item.product_id)
        physical = get_ledger_balance(db, "finished_good", product_id=item.product_id)

        reservations = db.execute(
            select(StockReservation).where(
                StockReservation.order_id == order.id,
                StockReservation.product_id == item.product_id,
                StockReservation.status == "active",
            ).with_for_update()
        ).scalars().all()

        reserved_for_order = round_qty(sum((r.reserved_qty for r in reservations), Decimal("0.0000")))
        other_reserved = round_qty(get_reserved_qty(db, item.product_id) - reserved_for_order)
        available_for_this_dispatch = round_qty(physical - other_reserved)

        if available_for_this_dispatch < item.quantity:
            shortage = round_qty(item.quantity - available_for_this_dispatch)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Revalidation failed at dispatch for {item.product_name}: Available {available_for_this_dispatch}, Requested {item.quantity}, Shortage {shortage}",
            )

        # FEFO batch allocation
        remaining = round_qty(item.quantity)
        batches = get_fefo_batches(db, item.product_id)
        for batch in batches:
            if remaining <= Decimal("0"):
                break
            take = min(remaining, batch["available_qty"])
            if take > Decimal("0"):
                record_stock_movement(
                    db,
                    item_category="finished_good",
                    product_id=item.product_id,
                    transaction_type="dispatch",
                    direction="OUT",
                    quantity=take,
                    unit=product.unit if product else "packet",
                    rate=item.unit_price,
                    source_doc_type="invoice",
                    source_doc_id=invoice.id,
                    source_doc_ref=invoice.invoice_number,
                    user_id=current_user.id,
                    batch_number=batch["batch_number"],
                    expiry_date=batch["expiry_date"],
                    remarks=f"FEFO dispatch for {invoice.invoice_number} ({invoice.buyer_name})",
                )
                remaining = round_qty(remaining - take)

        if remaining > Decimal("0"):
            record_stock_movement(
                db,
                item_category="finished_good",
                product_id=item.product_id,
                transaction_type="dispatch",
                direction="OUT",
                quantity=remaining,
                unit=product.unit if product else "packet",
                rate=item.unit_price,
                source_doc_type="invoice",
                source_doc_id=invoice.id,
                source_doc_ref=invoice.invoice_number,
                user_id=current_user.id,
                remarks=f"Dispatch for {invoice.invoice_number} ({invoice.buyer_name})",
            )

        for res in reservations:
            res.status = "fulfilled"

    now = datetime.now(timezone.utc)
    invoice.dispatch_status = "dispatched"
    invoice.dispatched_at = now
    order.status = "dispatched"
    order.dispatched_at = now

    log_audit(
        db,
        user_id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        action="DISPATCH",
        entity_type="invoice",
        entity_id=invoice.id,
        previous_values={"dispatch_status": "pending"},
        updated_values={"dispatch_status": "dispatched", "order_status": "dispatched"},
        remarks=f"Dispatched {invoice.invoice_number} and deducted finished goods inventory",
    )
    db.commit()
    return get_invoice(db, invoice.id)


def create_credit_note(db: Session, payload: CreditNoteCreate, current_user: User) -> CreditNote:
    """
    Creates an accounting credit note for an invoice.
    NEVER modifies physical stock_ledger directly; physical returns are handled separately.
    """
    invoice = db.execute(
        select(Invoice).options(joinedload(Invoice.items)).where(Invoice.id == payload.invoice_id).with_for_update(of=Invoice)
    ).unique().scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

    cn_date = payload.credit_note_date or date.today()
    fy = get_financial_year(cn_date)
    cn_number = _next_sequence_number(db, "CN", fy)

    taxable = round_money(payload.taxable_value) if payload.taxable_value is not None else invoice.taxable_value
    if taxable > invoice.taxable_value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Credit note taxable value cannot exceed original invoice taxable value",
        )

    avg_gst_rate = (
        invoice.items[0].gst_rate if invoice.items else Decimal("5.00")
    )
    gst = calc_gst_breakdown(taxable, avg_gst_rate, invoice.seller_state, invoice.place_of_supply)

    cn = CreditNote(
        credit_note_number=cn_number,
        financial_year=fy,
        invoice_id=invoice.id,
        customer_id=invoice.customer_id,
        credit_note_date=cn_date,
        reason=payload.reason,
        taxable_value=taxable,
        cgst_amount=Decimal(gst["cgst_amount"]),
        sgst_amount=Decimal(gst["sgst_amount"]),
        igst_amount=Decimal(gst["igst_amount"]),
        total_amount=Decimal(gst["grand_total"]),
        status="posted",
        created_by=current_user.id,
    )
    db.add(cn)
    db.flush()

    if taxable == invoice.taxable_value:
        invoice.status = "credited"

    log_audit(
        db,
        user_id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        action="CREDIT_NOTE_CREATE",
        entity_type="credit_note",
        entity_id=cn.id,
        updated_values={
            "credit_note_number": cn.credit_note_number,
            "invoice_number": invoice.invoice_number,
            "total_amount": cn.total_amount,
            "physical_stock_altered": False,
        },
        remarks=payload.reason,
    )
    db.commit()
    return cn


def record_sales_return(db: Session, payload: SalesReturnCreate, current_user: User) -> SalesReturn:
    """
    Records physical goods returned by customer after inspection.
    Only `usable_qty` enters saleable finished-goods stock_ledger;
    `damaged_qty` is tracked separately without polluting saleable inventory.
    """
    invoice = db.get(Invoice, payload.invoice_id)
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    product = db.get(Product, payload.product_id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    returned = round_qty(payload.returned_qty)
    usable = round_qty(payload.usable_qty)
    damaged = round_qty(payload.damaged_qty)
    if round_qty(usable + damaged) != returned:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usable quantity + Damaged quantity must equal total Returned quantity",
        )

    ret_date = payload.return_date or date.today()
    next_seq = int(db.execute(select(func.coalesce(func.max(SalesReturn.id), 0))).scalar_one()) + 1
    ret_number = f"RET-{ret_date.strftime('%Y%m')}-{next_seq:04d}"

    inspection_status = "usable" if damaged == Decimal("0") else ("damaged" if usable == Decimal("0") else "partial_usable")
    sales_ret = SalesReturn(
        return_number=ret_number,
        credit_note_id=payload.credit_note_id,
        invoice_id=invoice.id,
        customer_id=invoice.customer_id,
        product_id=product.id,
        return_date=ret_date,
        returned_qty=returned,
        usable_qty=usable,
        damaged_qty=damaged,
        inspection_status=inspection_status,
        stock_restored=usable > Decimal("0"),
        remarks=payload.remarks,
        created_by=current_user.id,
    )
    db.add(sales_ret)
    db.flush()

    if usable > Decimal("0"):
        record_stock_movement(
            db,
            item_category="finished_good",
            product_id=product.id,
            transaction_type="sales_return",
            direction="IN",
            quantity=usable,
            unit=product.unit,
            rate=product.selling_price,
            source_doc_type="sales_return",
            source_doc_id=sales_ret.id,
            source_doc_ref=sales_ret.return_number,
            user_id=current_user.id,
            remarks=f"Inspected usable return from {invoice.invoice_number} (damaged: {damaged})",
        )

    log_audit(
        db,
        user_id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        action="SALES_RETURN",
        entity_type="sales_return",
        entity_id=sales_ret.id,
        updated_values={
            "return_number": sales_ret.return_number,
            "usable_qty": usable,
            "damaged_qty": damaged,
            "stock_restored": sales_ret.stock_restored,
        },
        remarks=payload.remarks,
    )
    db.commit()
    return sales_ret


def get_invoice(db: Session, invoice_id: int) -> Invoice:
    stmt = (
        select(Invoice)
        .options(joinedload(Invoice.items), joinedload(Invoice.payments))
        .where(Invoice.id == invoice_id)
    )
    inv = db.execute(stmt).unique().scalar_one_or_none()
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    return inv
