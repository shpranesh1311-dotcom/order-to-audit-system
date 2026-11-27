from datetime import date, datetime
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from app.core.audit import log_audit
from app.core.database import get_db
from app.core.permissions import UserRole, require_roles
from app.models.inventory import StockLedger
from app.models.master import Material, Product
from app.models.user import User
from app.schemas.inventory_reports import StockAdjustmentCreate, StockLedgerRead
from app.services.stock_service import (
    get_fefo_batches,
    get_fg_availability,
    get_ledger_balance,
    reconcile_inventory,
    record_stock_movement,
)
from app.utils.calculations import round_money

router = APIRouter(prefix="/api/inventory", tags=["Inventory & Stock Ledger"])


@router.get("/summary", summary="Inventory dashboard summary derived from ledger")
def inventory_summary(
    db: Session = Depends(get_db),
    _: User = Depends(
        require_roles(UserRole.ADMIN, UserRole.PRODUCTION, UserRole.ACCOUNTANT, UserRole.OWNER)
    ),
):
    materials = db.execute(select(Material).order_by(Material.material_type, Material.id)).scalars().all()
    raw_items = []
    packaging_items = []
    low_stock = []
    total_rm_value = Decimal("0.00")
    total_pm_value = Decimal("0.00")

    for m in materials:
        cat = "raw_material" if m.material_type == "raw" else "packaging_material"
        bal = get_ledger_balance(db, cat, material_id=m.id)
        val = round_money(bal * m.current_avg_rate)
        is_low = bal <= m.reorder_level
        row = {
            "id": m.id,
            "code": m.code,
            "name": m.name,
            "category": m.category,
            "unit": m.base_unit,
            "closing_stock": bal,
            "avg_rate": m.current_avg_rate,
            "stock_value": val,
            "reorder_level": m.reorder_level,
            "is_low_stock": is_low,
        }
        if m.material_type == "raw":
            raw_items.append(row)
            total_rm_value = round_money(total_rm_value + val)
        else:
            packaging_items.append(row)
            total_pm_value = round_money(total_pm_value + val)
        if is_low:
            low_stock.append({"item_type": cat, **row})

    products = db.execute(select(Product).order_by(Product.id)).scalars().all()
    fg_items = []
    total_fg_value = Decimal("0.00")
    for p in products:
        fg = get_fg_availability(db, p.id)
        val = round_money(fg["physical_stock"] * p.selling_price)
        total_fg_value = round_money(total_fg_value + val)
        is_low = fg["available_stock"] <= p.reorder_level
        row = {
            "id": p.id,
            "code": p.code,
            "name": p.name,
            "unit": p.unit,
            "physical_stock": fg["physical_stock"],
            "reserved_stock": fg["reserved_stock"],
            "available_stock": fg["available_stock"],
            "selling_price": p.selling_price,
            "stock_value": val,
            "reorder_level": p.reorder_level,
            "is_low_stock": is_low,
            "batches": get_fefo_batches(db, p.id),
        }
        fg_items.append(row)
        if is_low:
            low_stock.append({"item_type": "finished_good", **row})

    return {
        "raw_materials": raw_items,
        "packaging_materials": packaging_items,
        "finished_goods": fg_items,
        "low_stock_alerts": low_stock,
        "valuation": {
            "raw_materials_value": total_rm_value,
            "packaging_materials_value": total_pm_value,
            "finished_goods_retail_value": total_fg_value,
        },
    }


@router.get("/ledger", response_model=list[StockLedgerRead], summary="Append-only stock movement ledger")
def list_ledger(
    item_category: str | None = Query(default=None),
    material_id: int | None = Query(default=None),
    product_id: int | None = Query(default=None),
    transaction_type: str | None = Query(default=None),
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(
        require_roles(UserRole.ADMIN, UserRole.PRODUCTION, UserRole.ACCOUNTANT, UserRole.OWNER)
    ),
):
    stmt = (
        select(StockLedger)
        .options(joinedload(StockLedger.material), joinedload(StockLedger.product))
        .order_by(StockLedger.id.desc())
    )
    if item_category:
        stmt = stmt.where(StockLedger.item_category == item_category)
    if material_id:
        stmt = stmt.where(StockLedger.material_id == material_id)
    if product_id:
        stmt = stmt.where(StockLedger.product_id == product_id)
    if transaction_type:
        stmt = stmt.where(StockLedger.transaction_type == transaction_type)
    if start_date:
        stmt = stmt.where(StockLedger.created_at >= datetime.combine(start_date, datetime.min.time()))
    if end_date:
        stmt = stmt.where(StockLedger.created_at <= datetime.combine(end_date, datetime.max.time()))

    entries = db.execute(stmt).scalars().all()
    out = []
    for e in entries:
        item = StockLedgerRead.model_validate(e)
        item.item_name = e.material.name if e.material else (e.product.name if e.product else None)
        out.append(item)
    return out


@router.get("/reconcile", summary="Reconcile cached stock balances against append-only stock ledger")
def reconcile_stock_endpoint(
    db: Session = Depends(get_db),
    _: User = Depends(
        require_roles(UserRole.ADMIN, UserRole.PRODUCTION, UserRole.ACCOUNTANT, UserRole.OWNER)
    ),
):
    items = reconcile_inventory(db)
    inconsistent = [i for i in items if not i["is_consistent"]]
    return {
        "is_fully_consistent": len(inconsistent) == 0,
        "discrepancy_count": len(inconsistent),
        "items": items,
    }


@router.post("/adjustments", response_model=StockLedgerRead, status_code=status.HTTP_201_CREATED, summary="Record audited stock adjustment (Admin)")
def adjust_stock(
    payload: StockAdjustmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    if payload.material_id:
        mat = db.get(Material, payload.material_id)
        if not mat:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found")
        unit = mat.base_unit
        rate = mat.current_avg_rate
    elif payload.product_id:
        prod = db.get(Product, payload.product_id)
        if not prod:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
        unit = prod.unit
        rate = prod.selling_price
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provide material_id or product_id")

    entry = record_stock_movement(
        db,
        item_category=payload.item_category,
        material_id=payload.material_id,
        product_id=payload.product_id,
        transaction_type="adjustment",
        direction=payload.direction,
        quantity=payload.quantity,
        unit=unit,
        rate=rate,
        source_doc_type="stock_adjustment",
        source_doc_id=0,
        source_doc_ref="ADJ-MANUAL",
        user_id=current_user.id,
        remarks=payload.remarks,
    )
    log_audit(
        db,
        user_id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        action="STOCK_ADJUSTMENT",
        entity_type="stock_ledger",
        entity_id=entry.id,
        updated_values={
            "item_category": payload.item_category,
            "direction": payload.direction,
            "quantity": payload.quantity,
            "remarks": payload.remarks,
        },
    )
    db.commit()
    db.refresh(entry)
    return StockLedgerRead.model_validate(entry)
