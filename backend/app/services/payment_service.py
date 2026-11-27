from datetime import date
from decimal import Decimal
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload
from app.core.audit import log_audit
from app.models.master import Customer
from app.models.sales import CreditNote, Invoice, Payment
from app.models.user import User
from app.schemas.sales import PaymentCreate
from app.utils.calculations import round_money


def get_invoice_outstanding(db: Session, invoice: Invoice) -> tuple[Decimal, Decimal]:
    paid = db.execute(
        select(func.coalesce(func.sum(Payment.amount), Decimal("0.00"))).where(
            Payment.invoice_id == invoice.id
        )
    ).scalar_one()
    credited = db.execute(
        select(func.coalesce(func.sum(CreditNote.total_amount), Decimal("0.00"))).where(
            CreditNote.invoice_id == invoice.id
        )
    ).scalar_one()
    paid_dec = round_money(paid)
    credited_dec = round_money(credited)
    outstanding = round_money(invoice.grand_total - paid_dec - credited_dec)
    return paid_dec, max(Decimal("0.00"), outstanding)


def record_payment(db: Session, payload: PaymentCreate, current_user: User) -> Payment:
    if payload.idempotency_key:
        existing = db.execute(
            select(Payment).where(Payment.idempotency_key == payload.idempotency_key)
        ).scalar_one_or_none()
        if existing is not None:
            return get_payment(db, existing.id)

    invoice = db.execute(
        select(Invoice).where(Invoice.id == payload.invoice_id).with_for_update()
    ).scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    if invoice.customer_id != payload.customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Selected invoice does not belong to the specified customer",
        )
    if invoice.status == "cancelled":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot allocate payment to a cancelled invoice")

    paid, outstanding = get_invoice_outstanding(db, invoice)
    amount = round_money(payload.amount)
    if amount <= Decimal("0.00"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payment amount must be greater than 0")
    if amount > outstanding:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payment amount (₹{amount}) exceeds outstanding balance (₹{outstanding}) on invoice {invoice.invoice_number}",
        )

    pay_date = payload.payment_date or date.today()
    next_seq = int(db.execute(select(func.coalesce(func.max(Payment.id), 0))).scalar_one()) + 1
    pay_number = f"PAY-{pay_date.strftime('%Y%m')}-{next_seq:04d}"

    payment = Payment(
        payment_number=pay_number,
        customer_id=payload.customer_id,
        invoice_id=invoice.id,
        payment_date=pay_date,
        amount=amount,
        payment_method=payload.payment_method,
        reference_number=payload.reference_number,
        notes=payload.notes,
        idempotency_key=payload.idempotency_key,
        created_by=current_user.id,
    )
    db.add(payment)
    db.flush()

    new_outstanding = round_money(outstanding - amount)
    log_audit(
        db,
        user_id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        action="PAYMENT_RECORD",
        entity_type="payment",
        entity_id=payment.id,
        previous_values={"paid": paid, "outstanding": outstanding},
        updated_values={
            "payment_number": pay_number,
            "invoice_number": invoice.invoice_number,
            "amount": amount,
            "new_outstanding": new_outstanding,
        },
        remarks=payload.notes,
    )
    db.commit()
    return get_payment(db, payment.id)


def get_payment(db: Session, payment_id: int) -> Payment:
    stmt = (
        select(Payment)
        .options(joinedload(Payment.customer), joinedload(Payment.invoice))
        .where(Payment.id == payment_id)
    )
    pay = db.execute(stmt).scalar_one_or_none()
    if not pay:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    return pay


def get_receivables_ageing(db: Session, as_of_date: date | None = None) -> dict:
    ref_date = as_of_date or date.today()
    invoices = (
        db.execute(
            select(Invoice)
            .options(joinedload(Invoice.customer))
            .where(Invoice.status != "cancelled")
            .order_by(Invoice.invoice_date.asc())
        )
        .scalars()
        .all()
    )

    by_customer: dict[int, dict] = {}
    invoice_rows: list[dict] = []
    totals = {
        "bucket_0_30": Decimal("0.00"),
        "bucket_31_60": Decimal("0.00"),
        "bucket_60_plus": Decimal("0.00"),
        "total_outstanding": Decimal("0.00"),
    }

    for inv in invoices:
        paid, outstanding = get_invoice_outstanding(db, inv)
        if outstanding <= Decimal("0.00"):
            continue
        days_old = max(0, (ref_date - inv.invoice_date).days)
        if days_old <= 30:
            bucket = "0-30 days"
            b_key = "bucket_0_30"
        elif days_old <= 60:
            bucket = "31-60 days"
            b_key = "bucket_31_60"
        else:
            bucket = "Above 60 days"
            b_key = "bucket_60_plus"

        totals[b_key] = round_money(totals[b_key] + outstanding)
        totals["total_outstanding"] = round_money(totals["total_outstanding"] + outstanding)

        invoice_rows.append(
            {
                "invoice_id": inv.id,
                "invoice_number": inv.invoice_number,
                "invoice_date": inv.invoice_date.isoformat(),
                "customer_id": inv.customer_id,
                "customer_name": inv.customer.name,
                "grand_total": inv.grand_total,
                "paid_amount": paid,
                "outstanding_amount": outstanding,
                "days_outstanding": days_old,
                "ageing_bucket": bucket,
            }
        )

        cust = by_customer.setdefault(
            inv.customer_id,
            {
                "customer_id": inv.customer_id,
                "customer_name": inv.customer.name,
                "customer_type": inv.customer.customer_type,
                "state": inv.customer.state,
                "bucket_0_30": Decimal("0.00"),
                "bucket_31_60": Decimal("0.00"),
                "bucket_60_plus": Decimal("0.00"),
                "total_outstanding": Decimal("0.00"),
            },
        )
        cust[b_key] = round_money(cust[b_key] + outstanding)
        cust["total_outstanding"] = round_money(cust["total_outstanding"] + outstanding)

    return {
        "as_of_date": ref_date.isoformat(),
        "summary": totals,
        "customers": list(by_customer.values()),
        "invoices": invoice_rows,
    }
