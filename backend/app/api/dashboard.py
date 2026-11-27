from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload
from app.core.database import get_db
from app.core.permissions import UserRole, require_roles
from app.models.master import Material, Product
from app.models.production import ProductionConsumption, ProductionRun
from app.models.sales import Invoice, Order
from app.models.user import User
from app.services.costing_service import get_product_costing_summary
from app.services.payment_service import get_receivables_ageing
from app.services.stock_service import get_fg_availability, get_ledger_balance
from app.utils.calculations import round_money

router = APIRouter(prefix="/api/dashboard", tags=["Owner & Executive Dashboard"])


@router.get("/owner", summary="Owner executive KPIs, trends, stock, production & variance alerts")
def owner_dashboard(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.OWNER, UserRole.ADMIN, UserRole.ACCOUNTANT)),
):
    today = date.today()

    orders_today = db.execute(
        select(func.count(Order.id)).where(Order.order_date == today)
    ).scalar_one()
    pending_approvals = db.execute(
        select(func.count(Order.id)).where(Order.status == "submitted")
    ).scalar_one()

    total_sales = db.execute(
        select(func.coalesce(func.sum(Invoice.grand_total), Decimal("0.00"))).where(Invoice.status != "cancelled")
    ).scalar_one()

    ageing = get_receivables_ageing(db, as_of_date=today)
    outstanding_dues = ageing["summary"]["total_outstanding"]

    products = db.execute(select(Product).where(Product.is_active.is_(True)).order_by(Product.id)).scalars().all()
    fg_levels = []
    total_fg_packets = Decimal("0.0000")
    for p in products:
        fg = get_fg_availability(db, p.id)
        total_fg_packets += fg["available_stock"]
        fg_levels.append(
            {
                "name": p.name,
                "physical": float(fg["physical_stock"]),
                "reserved": float(fg["reserved_stock"]),
                "available": float(fg["available_stock"]),
                "reorder_level": float(p.reorder_level),
            }
        )

    materials = db.execute(select(Material).where(Material.is_active.is_(True)).order_by(Material.id)).scalars().all()
    rm_levels = []
    for m in materials:
        cat = "raw_material" if m.material_type == "raw" else "packaging_material"
        bal = get_ledger_balance(db, cat, material_id=m.id)
        rm_levels.append(
            {
                "name": m.name,
                "type": m.material_type,
                "stock": float(bal),
                "unit": m.base_unit,
                "reorder_level": float(m.reorder_level),
            }
        )

    costing = get_product_costing_summary(db)
        # Finished goods stock valuation using weighted average production cost
    costing_by_product = {
        item["product_id"]: item for item in costing
    }

    total_fg_stock_value = Decimal("0.00")
    unvalued_fg_packets = Decimal("0.0000")
    fg_valuation = []

    for p in products:
        fg = get_fg_availability(db, p.id)
        available_qty = fg["available_stock"]

        product_cost = costing_by_product.get(p.id)
        avg_cost = (
            Decimal(product_cost["avg_cost_per_packet"])
            if product_cost and product_cost["avg_cost_per_packet"] is not None
            else None
        )

        stock_value = (
            round_money(available_qty * avg_cost)
            if avg_cost is not None
            else None
        )

        if stock_value is not None:
            total_fg_stock_value += stock_value
        elif available_qty > 0:
            unvalued_fg_packets += available_qty

        fg_valuation.append({
            "product_id": p.id,
            "product_name": p.name,
            "available_packets": str(available_qty),
            "average_cost_per_packet": str(avg_cost) if avg_cost is not None else None,
            "stock_value": str(stock_value) if stock_value is not None else None,
            "valuation_status": "valued" if stock_value is not None else "cost_unavailable",
        })

    # Sales trend by date
    inv_rows = db.execute(select(Invoice).order_by(Invoice.invoice_date.asc())).scalars().all()
    sales_by_day: dict[str, Decimal] = {}
    for inv in inv_rows:
        dkey = inv.invoice_date.isoformat()
        sales_by_day[dkey] = round_money(sales_by_day.get(dkey, Decimal("0.00")) + inv.grand_total)
    sales_trend = [{"date": k, "sales": float(v)} for k, v in sales_by_day.items()]

    # Production performance & variance alerts
    runs = (
        db.execute(
            select(ProductionRun)
            .options(
                joinedload(ProductionRun.product),
                joinedload(ProductionRun.consumptions).joinedload(ProductionConsumption.material),
            )
            .order_by(ProductionRun.run_date.desc(), ProductionRun.id.desc())
            .limit(10)
        )
        .unique()
        .scalars()
        .all()
    )
    production_performance = []
    variance_alerts = []
    for r in runs:
        production_performance.append(
            {
                "run_number": r.run_number,
                "product": r.product.name,
                "expected": float(r.expected_output),
                "actual": float(r.actual_good_packets),
                "damaged_pouches": float(r.damaged_pouches),
                "cost_per_packet": float(round_money(r.cost_per_packet)),
            }
        )
        if r.yield_flagged:
            variance_alerts.append(
                {
                    "run_number": r.run_number,
                    "product": r.product.name,
                    "metric": "Production Yield",
                    "planned": str(r.expected_output),
                    "actual": str(r.actual_good_packets),
                    "variance_pct": str(r.yield_variance_pct),
                }
            )
        for c in r.consumptions:
            if c.is_flagged:
                variance_alerts.append(
                    {
                        "run_number": r.run_number,
                        "product": r.product.name,
                        "metric": c.material.name,
                        "planned": str(c.planned_qty),
                        "actual": str(c.actual_qty),
                        "variance_pct": str(c.variance_pct),
                    }
                )

    return {
        "kpis": {
            "orders_today": orders_today,
            "pending_approvals": pending_approvals,
            "outstanding_dues": str(outstanding_dues),
            "total_sales": str(round_money(total_sales)),
            "finished_goods_available": str(total_fg_packets),
        },
        "costing_margins": costing,
        "fg_valuation": fg_valuation,
        "fg_stock_value": str(round_money(total_fg_stock_value)),
        "unvalued_fg_packets": str(unvalued_fg_packets),
        "sales_trend": sales_trend,
        "finished_goods_levels": fg_levels,
        "material_levels": rm_levels,
        "production_performance": production_performance,
        "variance_alerts": variance_alerts,
    }
