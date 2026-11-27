from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from app.core.database import get_db
from app.core.permissions import UserRole, require_roles
from app.models.production import ProductionConsumption, ProductionRun
from app.models.user import User
from app.schemas.purchase_production import (
    ProductionConsumptionRead,
    ProductionOverheadUpdate,
    ProductionRunCreate,
    ProductionRunRead,
)
from app.services.production_service import create_production_run, get_production_run, update_production_overheads

router = APIRouter(prefix="/api/production", tags=["Production & BOM Runs"])


def _to_run_read(run: ProductionRun) -> ProductionRunRead:
    return ProductionRunRead(
        id=run.id,
        run_number=run.run_number,
        product_id=run.product_id,
        product_name=run.product.name if run.product else None,
        bom_id=run.bom_id,
        bom_version=run.bom_version,
        run_date=run.run_date,
        batches=run.batches,
        expected_output=run.expected_output,
        actual_good_packets=run.actual_good_packets,
        damaged_pouches=run.damaged_pouches,
        wastage_qty=run.wastage_qty,
        actual_cartons_used=run.actual_cartons_used,
        yield_variance_qty=run.yield_variance_qty,
        yield_variance_pct=run.yield_variance_pct,
        yield_flagged=run.yield_flagged,
        tolerance_pct=run.tolerance_pct,
        labour_cost=run.labour_cost,
        gas_cost=run.gas_cost,
        power_cost=run.power_cost,
        other_overhead_cost=run.other_overhead_cost,
        raw_material_cost=run.raw_material_cost,
        packaging_cost=run.packaging_cost,
        total_cost=run.total_cost,
        cost_per_packet=run.cost_per_packet,
        batch_number=run.batch_number,
        expiry_date=run.expiry_date,
        status=run.status,
        remarks=run.remarks,
        created_at=run.created_at,
        consumptions=[
            ProductionConsumptionRead(
                id=c.id,
                material_id=c.material_id,
                material_name=c.material.name if c.material else None,
                material_type=c.material_type,
                planned_qty=c.planned_qty,
                actual_qty=c.actual_qty,
                unit=c.unit,
                variance_qty=c.variance_qty,
                variance_pct=c.variance_pct,
                is_flagged=c.is_flagged,
                unit_cost=c.unit_cost,
                total_cost=c.total_cost,
            )
            for c in run.consumptions
        ],
    )


@router.get("/runs", response_model=list[ProductionRunRead], summary="List production runs with variance")
def list_runs(
    db: Session = Depends(get_db),
    _: User = Depends(
        require_roles(UserRole.PRODUCTION, UserRole.ADMIN, UserRole.ACCOUNTANT, UserRole.OWNER)
    ),
):
    rows = (
        db.execute(
            select(ProductionRun)
            .options(
                joinedload(ProductionRun.product),
                joinedload(ProductionRun.consumptions).joinedload(ProductionConsumption.material),
            )
            .order_by(ProductionRun.run_date.desc(), ProductionRun.id.desc())
        )
        .unique()
        .scalars()
        .all()
    )
    return [_to_run_read(r) for r in rows]


@router.get("/runs/{run_id}", response_model=ProductionRunRead, summary="Get production run detail")
def read_run(
    run_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(
        require_roles(UserRole.PRODUCTION, UserRole.ADMIN, UserRole.ACCOUNTANT, UserRole.OWNER)
    ),
):
    return _to_run_read(get_production_run(db, run_id))


@router.post("/runs", response_model=ProductionRunRead, status_code=status.HTTP_201_CREATED, summary="Create atomic production run")
def create_run_endpoint(
    payload: ProductionRunCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.PRODUCTION, UserRole.ADMIN)),
):
    run = create_production_run(db, payload, current_user)
    return _to_run_read(run)


@router.patch("/runs/{run_id}/overheads", response_model=ProductionRunRead, summary="Update labour & overhead expenses and recalculate cost/packet")
def update_overheads_endpoint(
    run_id: int,
    payload: ProductionOverheadUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.PRODUCTION, UserRole.ADMIN)),
):
    run = update_production_overheads(db, run_id, payload, current_user)
    return _to_run_read(run)
