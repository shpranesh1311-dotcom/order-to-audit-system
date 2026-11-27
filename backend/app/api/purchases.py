from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from app.core.database import get_db
from app.core.permissions import UserRole, require_roles
from app.models.purchase import Purchase
from app.models.user import User
from app.schemas.purchase_production import PurchaseCreate, PurchaseRead
from app.services.purchase_service import record_purchase

router = APIRouter(prefix="/api/purchases", tags=["Purchases & Procurement"])


def _to_purchase_read(p: Purchase) -> PurchaseRead:
    return PurchaseRead(
        id=p.id,
        purchase_number=p.purchase_number,
        supplier_id=p.supplier_id,
        supplier_name=p.supplier.name if p.supplier else None,
        material_id=p.material_id,
        material_name=p.material.name if p.material else None,
        material_type=p.material.material_type if p.material else None,
        invoice_number=p.invoice_number,
        purchase_date=p.purchase_date,
        quantity=p.quantity,
        unit=p.unit,
        base_quantity=p.base_quantity,
        unit_rate=p.unit_rate,
        total_amount=p.total_amount,
        batch_number=p.batch_number,
        expiry_date=p.expiry_date,
        remarks=p.remarks,
        created_at=p.created_at,
    )


@router.get("", response_model=list[PurchaseRead], summary="List purchase records")
def list_purchases(
    db: Session = Depends(get_db),
    _: User = Depends(
        require_roles(UserRole.ADMIN, UserRole.PRODUCTION, UserRole.ACCOUNTANT, UserRole.OWNER)
    ),
):
    rows = (
        db.execute(
            select(Purchase)
            .options(joinedload(Purchase.supplier), joinedload(Purchase.material))
            .order_by(Purchase.purchase_date.desc(), Purchase.id.desc())
        )
        .scalars()
        .all()
    )
    return [_to_purchase_read(r) for r in rows]


@router.post("", response_model=PurchaseRead, status_code=status.HTTP_201_CREATED, summary="Record material purchase & update weighted-avg rate")
def create_purchase_endpoint(
    payload: PurchaseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PRODUCTION)),
):
    p = record_purchase(db, payload, current_user)
    return _to_purchase_read(p)
