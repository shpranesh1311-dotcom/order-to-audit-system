from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.audit import log_audit
from app.core.database import get_db
from app.core.permissions import UserRole, require_roles
from app.models.master import Material
from app.models.user import User
from app.schemas.master import MaterialCreate, MaterialRead, MaterialUpdate
from app.services.stock_service import get_ledger_balance, record_stock_movement

router = APIRouter(prefix="/api/materials", tags=["Raw & Packaging Materials"])


@router.get("", response_model=list[MaterialRead], summary="List raw and packaging materials with live stock")
def list_materials(
    material_type: str | None = Query(default=None, pattern="^(raw|packaging)$"),
    db: Session = Depends(get_db),
    _: User = Depends(
        require_roles(UserRole.ADMIN, UserRole.PRODUCTION, UserRole.ACCOUNTANT, UserRole.OWNER)
    ),
):
    stmt = select(Material).order_by(Material.material_type, Material.id)
    if material_type:
        stmt = stmt.where(Material.material_type == material_type)
    materials = db.execute(stmt).scalars().all()
    out: list[MaterialRead] = []
    for m in materials:
        cat = "raw_material" if m.material_type == "raw" else "packaging_material"
        stock = get_ledger_balance(db, cat, material_id=m.id)
        item = MaterialRead.model_validate(m)
        item.current_stock = stock
        out.append(item)
    return out


@router.post("", response_model=MaterialRead, status_code=status.HTTP_201_CREATED, summary="Create material (Admin/Production)")
def create_material(
    payload: MaterialCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PRODUCTION)),
):
    existing = db.execute(select(Material).where(Material.code == payload.code)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Material code already exists")

    mat = Material(
        code=payload.code,
        name=payload.name,
        material_type=payload.material_type,
        category=payload.category,
        base_unit=payload.base_unit,
        opening_qty=payload.opening_qty,
        opening_rate=payload.opening_rate,
        current_avg_rate=payload.opening_rate,
        reorder_level=payload.reorder_level,
        density_kg_per_litre=payload.density_kg_per_litre,
        is_active=True,
    )
    db.add(mat)
    db.flush()

    cat = "raw_material" if mat.material_type == "raw" else "packaging_material"
    if mat.opening_qty > Decimal("0"):
        record_stock_movement(
            db,
            item_category=cat,
            material_id=mat.id,
            transaction_type="opening",
            direction="IN",
            quantity=mat.opening_qty,
            unit=mat.base_unit,
            rate=mat.opening_rate,
            source_doc_type="opening_stock",
            source_doc_id=mat.id,
            source_doc_ref=f"OPEN-{mat.code}",
            user_id=current_user.id,
            remarks="Opening material balance",
        )

    log_audit(
        db,
        user_id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        action="CREATE",
        entity_type="material",
        entity_id=mat.id,
        updated_values={"code": mat.code, "name": mat.name, "material_type": mat.material_type},
    )
    db.commit()
    db.refresh(mat)
    res = MaterialRead.model_validate(mat)
    res.current_stock = get_ledger_balance(db, cat, material_id=mat.id)
    return res


@router.patch("/{material_id}", response_model=MaterialRead, summary="Update material")
def update_material(
    material_id: int,
    payload: MaterialUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PRODUCTION)),
):
    mat = db.get(Material, material_id)
    if not mat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found")
    updates = payload.model_dump(exclude_unset=True)
    for field, val in updates.items():
        setattr(mat, field, val)
    log_audit(
        db,
        user_id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        action="EDIT",
        entity_type="material",
        entity_id=mat.id,
        updated_values=updates,
    )
    db.commit()
    db.refresh(mat)
    cat = "raw_material" if mat.material_type == "raw" else "packaging_material"
    res = MaterialRead.model_validate(mat)
    res.current_stock = get_ledger_balance(db, cat, material_id=mat.id)
    return res
