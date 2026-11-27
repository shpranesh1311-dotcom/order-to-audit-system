from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from app.models.master import Product
from app.models.production import ProductionConsumption, ProductionRun
from app.utils.calculations import round_money, round_pct


def get_product_costing_summary(db: Session) -> list[dict]:
    products = db.execute(select(Product).where(Product.is_active.is_(True)).order_by(Product.id)).scalars().all()
    results: list[dict] = []
    for prod in products:
        latest_run = db.execute(
            select(ProductionRun)
            .where(ProductionRun.product_id == prod.id)
            .order_by(ProductionRun.run_date.desc(), ProductionRun.id.desc())
            .limit(1)
        ).scalar_one_or_none()

        all_runs = db.execute(
            select(ProductionRun).where(ProductionRun.product_id == prod.id)
        ).scalars().all()

        if latest_run:
            latest_cpp = round_money(latest_run.cost_per_packet)
            total_packets = sum((r.actual_good_packets for r in all_runs), Decimal("0.0000"))
            total_cost_all = sum((r.total_cost for r in all_runs), Decimal("0.00"))
            avg_cpp = round_money(total_cost_all / total_packets) if total_packets > 0 else latest_cpp
            profit_per_packet = round_money(prod.selling_price - latest_cpp)
            margin_pct = round_pct((profit_per_packet / prod.selling_price) * Decimal("100")) if prod.selling_price > 0 else Decimal("0.00")
            results.append(
                {
                    "product_id": prod.id,
                    "product_code": prod.code,
                    "product_name": prod.name,
                    "selling_price_excl_gst": str(prod.selling_price),
                    "latest_run_number": latest_run.run_number,
                    "latest_cost_per_packet": str(latest_cpp),
                    "latest_cost_per_packet_precise": str(latest_run.cost_per_packet),
                    "avg_cost_per_packet": str(avg_cpp),
                    "profit_per_packet": str(profit_per_packet),
                    "profit_margin_pct": str(margin_pct),
                    "total_runs": len(all_runs),
                    "total_packets_produced": str(total_packets),
                }
            )
        else:
            results.append(
                {
                    "product_id": prod.id,
                    "product_code": prod.code,
                    "product_name": prod.name,
                    "selling_price_excl_gst": str(prod.selling_price),
                    "latest_run_number": None,
                    "latest_cost_per_packet": None,
                    "latest_cost_per_packet_precise": None,
                    "avg_cost_per_packet": None,
                    "profit_per_packet": None,
                    "profit_margin_pct": None,
                    "total_runs": 0,
                    "total_packets_produced": str(Decimal("0.0000")),
                }
            )
    return results


def get_production_cost_breakdown(db: Session, run_id: int) -> dict | None:
    run = (
        db.execute(
            select(ProductionRun)
            .options(
                joinedload(ProductionRun.product),
                joinedload(ProductionRun.consumptions).joinedload(ProductionConsumption.material),
            )
            .where(ProductionRun.id == run_id)
        )
        .unique()
        .scalar_one_or_none()
    )
    if not run:
        return None

    display_cpp = round_money(run.cost_per_packet)
    selling = run.product.selling_price
    profit_per_packet = round_money(selling - display_cpp)
    margin_pct = round_pct((profit_per_packet / selling) * Decimal("100")) if selling > 0 else Decimal("0.00")
    return {
        "run_id": run.id,
        "run_number": run.run_number,
        "run_date": run.run_date.isoformat(),
        "product_id": run.product_id,
        "product_name": run.product.name,
        "good_packets_produced": str(run.actual_good_packets),
        "raw_material_cost": str(run.raw_material_cost),
        "packaging_cost": str(run.packaging_cost),
        "labour_cost": str(run.labour_cost),
        "gas_cost": str(run.gas_cost),
        "power_cost": str(run.power_cost),
        "other_overhead_cost": str(run.other_overhead_cost),
        "total_production_cost": str(run.total_cost),
        "cost_per_packet": str(display_cpp),
        "cost_per_packet_precise": str(run.cost_per_packet),
        "selling_price_excl_gst": str(selling),
        "profit_per_packet": str(profit_per_packet),
        "profit_margin_pct": str(margin_pct),
        "lines": [
            {
                "material_name": c.material.name,
                "material_type": c.material_type,
                "actual_qty": str(c.actual_qty),
                "unit": c.unit,
                "unit_cost": str(c.unit_cost),
                "total_cost": str(c.total_cost),
            }
            for c in run.consumptions
        ],
    }
