from decimal import Decimal
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from app.core.database import get_db
from app.core.permissions import UserRole, require_roles
from app.models.bom import Bom, BomItem
from app.models.user import User
from app.schemas.bom import BomCreate, BomItemRead, BomPlanResponse, BomRead
from app.services.bom_service import calculate_bom_plan, create_bom, get_bom

router = APIRouter(prefix="/api/bom", tags=["Bill of Materials"])


def _to_bom_read(bom: Bom) -> BomRead:
    return BomRead(
        id=bom.id,
        product_id=bom.product_id,
        product_name=bom.product.name if bom.product else None,
        version=bom.version,
        name=bom.name,
        expected_output_qty=bom.expected_output_qty,
        is_active=bom.is_active,
        notes=bom.notes,
        created_at=bom.created_at,
        items=[
            BomItemRead(
                id=it.id,
                material_id=it.material_id,
                material_name=it.material.name if it.material else None,
                material_type=it.material.material_type if it.material else None,
                quantity=it.quantity,
                unit=it.unit,
            )
            for it in bom.items
        ],
    )


@router.get("", response_model=list[BomRead], summary="List BOMs")
def list_boms(
    product_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(
        require_roles(UserRole.ADMIN, UserRole.PRODUCTION, UserRole.ACCOUNTANT, UserRole.OWNER)
    ),
):
    stmt = (
        select(Bom)
        .options(joinedload(Bom.product), joinedload(Bom.items).joinedload(BomItem.material))
        .order_by(Bom.product_id, Bom.version.desc())
    )
    if product_id is not None:
        stmt = stmt.where(Bom.product_id == product_id)
    boms = db.execute(stmt).unique().scalars().all()
    return [_to_bom_read(b) for b in boms]


@router.get("/{bom_id}", response_model=BomRead, summary="Get BOM details")
def read_bom(
    bom_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(
        require_roles(UserRole.ADMIN, UserRole.PRODUCTION, UserRole.ACCOUNTANT, UserRole.OWNER)
    ),
):
    return _to_bom_read(get_bom(db, bom_id))


@router.post("", response_model=BomRead, status_code=status.HTTP_201_CREATED, summary="Create new BOM version (Admin/Production)")
def create_bom_endpoint(
    payload: BomCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PRODUCTION)),
):
    return _to_bom_read(create_bom(db, payload, current_user))


@router.get("/{bom_id}/plan", response_model=BomPlanResponse, summary="Calculate planned consumption for batches")
def plan_bom(
    bom_id: int,
    batches: Decimal = Query(default=Decimal("1"), gt=0),
    db: Session = Depends(get_db),
    _: User = Depends(
        require_roles(UserRole.ADMIN, UserRole.PRODUCTION, UserRole.OWNER, UserRole.ACCOUNTANT)
    ),
):
    return calculate_bom_plan(db, bom_id, batches)
