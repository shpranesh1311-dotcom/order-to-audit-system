from datetime import date
from decimal import Decimal
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.models.inventory import StockBalance, StockLedger, StockReservation
from app.models.master import Material, Product
from app.utils.calculations import round_money, round_qty, round_rate, to_decimal


def make_item_key(item_category: str, material_id: int | None = None, product_id: int | None = None) -> str:
    if material_id is not None:
        return f"MAT:{material_id}"
    if product_id is not None:
        return f"PROD:{product_id}"
    raise ValueError("Either material_id or product_id must be provided")


def ensure_and_lock_balance(
    db: Session,
    item_category: str,
    material_id: int | None = None,
    product_id: int | None = None,
) -> StockBalance:
    key = make_item_key(item_category, material_id=material_id, product_id=product_id)
    stmt = select(StockBalance).where(StockBalance.item_key == key).with_for_update()
    bal = db.execute(stmt).scalar_one_or_none()
    if bal is None:
        bal = StockBalance(
            item_key=key,
            item_category=item_category,
            material_id=material_id,
            product_id=product_id,
            quantity=Decimal("0.0000"),
        )
        db.add(bal)
        db.flush()
        bal = db.execute(select(StockBalance).where(StockBalance.item_key == key).with_for_update()).scalar_one()
    return bal


def get_ledger_balance(
    db: Session,
    item_category: str,
    material_id: int | None = None,
    product_id: int | None = None,
) -> Decimal:
    stmt = select(func.coalesce(func.sum(StockLedger.signed_quantity), Decimal("0.0000")))
    if material_id is not None:
        stmt = stmt.where(StockLedger.material_id == material_id)
    elif product_id is not None:
        stmt = stmt.where(StockLedger.product_id == product_id)
    else:
        raise ValueError("Either material_id or product_id must be provided")
    val = db.execute(stmt).scalar_one()
    return round_qty(val)


def get_reserved_qty(db: Session, product_id: int) -> Decimal:
    stmt = select(func.coalesce(func.sum(StockReservation.reserved_qty), Decimal("0.0000"))).where(
        StockReservation.product_id == product_id,
        StockReservation.status == "active",
    )
    return round_qty(db.execute(stmt).scalar_one())


def get_fg_availability(db: Session, product_id: int) -> dict[str, Decimal]:
    physical = get_ledger_balance(db, "finished_good", product_id=product_id)
    reserved = get_reserved_qty(db, product_id)
    available = round_qty(physical - reserved)
    return {
        "physical_stock": physical,
        "reserved_stock": reserved,
        "available_stock": available,
    }


def record_stock_movement(
    db: Session,
    *,
    item_category: str,
    material_id: int | None = None,
    product_id: int | None = None,
    transaction_type: str,
    direction: str,
    quantity: Decimal,
    unit: str,
    rate: Decimal,
    source_doc_type: str,
    source_doc_id: int,
    source_doc_ref: str | None = None,
    user_id: int | None = None,
    batch_number: str | None = None,
    expiry_date: date | None = None,
    remarks: str | None = None,
    allow_negative: bool = False,
) -> StockLedger:
    qty = round_qty(quantity)
    if qty <= Decimal("0"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Stock movement quantity must be greater than zero",
        )
    if direction not in ("IN", "OUT"):
        raise ValueError(f"Invalid stock direction: {direction}")

    bal_row = ensure_and_lock_balance(
        db, item_category, material_id=material_id, product_id=product_id
    )
    current_physical = get_ledger_balance(
        db, item_category, material_id=material_id, product_id=product_id
    )

    signed = qty if direction == "IN" else -qty
    new_balance = round_qty(current_physical + signed)

    if direction == "OUT" and not allow_negative and new_balance < Decimal("0"):
        shortage = round_qty(qty - current_physical)
        item_label = f"Material #{material_id}" if material_id else f"Product #{product_id}"
        if material_id:
            mat = db.get(Material, material_id)
            if mat:
                item_label = mat.name
        elif product_id:
            prod = db.get(Product, product_id)
            if prod:
                item_label = prod.name
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Insufficient stock for {item_label}. Requested: {qty} {unit}, Available: {current_physical} {unit}, Shortage: {shortage} {unit}",
        )

    rate_val = round_rate(rate)
    total_val = round_money(qty * rate_val)

    ledger_entry = StockLedger(
        item_category=item_category,
        material_id=material_id,
        product_id=product_id,
        transaction_type=transaction_type,
        direction=direction,
        quantity=qty,
        signed_quantity=signed,
        unit=unit,
        rate=rate_val,
        total_value=total_val,
        batch_number=batch_number,
        expiry_date=expiry_date,
        source_doc_type=source_doc_type,
        source_doc_id=source_doc_id,
        source_doc_ref=source_doc_ref,
        user_id=user_id,
        remarks=remarks,
    )
    db.add(ledger_entry)
    bal_row.quantity = new_balance
    db.flush()
    return ledger_entry


def reconcile_inventory(db: Session) -> list[dict]:
    """Compare cached StockBalance rows with ledger-derived SUM(signed_quantity) without altering ledger."""
    balances = db.execute(select(StockBalance).order_by(StockBalance.id)).scalars().all()
    results: list[dict] = []
    for bal in balances:
        ledger_qty = get_ledger_balance(
            db, bal.item_category, material_id=bal.material_id, product_id=bal.product_id
        )
        diff = round_qty(bal.quantity - ledger_qty)
        item_name = bal.item_key
        unit = ""
        if bal.material_id:
            mat = db.get(Material, bal.material_id)
            if mat:
                item_name = mat.name
                unit = mat.base_unit
        elif bal.product_id:
            prod = db.get(Product, bal.product_id)
            if prod:
                item_name = prod.name
                unit = prod.unit
        results.append(
            {
                "item_key": bal.item_key,
                "item_category": bal.item_category,
                "item_name": item_name,
                "unit": unit,
                "cached_balance": bal.quantity,
                "ledger_balance": ledger_qty,
                "difference": diff,
                "is_consistent": diff == Decimal("0.0000"),
            }
        )
    return results


def get_fefo_batches(db: Session, product_id: int) -> list[dict]:
    """Return available finished-goods batches ordered by earliest expiry date (FEFO)."""
    stmt = (
        select(
            StockLedger.batch_number,
            StockLedger.expiry_date,
            func.sum(StockLedger.signed_quantity).label("qty"),
        )
        .where(
            StockLedger.product_id == product_id,
            StockLedger.batch_number.is_not(None),
        )
        .group_by(StockLedger.batch_number, StockLedger.expiry_date)
        .having(func.sum(StockLedger.signed_quantity) > Decimal("0"))
        .order_by(StockLedger.expiry_date.asc().nulls_last(), StockLedger.batch_number.asc())
    )
    rows = db.execute(stmt).all()
    return [
        {
            "batch_number": r.batch_number,
            "expiry_date": r.expiry_date,
            "available_qty": round_qty(r.qty),
        }
        for r in rows
    ]
