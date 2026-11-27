from datetime import date
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from app.core.database import get_db
from app.core.permissions import UserRole, require_roles
from app.models.sales import Payment
from app.models.user import User
from app.schemas.sales import PaymentCreate, PaymentRead
from app.services.payment_service import get_receivables_ageing, record_payment

router = APIRouter(prefix="/api/payments", tags=["Payments & Receivables"])


def _to_payment_read(p: Payment) -> PaymentRead:
    return PaymentRead(
        id=p.id,
        payment_number=p.payment_number,
        customer_id=p.customer_id,
        customer_name=p.customer.name if p.customer else None,
        invoice_id=p.invoice_id,
        invoice_number=p.invoice.invoice_number if p.invoice else None,
        payment_date=p.payment_date,
        amount=p.amount,
        payment_method=p.payment_method,
        reference_number=p.reference_number,
        notes=p.notes,
        created_at=p.created_at,
    )


@router.get("", response_model=list[PaymentRead], summary="List recorded customer payments")
def list_payments(
    customer_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN, UserRole.ACCOUNTANT, UserRole.OWNER)),
):
    stmt = (
        select(Payment)
        .options(joinedload(Payment.customer), joinedload(Payment.invoice))
        .order_by(Payment.payment_date.desc(), Payment.id.desc())
    )
    if customer_id is not None:
        stmt = stmt.where(Payment.customer_id == customer_id)
    rows = db.execute(stmt).scalars().all()
    return [_to_payment_read(r) for r in rows]


@router.post("", response_model=PaymentRead, status_code=status.HTTP_201_CREATED, summary="Record customer payment against invoice (Admin)")
def create_payment_endpoint(
    payload: PaymentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    pay = record_payment(db, payload, current_user)
    return _to_payment_read(pay)


@router.get("/ageing", summary="Customer-wise receivables ageing (0-30, 31-60, 60+ days)")
def receivables_ageing(
    as_of_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN, UserRole.ACCOUNTANT, UserRole.OWNER)),
):
    return get_receivables_ageing(db, as_of_date=as_of_date)
