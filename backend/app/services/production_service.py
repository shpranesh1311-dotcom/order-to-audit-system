from datetime import date, timedelta
from decimal import Decimal
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload
from app.core.audit import log_audit
from app.models.bom import Bom, BomItem
from app.models.master import Material, Product
from app.models.production import ProductionConsumption, ProductionRun
from app.models.user import FactorySettings, User
from app.schemas.purchase_production import ProductionOverheadUpdate, ProductionRunCreate
from app.services.stock_service import record_stock_movement
from app.utils.calculations import calc_variance, round_money, round_qty, to_decimal
from app.utils.unit_conversion import UnitConversionError, convert_quantity


def create_production_run(db: Session, payload: ProductionRunCreate, current_user: User) -> ProductionRun:
    product = db.get(Product, payload.product_id)
    if not product or not product.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active product not found")

    bom = db.execute(
        select(Bom)
        .options(joinedload(Bom.items).joinedload(BomItem.material))
        .where(Bom.id == payload.bom_id, Bom.product_id == payload.product_id)
    ).unique().scalar_one_or_none()
    if not bom:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="BOM for selected product not found")

    factory = db.execute(select(FactorySettings)).scalar_one_or_none()
    tolerance_pct = factory.default_variance_tolerance_pct if factory else Decimal("3.00")

    run_date = payload.run_date or date.today()
    batches = to_decimal(payload.batches)
    expected_output = round_qty(bom.expected_output_qty * batches)
    actual_good = round_qty(payload.actual_good_packets)
    damaged_pouches = round_qty(payload.damaged_pouches)
    wastage_qty = round_qty(payload.wastage_qty)
    actual_cartons = round_qty(payload.actual_cartons_used)

    yield_var_qty, yield_var_pct, yield_flagged = calc_variance(expected_output, actual_good, tolerance_pct)

    next_seq = int(db.execute(select(func.coalesce(func.max(ProductionRun.id), 0))).scalar_one()) + 1
    run_number = f"PRD-{run_date.strftime('%Y%m')}-{next_seq:04d}"
    batch_number = payload.batch_number or f"{product.code}-{run_date.strftime('%y%m%d')}-{next_seq:03d}"
    expiry_date = payload.expiry_date or (run_date + timedelta(days=90))

    raw_input_map = {item.material_id: item for item in payload.raw_consumptions}

    run = ProductionRun(
        run_number=run_number,
        product_id=product.id,
        bom_id=bom.id,
        bom_version=bom.version,
        run_date=run_date,
        batches=batches,
        expected_output=expected_output,
        actual_good_packets=actual_good,
        damaged_pouches=damaged_pouches,
        wastage_qty=wastage_qty,
        actual_cartons_used=actual_cartons,
        yield_variance_qty=yield_var_qty,
        yield_variance_pct=yield_var_pct,
        yield_flagged=yield_flagged,
        tolerance_pct=tolerance_pct,
        labour_cost=round_money(payload.labour_cost),
        gas_cost=round_money(payload.gas_cost),
        power_cost=round_money(payload.power_cost),
        other_overhead_cost=round_money(payload.other_overhead_cost),
        batch_number=batch_number,
        expiry_date=expiry_date,
        status="completed",
        remarks=payload.remarks,
        created_by=current_user.id,
    )
    db.add(run)
    db.flush()

    raw_material_cost = Decimal("0.00")
    packaging_cost = Decimal("0.00")

    for bom_item in bom.items:
        mat = db.execute(
            select(Material).where(Material.id == bom_item.material_id).with_for_update()
        ).scalar_one()

        try:
            planned_per_batch = convert_quantity(
                bom_item.quantity,
                bom_item.unit,
                mat.base_unit,
                density_kg_per_litre=mat.density_kg_per_litre,
            )
        except UnitConversionError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        planned_qty = round_qty(planned_per_batch * batches)

        if mat.material_type == "packaging":
            name_lower = mat.name.lower()
            if "pouch" in name_lower or "primary" in mat.category.lower():
                actual_qty = round_qty(actual_good + damaged_pouches)
            elif "carton" in name_lower or "secondary" in mat.category.lower():
                actual_qty = actual_cartons
            elif mat.id in raw_input_map:
                actual_qty = round_qty(raw_input_map[mat.id].actual_qty)
            else:
                actual_qty = planned_qty
        else:
            if mat.id in raw_input_map:
                inp = raw_input_map[mat.id]
                inp_unit = inp.unit or mat.base_unit
                try:
                    actual_qty = convert_quantity(
                        inp.actual_qty,
                        inp_unit,
                        mat.base_unit,
                        density_kg_per_litre=mat.density_kg_per_litre,
                    )
                except UnitConversionError as exc:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
            else:
                actual_qty = planned_qty

        var_qty, var_pct, is_flagged = calc_variance(planned_qty, actual_qty, tolerance_pct)
        unit_cost = mat.current_avg_rate
        line_cost = round_money(actual_qty * unit_cost)

        if mat.material_type == "raw":
            raw_material_cost = round_money(raw_material_cost + line_cost)
            ledger_cat = "raw_material"
        else:
            packaging_cost = round_money(packaging_cost + line_cost)
            ledger_cat = "packaging_material"

        db.add(
            ProductionConsumption(
                production_run_id=run.id,
                material_id=mat.id,
                material_type=mat.material_type,
                planned_qty=planned_qty,
                actual_qty=actual_qty,
                unit=mat.base_unit,
                variance_qty=var_qty,
                variance_pct=var_pct,
                is_flagged=is_flagged,
                unit_cost=unit_cost,
                total_cost=line_cost,
            )
        )

        if actual_qty > Decimal("0"):
            record_stock_movement(
                db,
                item_category=ledger_cat,
                material_id=mat.id,
                transaction_type="production_issue",
                direction="OUT",
                quantity=actual_qty,
                unit=mat.base_unit,
                rate=unit_cost,
                source_doc_type="production_run",
                source_doc_id=run.id,
                source_doc_ref=run.run_number,
                user_id=current_user.id,
                remarks=f"Issued for {run.run_number} ({product.name})",
            )

    total_cost = round_money(
        raw_material_cost
        + packaging_cost
        + run.labour_cost
        + run.gas_cost
        + run.power_cost
        + run.other_overhead_cost
    )
    cost_per_packet = round_qty(total_cost / actual_good)

    run.raw_material_cost = raw_material_cost
    run.packaging_cost = packaging_cost
    run.total_cost = total_cost
    run.cost_per_packet = cost_per_packet

    record_stock_movement(
        db,
        item_category="finished_good",
        product_id=product.id,
        transaction_type="production_output",
        direction="IN",
        quantity=actual_good,
        unit=product.unit,
        rate=cost_per_packet,
        source_doc_type="production_run",
        source_doc_id=run.id,
        source_doc_ref=run.run_number,
        user_id=current_user.id,
        batch_number=batch_number,
        expiry_date=expiry_date,
        remarks=f"Good output from {run.run_number} (Damaged pouches: {damaged_pouches}, Wastage: {wastage_qty})",
    )

    log_audit(
        db,
        user_id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        action="CREATE",
        entity_type="production_run",
        entity_id=run.id,
        updated_values={
            "run_number": run.run_number,
            "product": product.name,
            "expected_output": expected_output,
            "actual_good_packets": actual_good,
            "yield_variance_pct": yield_var_pct,
            "total_cost": total_cost,
            "cost_per_packet": cost_per_packet,
        },
        remarks=payload.remarks,
    )
    db.commit()
    return get_production_run(db, run.id)


