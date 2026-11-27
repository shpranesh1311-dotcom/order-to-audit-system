import csv
import io
from datetime import date
from decimal import Decimal

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.inventory import StockLedger
from app.models.master import Customer, Material, Product, Supplier
from app.models.production import ProductionConsumption, ProductionRun
from app.models.purchase import Purchase
from app.models.sales import Invoice, InvoiceItem, Order, Payment

from app.services.costing_service import get_product_costing_summary
from app.services.payment_service import (
    get_invoice_outstanding,
    get_receivables_ageing,
)
from app.services.stock_service import (
    get_fg_availability,
    get_ledger_balance,
)
from app.utils.calculations import round_money


def _date_in_range(
    d: date,
    start_date: date | None,
    end_date: date | None,
) -> bool:
    if start_date and d < start_date:
        return False

    if end_date and d > end_date:
        return False

    return True


def build_report(
    db: Session,
    report_type: str,
    start_date: date | None = None,
    end_date: date | None = None,
    material_id: int | None = None,
) -> dict:

    # Map frontend report names to existing backend implementations.
    report_aliases = {
        "production_report": "production_variance",
        "variance_analysis": "production_variance",
        "costing_report": "costing_summary",
        "payment_collection": "payment_register",
        "outstanding_balances": "receivables_ageing",
    }

    report_type = report_aliases.get(report_type, report_type)

    # ---------------------------------------------------------
    # 1. SALES REGISTER
    # ---------------------------------------------------------

    if report_type == "sales_register":

        invoices = (
            db.execute(
                select(Invoice)
                .options(
                    joinedload(Invoice.customer),
                    joinedload(Invoice.order).joinedload(Order.salesman),
                )
                .order_by(
                    Invoice.invoice_date.desc(),
                    Invoice.id.desc(),
                )
            )
            .unique()
            .scalars()
            .all()
        )

        rows = []

        for inv in invoices:

            if not _date_in_range(
                inv.invoice_date,
                start_date,
                end_date,
            ):
                continue

            paid, outstanding = get_invoice_outstanding(db, inv)

            rows.append(
                {
                    "invoice_number": inv.invoice_number,
                    "invoice_date": inv.invoice_date.isoformat(),
                    "customer": inv.buyer_name,
                    "state": inv.place_of_supply,
                    "salesman": (
                        inv.order.salesman.full_name
                        if inv.order and inv.order.salesman
                        else "-"
                    ),
                    "tax_type": inv.tax_type,
                    "taxable_value": str(inv.taxable_value),
                    "cgst": str(inv.cgst_amount),
                    "sgst": str(inv.sgst_amount),
                    "igst": str(inv.igst_amount),
                    "grand_total": str(inv.grand_total),
                    "paid": str(paid),
                    "outstanding": str(outstanding),
                    "dispatch_status": inv.dispatch_status,
                }
            )

        return {
            "report_type": report_type,
            "title": "Sales Register",
            "columns": [
                "invoice_number",
                "invoice_date",
                "customer",
                "state",
                "salesman",
                "tax_type",
                "taxable_value",
                "cgst",
                "sgst",
                "igst",
                "grand_total",
                "paid",
                "outstanding",
                "dispatch_status",
            ],
            "rows": rows,
        }

    # ---------------------------------------------------------
    # 2. SALES BY CUSTOMER
    # ---------------------------------------------------------

    if report_type == "sales_by_customer":

        invoices = db.execute(
            select(Invoice)
        ).scalars().all()

        agg = {}

        for inv in invoices:

            if not _date_in_range(
                inv.invoice_date,
                start_date,
                end_date,
            ):
                continue

            paid, outstanding = get_invoice_outstanding(db, inv)

            entry = agg.setdefault(
                inv.buyer_name,
                {
                    "customer": inv.buyer_name,
                    "state": inv.buyer_state,
                    "invoices": 0,
                    "taxable_value": Decimal("0.00"),
                    "total_tax": Decimal("0.00"),
                    "grand_total": Decimal("0.00"),
                    "paid": Decimal("0.00"),
                    "outstanding": Decimal("0.00"),
                },
            )

            entry["invoices"] += 1
            entry["taxable_value"] = round_money(
                entry["taxable_value"] + inv.taxable_value
            )
            entry["total_tax"] = round_money(
                entry["total_tax"] + inv.total_tax
            )
            entry["grand_total"] = round_money(
                entry["grand_total"] + inv.grand_total
            )
            entry["paid"] = round_money(
                entry["paid"] + paid
            )
            entry["outstanding"] = round_money(
                entry["outstanding"] + outstanding
            )

        rows = [
            {
                k: str(v) if isinstance(v, Decimal) else v
                for k, v in r.items()
            }
            for r in agg.values()
        ]

        return {
            "report_type": report_type,
            "title": "Customer-wise Sales Summary",
            "columns": [
                "customer",
                "state",
                "invoices",
                "taxable_value",
                "total_tax",
                "grand_total",
                "paid",
                "outstanding",
            ],
            "rows": rows,
        }

    # ---------------------------------------------------------
    # 3. SALES BY PRODUCT
    # ---------------------------------------------------------

    if report_type == "sales_by_product":

        items = (
            db.execute(
                select(InvoiceItem).options(
                    joinedload(InvoiceItem.invoice)
                )
            )
            .scalars()
            .all()
        )

        agg = {}

        for it in items:

            if not _date_in_range(
                it.invoice.invoice_date,
                start_date,
                end_date,
            ):
                continue

            entry = agg.setdefault(
                it.product_name,
                {
                    "product_name": it.product_name,
                    "hsn_code": it.hsn_code,
                    "quantity": Decimal("0.0000"),
                    "taxable_value": Decimal("0.00"),
                    "total_amount": Decimal("0.00"),
                },
            )

            entry["quantity"] += it.quantity
            entry["taxable_value"] = round_money(
                entry["taxable_value"] + it.taxable_value
            )
            entry["total_amount"] = round_money(
                entry["total_amount"] + it.total_amount
            )

        rows = [
            {
                k: str(v) if isinstance(v, Decimal) else v
                for k, v in r.items()
            }
            for r in agg.values()
        ]

        return {
            "report_type": report_type,
            "title": "Product-wise Sales Summary",
            "columns": [
                "product_name",
                "hsn_code",
                "quantity",
                "taxable_value",
                "total_amount",
            ],
            "rows": rows,
        }

    # ---------------------------------------------------------
    # 4. SALES BY SALESMAN
    # ---------------------------------------------------------

    if report_type == "sales_by_salesman":

        orders = (
            db.execute(
                select(Order).options(
                    joinedload(Order.salesman),
                    joinedload(Order.invoice),
                )
            )
            .scalars()
            .all()
        )

        agg = {}

        for o in orders:

            if not _date_in_range(
                o.order_date,
                start_date,
                end_date,
            ):
                continue

            sname = (
                o.salesman.full_name
                if o.salesman
                else f"User #{o.salesman_id}"
            )

            entry = agg.setdefault(
                sname,
                {
                    "salesman": sname,
                    "total_orders": 0,
                    "approved_or_invoiced": 0,
                    "rejected": 0,
                    "order_value": Decimal("0.00"),
                    "invoiced_value": Decimal("0.00"),
                },
            )

            entry["total_orders"] += 1

            if o.status in ("approved", "invoiced", "dispatched"):
                entry["approved_or_invoiced"] += 1

            if o.status == "rejected":
                entry["rejected"] += 1

            entry["order_value"] = round_money(
                entry["order_value"] + o.total_amount
            )

            if o.invoice:
                entry["invoiced_value"] = round_money(
                    entry["invoiced_value"] + o.invoice.grand_total
                )

        rows = [
            {
                k: str(v) if isinstance(v, Decimal) else v
                for k, v in r.items()
            }
            for r in agg.values()
        ]

        return {
            "report_type": report_type,
            "title": "Salesman-wise Sales Summary",
            "columns": [
                "salesman",
                "total_orders",
                "approved_or_invoiced",
                "rejected",
                "order_value",
                "invoiced_value",
            ],
            "rows": rows,
        }

    # ---------------------------------------------------------
    # 5. GST SUMMARY
    # ---------------------------------------------------------

    if report_type == "gst_summary":

        items = (
            db.execute(
                select(InvoiceItem).options(
                    joinedload(InvoiceItem.invoice)
                )
            )
            .scalars()
            .all()
        )

        hsn_agg = {}

        totals = {
            "taxable_value": Decimal("0.00"),
            "cgst_amount": Decimal("0.00"),
            "sgst_amount": Decimal("0.00"),
            "igst_amount": Decimal("0.00"),
            "total_tax": Decimal("0.00"),
            "grand_total": Decimal("0.00"),
        }

        for it in items:

            if not _date_in_range(
                it.invoice.invoice_date,
                start_date,
                end_date,
            ):
                continue

            key = (it.hsn_code, str(it.gst_rate))

            entry = hsn_agg.setdefault(
                key,
                {
                    "hsn_code": it.hsn_code,
                    "gst_rate_pct": str(it.gst_rate),
                    "total_quantity": Decimal("0.0000"),
                    "taxable_value": Decimal("0.00"),
                    "cgst_amount": Decimal("0.00"),
                    "sgst_amount": Decimal("0.00"),
                    "igst_amount": Decimal("0.00"),
                    "total_tax": Decimal("0.00"),
                    "total_invoice_value": Decimal("0.00"),
                },
            )

            entry["total_quantity"] += it.quantity

            entry["taxable_value"] = round_money(
                entry["taxable_value"] + it.taxable_value
            )
            entry["cgst_amount"] = round_money(
                entry["cgst_amount"] + it.cgst_amount
            )
            entry["sgst_amount"] = round_money(
                entry["sgst_amount"] + it.sgst_amount
            )
            entry["igst_amount"] = round_money(
                entry["igst_amount"] + it.igst_amount
            )

            line_tax = round_money(
                it.cgst_amount + it.sgst_amount + it.igst_amount
            )

            entry["total_tax"] = round_money(
                entry["total_tax"] + line_tax
            )

            entry["total_invoice_value"] = round_money(
                entry["total_invoice_value"] + it.total_amount
            )

            totals["taxable_value"] = round_money(
                totals["taxable_value"] + it.taxable_value
            )
            totals["cgst_amount"] = round_money(
                totals["cgst_amount"] + it.cgst_amount
            )
            totals["sgst_amount"] = round_money(
                totals["sgst_amount"] + it.sgst_amount
            )
            totals["igst_amount"] = round_money(
                totals["igst_amount"] + it.igst_amount
            )
            totals["total_tax"] = round_money(
                totals["total_tax"] + line_tax
            )
            totals["grand_total"] = round_money(
                totals["grand_total"] + it.total_amount
            )

        rows = [
            {
                k: str(v) if isinstance(v, Decimal) else v
                for k, v in r.items()
            }
            for r in hsn_agg.values()
        ]

        return {
            "report_type": report_type,
            "title": "GST Outward Supplies Summary",
            "disclaimer": (
                "For internal accounting and GST return preparation "
                "reference only. This system does not file GST returns."
            ),
            "summary": {
                k: str(v)
                for k, v in totals.items()
            },
            "columns": [
                "hsn_code",
                "gst_rate_pct",
                "total_quantity",
                "taxable_value",
                "cgst_amount",
                "sgst_amount",
                "igst_amount",
                "total_tax",
                "total_invoice_value",
            ],
            "rows": rows,
        }

    # ---------------------------------------------------------
    # 6. GST SALES DETAIL
    # ---------------------------------------------------------

    if report_type == "gst_sales_detail":

        items = (
            db.execute(
                select(InvoiceItem)
                .options(joinedload(InvoiceItem.invoice))
                .order_by(InvoiceItem.id)
            )
            .scalars()
            .all()
        )

        rows = []

        for it in items:

            inv = it.invoice

            if not _date_in_range(
                inv.invoice_date,
                start_date,
                end_date,
            ):
                continue

            rows.append(
                {
                    "invoice_number": inv.invoice_number,
                    "invoice_date": inv.invoice_date.isoformat(),
                    "customer": inv.buyer_name,
                    "buyer_gstin": inv.buyer_gstin or "-",
                    "place_of_supply": inv.place_of_supply,
                    "tax_type": inv.tax_type,
                    "product": it.product_name,
                    "hsn_code": it.hsn_code,
                    "quantity": str(it.quantity),
                    "unit_price": str(it.unit_price),
                    "taxable_value": str(it.taxable_value),
                    "gst_rate": str(it.gst_rate),
                    "cgst_amount": str(it.cgst_amount),
                    "sgst_amount": str(it.sgst_amount),
                    "igst_amount": str(it.igst_amount),
                    "total_amount": str(it.total_amount),
                }
            )

        return {
            "report_type": report_type,
            "title": "GST Sales Detail Report",
            "disclaimer": (
                "Detailed outward supply information for internal "
                "GST reconciliation. This report does not file GST returns."
            ),
            "columns": [
                "invoice_number",
                "invoice_date",
                "customer",
                "buyer_gstin",
                "place_of_supply",
                "tax_type",
                "product",
                "hsn_code",
                "quantity",
                "unit_price",
                "taxable_value",
                "gst_rate",
                "cgst_amount",
                "sgst_amount",
                "igst_amount",
                "total_amount",
            ],
            "rows": rows,
        }

    # ---------------------------------------------------------
    # 7. PURCHASE REGISTER AND PURCHASE SUMMARIES
    # ---------------------------------------------------------

    if report_type in (
        "purchase_register",
        "purchases_by_supplier",
        "purchases_by_material",
    ):

        purchases = (
            db.execute(
                select(Purchase)
                .options(
                    joinedload(Purchase.supplier),
                    joinedload(Purchase.material),
                )
                .order_by(
                    Purchase.purchase_date.desc(),
                    Purchase.id.desc(),
                )
            )
            .scalars()
            .all()
        )

        filtered = [
            p for p in purchases
            if _date_in_range(
                p.purchase_date,
                start_date,
                end_date,
            )
        ]

        if report_type == "purchase_register":

            rows = [
                {
                    "purchase_number": p.purchase_number,
                    "purchase_date": p.purchase_date.isoformat(),
                    "supplier": p.supplier.name,
                    "invoice_number": p.invoice_number,
                    "material": p.material.name,
                    "material_type": p.material.material_type,
                    "quantity": str(p.quantity),
                    "unit": p.unit,
                    "unit_rate": str(p.unit_rate),
                    "total_amount": str(p.total_amount),
                }
                for p in filtered
            ]

            return {
                "report_type": report_type,
                "title": "Purchase Register",
                "columns": [
                    "purchase_number",
                    "purchase_date",
                    "supplier",
                    "invoice_number",
                    "material",
                    "material_type",
                    "quantity",
                    "unit",
                    "unit_rate",
                    "total_amount",
                ],
                "rows": rows,
            }

        key_name = (
            "supplier"
            if report_type == "purchases_by_supplier"
            else "material"
        )

        agg = {}

        for p in filtered:

            key = (
                p.supplier.name
                if report_type == "purchases_by_supplier"
                else p.material.name
            )

            entry = agg.setdefault(
                key,
                {
                    key_name: key,
                    "transactions": 0,
                    "total_base_qty": Decimal("0.0000"),
                    "unit": (
                        p.material.base_unit
                        if report_type == "purchases_by_material"
                        else "mixed"
                    ),
                    "total_amount": Decimal("0.00"),
                },
            )

            entry["transactions"] += 1
            entry["total_base_qty"] += p.base_quantity
            entry["total_amount"] = round_money(
                entry["total_amount"] + p.total_amount
            )

        rows = [
            {
                k: str(v) if isinstance(v, Decimal) else v
                for k, v in r.items()
            }
            for r in agg.values()
        ]

        return {
            "report_type": report_type,
            "title": (
                "Supplier-wise Purchases"
                if report_type == "purchases_by_supplier"
                else "Material-wise Purchases"
            ),
            "columns": [
                key_name,
                "transactions",
                "total_base_qty",
                "unit",
                "total_amount",
            ],
            "rows": rows,
        }

    # ---------------------------------------------------------
    # 8. GST PURCHASE DETAIL
    # ---------------------------------------------------------

    if report_type == "gst_purchase_detail":

        purchases = (
            db.execute(
                select(Purchase)
                .options(
                    joinedload(Purchase.supplier),
                    joinedload(Purchase.material),
                )
                .order_by(
                    Purchase.purchase_date.desc(),
                    Purchase.id.desc(),
                )
            )
            .scalars()
            .all()
        )

        rows = []

        for p in purchases:

            if not _date_in_range(
                p.purchase_date,
                start_date,
                end_date,
            ):
                continue

            rows.append(
                {
                    "purchase_number": p.purchase_number,
                    "purchase_date": p.purchase_date.isoformat(),
                    "supplier": p.supplier.name,
                    "invoice_number": p.invoice_number,
                    "material": p.material.name,
                    "quantity": str(p.quantity),
                    "unit": p.unit,
                    "unit_rate": str(p.unit_rate),
                    "taxable_value": str(p.total_amount),
                    "gst_status": "GST details not recorded",
                }
            )

        return {
            "report_type": report_type,
            "title": "GST Purchase Detail Report",
            "disclaimer": (
                "Purchase records currently do not store GST rates, "
                "CGST, SGST or IGST amounts. The purchase amount is shown "
                "without assuming any GST calculation."
            ),
            "columns": [
                "purchase_number",
                "purchase_date",
                "supplier",
                "invoice_number",
                "material",
                "quantity",
                "unit",
                "unit_rate",
                "taxable_value",
                "gst_status",
            ],
            "rows": rows,
        }

    # ---------------------------------------------------------
    # 9. INVENTORY SUMMARY
    # ---------------------------------------------------------

    if report_type == "inventory_summary":

        rows = []

        materials = (
            db.execute(
                select(Material).order_by(
                    Material.material_type,
                    Material.id,
                )
            )
            .scalars()
            .all()
        )

        for m in materials:

            cat = (
                "raw_material"
                if m.material_type == "raw"
                else "packaging_material"
            )

            bal = get_ledger_balance(
                db,
                cat,
                material_id=m.id,
            )

            val = round_money(
                bal * m.current_avg_rate
            )

            rows.append(
                {
                    "category": cat,
                    "code": m.code,
                    "item_name": m.name,
                    "unit": m.base_unit,
                    "closing_stock": str(bal),
                    "reserved": "0.0000",
                    "available": str(bal),
                    "valuation_rate": str(m.current_avg_rate),
                    "stock_value": str(val),
                    "reorder_level": str(m.reorder_level),
                    "status": (
                        "LOW_STOCK"
                        if bal <= m.reorder_level
                        else "OK"
                    ),
                }
            )

        products = (
            db.execute(
                select(Product).order_by(Product.id)
            )
            .scalars()
            .all()
        )

        for p in products:

            fg = get_fg_availability(db, p.id)

            val = round_money(
                fg["physical_stock"] * p.selling_price
            )

            rows.append(
                {
                    "category": "finished_good",
                    "code": p.code,
                    "item_name": p.name,
                    "unit": p.unit,
                    "closing_stock": str(fg["physical_stock"]),
                    "reserved": str(fg["reserved_stock"]),
                    "available": str(fg["available_stock"]),
                    "valuation_rate": str(p.selling_price),
                    "stock_value": str(val),
                    "reorder_level": str(p.reorder_level),
                    "status": (
                        "LOW_STOCK"
                        if fg["available_stock"] <= p.reorder_level
                        else "OK"
                    ),
                }
            )

        return {
            "report_type": report_type,
            "title": "Inventory Stock Summary & Valuation",
            "columns": [
                "category",
                "code",
                "item_name",
                "unit",
                "closing_stock",
                "reserved",
                "available",
                "valuation_rate",
                "stock_value",
                "reorder_level",
                "status",
            ],
            "rows": rows,
        }

    # ---------------------------------------------------------
    # 10. STOCK LEDGER
    # ---------------------------------------------------------

    if report_type == "stock_ledger":

        query = select(StockLedger).order_by(
            StockLedger.created_at.desc(),
            StockLedger.id.desc(),
        )

        if material_id is not None:
            query = query.where(
                StockLedger.material_id == material_id
            )

        ledger_entries = (
            db.execute(query)
            .scalars()
            .all()
        )

        rows = []

        for entry in ledger_entries:

            entry_date = entry.created_at.date()

            if not _date_in_range(
                entry_date,
                start_date,
                end_date,
            ):
                continue

            item_name = "-"

            if entry.material_id:
                material = db.get(
                    Material,
                    entry.material_id,
                )

                if material:
                    item_name = material.name

            elif entry.product_id:
                product = db.get(
                    Product,
                    entry.product_id,
                )

                if product:
                    item_name = product.name

            rows.append(
                {
                    "transaction_id": entry.id,
                    "transaction_date": entry_date.isoformat(),
                    "item_category": entry.item_category,
                    "item_name": item_name,
                    "transaction_type": entry.transaction_type,
                    "direction": entry.direction,
                    "quantity": str(entry.quantity),
                    "signed_quantity": str(entry.signed_quantity),
                    "unit": entry.unit,
                    "rate": str(entry.rate),
                    "total_value": str(entry.total_value),
                    "source_doc_type": entry.source_doc_type or "-",
                    "source_doc_id": (
                        str(entry.source_doc_id)
                        if entry.source_doc_id
                        else "-"
                    ),
                    "source_doc_ref": entry.source_doc_ref or "-",
                    "remarks": entry.remarks or "-",
                }
            )

        return {
            "report_type": report_type,
            "title": "Stock Movement Ledger",
            "columns": [
                "transaction_id",
                "transaction_date",
                "item_category",
                "item_name",
                "transaction_type",
                "direction",
                "quantity",
                "signed_quantity",
                "unit",
                "rate",
                "total_value",
                "source_doc_type",
                "source_doc_id",
                "source_doc_ref",
                "remarks",
            ],
            "rows": rows,
        }

    # ---------------------------------------------------------
    # 11. PRODUCTION VARIANCE
    # ---------------------------------------------------------

    if report_type == "production_variance":

        runs = (
            db.execute(
                select(ProductionRun)
                .options(
                    joinedload(ProductionRun.product),
                    joinedload(
                        ProductionRun.consumptions
                    ).joinedload(
                        ProductionConsumption.material
                    ),
                )
                .order_by(
                    ProductionRun.run_date.desc(),
                    ProductionRun.id.desc(),
                )
            )
            .unique()
            .scalars()
            .all()
        )

        rows = []

        for r in runs:

            if not _date_in_range(
                r.run_date,
                start_date,
                end_date,
            ):
                continue

            rows.append(
                {
                    "run_number": r.run_number,
                    "run_date": r.run_date.isoformat(),
                    "product": r.product.name,
                    "item_or_metric": "Yield (Good Packets)",
                    "planned_or_expected": str(r.expected_output),
                    "actual": str(r.actual_good_packets),
                    "unit": "packet",
                    "variance_qty": str(r.yield_variance_qty),
                    "variance_pct": f"{r.yield_variance_pct}%",
                    "status": (
                        "Flagged"
                        if r.yield_flagged
                        else "Within tolerance"
                    ),
                }
            )

            for c in r.consumptions:

                rows.append(
                    {
                        "run_number": r.run_number,
                        "run_date": r.run_date.isoformat(),
                        "product": r.product.name,
                        "item_or_metric": c.material.name,
                        "planned_or_expected": str(c.planned_qty),
                        "actual": str(c.actual_qty),
                        "unit": c.unit,
                        "variance_qty": str(c.variance_qty),
                        "variance_pct": f"{c.variance_pct}%",
                        "status": (
                            "Flagged"
                            if c.is_flagged
                            else "Within tolerance"
                        ),
                    }
                )

        return {
            "report_type": report_type,
            "title": "Production Planned vs Actual & Variance Report",
            "columns": [
                "run_number",
                "run_date",
                "product",
                "item_or_metric",
                "planned_or_expected",
                "actual",
                "unit",
                "variance_qty",
                "variance_pct",
                "status",
            ],
            "rows": rows,
        }

    # ---------------------------------------------------------
    # 12. COSTING SUMMARY
    # ---------------------------------------------------------

    if report_type == "costing_summary":

        runs = (
            db.execute(
                select(ProductionRun)
                .options(
                    joinedload(ProductionRun.product)
                )
                .order_by(
                    ProductionRun.run_date.desc(),
                    ProductionRun.id.desc(),
                )
            )
            .scalars()
            .all()
        )

        rows = []

        for r in runs:

            if not _date_in_range(
                r.run_date,
                start_date,
                end_date,
            ):
                continue

            overhead = round_money(
                r.gas_cost
                + r.power_cost
                + r.other_overhead_cost
            )

            rows.append(
                {
                    "run_number": r.run_number,
                    "run_date": r.run_date.isoformat(),
                    "product": r.product.name,
                    "good_packets": str(r.actual_good_packets),
                    "raw_material_cost": str(r.raw_material_cost),
                    "packaging_cost": str(r.packaging_cost),
                    "labour_cost": str(r.labour_cost),
                    "overhead_cost": str(overhead),
                    "total_cost": str(r.total_cost),
                    "cost_per_packet": str(
                        round_money(r.cost_per_packet)
                    ),
                }
            )

        return {
            "report_type": report_type,
            "title": "Production Run Costing & Cost Per Packet",
            "product_margins": [
                {
                    k: str(v) if isinstance(v, Decimal) else v
                    for k, v in m.items()
                }
                for m in get_product_costing_summary(db)
            ],
            "columns": [
                "run_number",
                "run_date",
                "product",
                "good_packets",
                "raw_material_cost",
                "packaging_cost",
                "labour_cost",
                "overhead_cost",
                "total_cost",
                "cost_per_packet",
            ],
            "rows": rows,
        }

    # ---------------------------------------------------------
    # 13. PAYMENT REGISTER
    # ---------------------------------------------------------

    if report_type == "payment_register":

        payments = (
            db.execute(
                select(Payment)
                .options(
                    joinedload(Payment.customer),
                    joinedload(Payment.invoice),
                )
                .order_by(
                    Payment.payment_date.desc(),
                    Payment.id.desc(),
                )
            )
            .scalars()
            .all()
        )

        rows = []

        for p in payments:

            if not _date_in_range(
                p.payment_date,
                start_date,
                end_date,
            ):
                continue

            rows.append(
                {
                    "payment_number": p.payment_number,
                    "payment_date": p.payment_date.isoformat(),
                    "customer": p.customer.name,
                    "invoice_number": (
                        p.invoice.invoice_number
                        if p.invoice
                        else "-"
                    ),
                    "method": p.payment_method,
                    "reference": p.reference_number or "-",
                    "amount": str(p.amount),
                }
            )

        return {
            "report_type": report_type,
            "title": "Payment & Collection Register",
            "columns": [
                "payment_number",
                "payment_date",
                "customer",
                "invoice_number",
                "method",
                "reference",
                "amount",
            ],
            "rows": rows,
        }

    # ---------------------------------------------------------
    # 14. RECEIVABLES AGEING
    # ---------------------------------------------------------

    if report_type == "receivables_ageing":

        ageing = get_receivables_ageing(
            db,
            as_of_date=end_date or date.today(),
        )

        rows = [
            {
                k: str(v) if isinstance(v, Decimal) else v
                for k, v in inv.items()
            }
            for inv in ageing["invoices"]
        ]

        return {
            "report_type": report_type,
            "title": "Outstanding Receivables & Ageing Report",
            "summary": {
                k: str(v)
                for k, v in ageing["summary"].items()
            },
            "columns": [
                "invoice_number",
                "invoice_date",
                "customer_name",
                "grand_total",
                "paid_amount",
                "outstanding_amount",
                "days_outstanding",
                "ageing_bucket",
            ],
            "rows": rows,
        }

    # ---------------------------------------------------------
    # 15. PROFIT & LOSS SUMMARY (OPERATIONAL ESTIMATE)
    # ---------------------------------------------------------

    if report_type == "profit_loss_summary":

        invoices = (
            db.execute(
                select(Invoice)
            )
            .scalars()
            .all()
        )

        runs = (
            db.execute(
                select(ProductionRun)
            )
            .scalars()
            .all()
        )

        total_sales = Decimal("0.00")
        total_tax = Decimal("0.00")
        production_cost = Decimal("0.00")
        total_packets = Decimal("0")

        for inv in invoices:

            if not _date_in_range(
                inv.invoice_date,
                start_date,
                end_date,
            ):
                continue

            total_sales = round_money(
                total_sales + inv.taxable_value
            )

            total_tax = round_money(
                total_tax + inv.total_tax
            )

        for r in runs:

            if not _date_in_range(
                r.run_date,
                start_date,
                end_date,
            ):
                continue

            production_cost = round_money(
                production_cost + r.total_cost
            )

            total_packets += r.actual_good_packets

        estimated_difference = round_money(
            total_sales - production_cost
        )

        rows = [
            {
                "metric": "Taxable Sales",
                "amount": str(total_sales),
            },
            {
                "metric": "GST Collected",
                "amount": str(total_tax),
            },
            {
                "metric": "Production Cost",
                "amount": str(production_cost),
            },
            {
                "metric": "Sales Less Production Cost",
                "amount": str(estimated_difference),
            },
            {
                "metric": "Good Packets Produced",
                "amount": str(total_packets),
            },
        ]

        return {
            "report_type": report_type,
            "title": "Operational Profit & Loss Summary",
            "disclaimer": (
                "This is an operational estimate, not an audited "
                "profit and loss statement. Production costs are compared "
                "with taxable sales in the selected period. The calculation "
                "does not match the cost of individual sold quantities and "
                "does not include all expenses, inventory adjustments, "
                "or accounting adjustments."
            ),
            "columns": [
                "metric",
                "amount",
            ],
            "rows": rows,
        }

    # ---------------------------------------------------------
    # UNSUPPORTED REPORT
    # ---------------------------------------------------------

    raise ValueError(
        f"Unsupported report type: {report_type}"
    )


