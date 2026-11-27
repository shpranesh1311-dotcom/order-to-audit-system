from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from app.core.audit import log_audit
from app.core.database import get_db
from app.core.permissions import UserRole, require_roles
from app.models.master import Supplier
from app.models.purchase import Purchase
from app.models.user import User
from app.schemas.master import SupplierCreate, SupplierRead, SupplierUpdate
from app.schemas.purchase_production import PurchaseRead

router = APIRouter(prefix="/api/suppliers", tags=["Suppliers"])


@router.get("", response_model=list[SupplierRead], summary="List suppliers")
def list_suppliers(
    db: Session = Depends(get_db),
    _: User = Depends(
        require_roles(UserRole.ADMIN, UserRole.PRODUCTION, UserRole.ACCOUNTANT, UserRole.OWNER)
    ),
):
    return db.execute(select(Supplier).order_by(Supplier.name)).scalars().all()


@router.post("", response_model=SupplierRead, status_code=status.HTTP_201_CREATED, summary="Create supplier")
def create_supplier(
    payload: SupplierCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PRODUCTION)),
):
    sup = Supplier(**payload.model_dump(), is_active=True)
    db.add(sup)
    db.flush()
    log_audit(
        db,
        user_id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        action="CREATE",
        entity_type="supplier",
        entity_id=sup.id,
        updated_values={"name": sup.name, "state": sup.state},
    )
    db.commit()
    db.refresh(sup)
    return sup


@router.patch("/{supplier_id}", response_model=SupplierRead, summary="Update supplier")
def update_supplier(
    supplier_id: int,
    payload: SupplierUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PRODUCTION)),
):
    sup = db.get(Supplier, supplier_id)
    if not sup:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
    updates = payload.model_dump(exclude_unset=True)
    prev = {k: getattr(sup, k) for k in updates}
    for field, val in updates.items():
        setattr(sup, field, val)
    log_audit(
        db,
        user_id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        action="EDIT",
        entity_type="supplier",
        entity_id=sup.id,
        previous_values=prev,
        updated_values=updates,
    )
    db.commit()
    db.refresh(sup)
    return sup


@router.get("/{supplier_id}/purchases", response_model=list[PurchaseRead], summary="Supplier purchase history")
def supplier_purchases(
    supplier_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(
        require_roles(UserRole.ADMIN, UserRole.PRODUCTION, UserRole.ACCOUNTANT, UserRole.OWNER)
    ),
):
    rows = (
        db.execute(
            select(Purchase)
            .options(joinedload(Purchase.supplier), joinedload(Purchase.material))
            .where(Purchase.supplier_id == supplier_id)
            .order_by(Purchase.purchase_date.desc(), Purchase.id.desc())
        )
        .scalars()
        .all()
    )
    return [
        PurchaseRead(
            **{
                **PurchaseRead.model_validate(r).model_dump(),
                "supplier_name": r.supplier.name,
                "material_name": r.material.name,
                "material_type": r.material.material_type,
            }
        )
        for r in rows
    ]
