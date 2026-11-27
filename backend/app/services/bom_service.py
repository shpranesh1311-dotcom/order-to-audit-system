from decimal import Decimal
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload
from app.core.audit import log_audit
from app.models.bom import Bom, BomItem
from app.models.master import Material, Product
from app.models.user import User
from app.schemas.bom import BomCreate
from app.services.stock_service import get_ledger_balance
from app.utils.calculations import round_qty, to_decimal
from app.utils.unit_conversion import UnitConversionError, convert_quantity


def create_bom(db: Session, payload: BomCreate, current_user: User) -> Bom:
    product = db.get(Product, payload.product_id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    max_ver = db.execute(
        select(func.coalesce(func.max(Bom.version), 0)).where(Bom.product_id == payload.product_id)
    ).scalar_one()
    next_version = int(max_ver) + 1

    bom = Bom(
        product_id=payload.product_id,
        version=next_version,
        name=payload.name,
        expected_output_qty=round_qty(payload.expected_output_qty),
        is_active=True,
        notes=payload.notes,
    )
    db.add(bom)
    db.flush()

    for item in payload.items:
        mat = db.get(Material, item.material_id)
        if not mat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Material #{item.material_id} not found",
            )
        try:
            convert_quantity(
                item.quantity,
                item.unit,
                mat.base_unit,
                density_kg_per_litre=mat.density_kg_per_litre,
            )
        except UnitConversionError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        db.add(
            BomItem(
                bom_id=bom.id,
                material_id=mat.id,
                quantity=round_qty(item.quantity),
                unit=item.unit,
            )
        )

    log_audit(
        db,
        user_id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        action="CREATE",
        entity_type="bom",
        entity_id=bom.id,
        updated_values={"product_id": product.id, "version": next_version, "name": bom.name},
    )
    db.commit()
    return get_bom(db, bom.id)


def get_bom(db: Session, bom_id: int) -> Bom:
    stmt = (
        select(Bom)
        .options(joinedload(Bom.product), joinedload(Bom.items).joinedload(BomItem.material))
        .where(Bom.id == bom_id)
    )
    bom = db.execute(stmt).unique().scalar_one_or_none()
    if not bom:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="BOM not found")
    return bom


def calculate_bom_plan(db: Session, bom_id: int, batches: Decimal) -> dict:
    bom = get_bom(db, bom_id)
    batch_dec = to_decimal(batches)
    if batch_dec <= Decimal("0"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Batches must be greater than 0")

    expected_output = round_qty(bom.expected_output_qty * batch_dec)
    planned_lines: list[dict] = []
    for item in bom.items:
        mat = item.material
        base_per_batch = convert_quantity(
            item.quantity,
            item.unit,
            mat.base_unit,
            density_kg_per_litre=mat.density_kg_per_litre,
        )
        planned_qty = round_qty(base_per_batch * batch_dec)
        cat = "raw_material" if mat.material_type == "raw" else "packaging_material"
        avail = get_ledger_balance(db, cat, material_id=mat.id)
        planned_lines.append(
            {
                "material_id": mat.id,
                "material_name": mat.name,
                "material_type": mat.material_type,
                "planned_qty": planned_qty,
                "unit": mat.base_unit,
                "available_stock": avail,
                "avg_rate": mat.current_avg_rate,
            }
        )

    return {
        "bom_id": bom.id,
        "product_id": bom.product_id,
        "product_name": bom.product.name,
        "version": bom.version,
        "batches": batch_dec,
        "expected_output_qty": expected_output,
        "items": planned_lines,
    }