def update_production_overheads(
    db: Session,
    run_id: int,
    payload: ProductionOverheadUpdate,
    current_user: User,
) -> ProductionRun:
    run = db.execute(
        select(ProductionRun).where(ProductionRun.id == run_id).with_for_update()
    ).scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Production run not found")

    prev = {
        "labour_cost": run.labour_cost,
        "gas_cost": run.gas_cost,
        "power_cost": run.power_cost,
        "other_overhead_cost": run.other_overhead_cost,
        "total_cost": run.total_cost,
        "cost_per_packet": run.cost_per_packet,
    }

    if payload.labour_cost is not None:
        run.labour_cost = round_money(payload.labour_cost)
    if payload.gas_cost is not None:
        run.gas_cost = round_money(payload.gas_cost)
    if payload.power_cost is not None:
        run.power_cost = round_money(payload.power_cost)
    if payload.other_overhead_cost is not None:
        run.other_overhead_cost = round_money(payload.other_overhead_cost)
    if payload.remarks is not None:
        run.remarks = payload.remarks

    run.total_cost = round_money(
        run.raw_material_cost
        + run.packaging_cost
        + run.labour_cost
        + run.gas_cost
        + run.power_cost
        + run.other_overhead_cost
    )
    run.cost_per_packet = round_qty(run.total_cost / run.actual_good_packets)

    log_audit(
        db,
        user_id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        action="EDIT",
        entity_type="production_run",
        entity_id=run.id,
        previous_values=prev,
        updated_values={
            "labour_cost": run.labour_cost,
            "gas_cost": run.gas_cost,
            "power_cost": run.power_cost,
            "other_overhead_cost": run.other_overhead_cost,
            "total_cost": run.total_cost,
            "cost_per_packet": run.cost_per_packet,
        },
        remarks=payload.remarks or "Updated production run labour and overhead costs",
    )
    db.commit()
    return get_production_run(db, run.id)


def get_production_run(db: Session, run_id: int) -> ProductionRun:
    stmt = (
        select(ProductionRun)
        .options(
            joinedload(ProductionRun.product),
            joinedload(ProductionRun.consumptions).joinedload(ProductionConsumption.material),
        )
        .where(ProductionRun.id == run_id)
    )
    run = db.execute(stmt).unique().scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Production run not found")
    return run