# =============================================================
# CSV EXPORT
# =============================================================

def export_report_csv(report_data: dict) -> bytes:

    buf = io.StringIO()

    writer = csv.DictWriter(
        buf,
        fieldnames=report_data["columns"],
    )

    writer.writeheader()

    for row in report_data["rows"]:

        writer.writerow(
            {
                col: row.get(col, "")
                for col in report_data["columns"]
            }
        )

    return buf.getvalue().encode("utf-8-sig")


# =============================================================
# EXCEL EXPORT
# =============================================================

def export_report_excel(report_data: dict) -> bytes:

    wb = Workbook()

    ws = wb.active
    ws.title = report_data["report_type"][:30]

    ws.append([report_data["title"]])

    ws["A1"].font = Font(
        bold=True,
        size=13,
    )

    ws.append([])

    headers = [
        col.replace("_", " ").title()
        for col in report_data["columns"]
    ]

    ws.append(headers)

    header_row = ws.max_row

    fill = PatternFill(
        start_color="B45309",
        end_color="B45309",
        fill_type="solid",
    )

    for cell in ws[header_row]:

        cell.font = Font(
            bold=True,
            color="FFFFFF",
        )

        cell.fill = fill

    for row in report_data["rows"]:

        ws.append(
            [
                row.get(col, "")
                for col in report_data["columns"]
            ]
        )

    for col in ws.columns:

        max_len = max(
            (
                len(str(c.value or ""))
                for c in col
            ),
            default=12,
        )

        ws.column_dimensions[
            col[0].column_letter
        ].width = min(max_len + 4, 40)

    out = io.BytesIO()

    wb.save(out)

    return out.getvalue()