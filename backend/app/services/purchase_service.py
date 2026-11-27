from decimal import Decimal
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload
from app.core.audit import log_audit
from app.models.master import Material, Supplier
from app.models.purchase import Purchase
from app.models.user import User
from app.schemas.purchase_production import PurchaseCreate
from app.services.stock_service import get_ledger_balance, record_stock_movement
from app.utils.calculations import calc_weighted_avg_rate, round_money, round_qty, round_rate, to_decimal
from app.utils.unit_conversion import UnitConversionError, convert_quantity


def record_purchase(db: Session, payload: PurchaseCreate, current_user: User) -> Purchase:
    if payload.idempotency_key:
        existing_idem = db.execute(
            select(Purchase).where(Purchase.idempotency_key == payload.idempotency_key)
        ).scalar_one_or_none()
        if existing_idem is not None:
            return get_purchase(db, existing_idem.id)

    supplier = db.get(Supplier, payload.supplier_id)
    if not supplier or not supplier.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active supplier not found")

    material = db.execute(
        select(Material).where(Material.id == payload.material_id).with_for_update()
    ).scalar_one_or_none()
    if not material or not material.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active material not found")

    dup = db.execute(
        select(Purchase).where(
            Purchase.supplier_id == payload.supplier_id,
            Purchase.invoice_number == payload.invoice_number,
            Purchase.material_id == payload.material_id,
        )
    ).scalar_one_or_none()
    if dup is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Duplicate purchase: invoice '{payload.invoice_number}' for supplier '{supplier.name}' and material '{material.name}' already posted",
        )

    try:
        base_qty = convert_quantity(
            payload.quantity,
            payload.unit,
            material.base_unit,
            density_kg_per_litre=material.density_kg_per_litre,
        )
    except UnitConversionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    qty = round_qty(payload.quantity)
    unit_rate = to_decimal(payload.unit_rate)
    total_amount = round_money(qty * unit_rate)
    base_rate = round_rate(total_amount / base_qty)

    item_category = "raw_material" if material.material_type == "raw" else "packaging_material"
    old_stock = get_ledger_balance(db, item_category, material_id=material.id)
    old_avg_rate = material.current_avg_rate
    new_avg_rate = calc_weighted_avg_rate(old_stock, old_avg_rate, base_qty, base_rate)

    next_seq = int(db.execute(select(func.coalesce(func.max(Purchase.id), 0))).scalar_one()) + 1
    purchase_number = f"PUR-{payload.purchase_date.strftime('%Y%m')}-{next_seq:04d}"

    purchase = Purchase(
        purchase_number=purchase_number,
        supplier_id=supplier.id,
        material_id=material.id,
        invoice_number=payload.invoice_number.strip(),
        purchase_date=payload.purchase_date,
        quantity=qty,
        unit=payload.unit,
        base_quantity=base_qty,
        unit_rate=unit_rate,
        total_amount=total_amount,
        batch_number=payload.batch_number,
        expiry_date=payload.expiry_date,
        remarks=payload.remarks,
        idempotency_key=payload.idempotency_key,
        created_by=current_user.id,
    )
    db.add(purchase)
    db.flush()

    material.current_avg_rate = new_avg_rate

    record_stock_movement(
        db,
        item_category=item_category,
        material_id=material.id,
        transaction_type="purchase",
        direction="IN",
        quantity=base_qty,
        unit=material.base_unit,
        rate=base_rate,
        source_doc_type="purchase",
        source_doc_id=purchase.id,
        source_doc_ref=purchase.purchase_number,
        user_id=current_user.id,
        batch_number=payload.batch_number,
        expiry_date=payload.expiry_date,
        remarks=f"Purchase from {supplier.name} (Inv: {purchase.invoice_number})",
    )

    log_audit(
        db,
        user_id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        action="CREATE",
        entity_type="purchase",
        entity_id=purchase.id,
        previous_values={"avg_rate": old_avg_rate, "stock": old_stock},
        updated_values={
            "purchase_number": purchase.purchase_number,
            "material": material.name,
            "base_quantity": base_qty,
            "unit_rate": unit_rate,
            "new_avg_rate": new_avg_rate,
        },
        remarks=payload.remarks,
    )
    db.commit()
    return get_purchase(db, purchase.id)


def get_purchase(db: Session, purchase_id: int) -> Purchase:
    stmt = (
        select(Purchase)
        .options(joinedload(Purchase.supplier), joinedload(Purchase.material))
        .where(Purchase.id == purchase_id)
    )
    purchase = db.execute(stmt).scalar_one_or_none()
    if not purchase:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase not found")
    return purchase
