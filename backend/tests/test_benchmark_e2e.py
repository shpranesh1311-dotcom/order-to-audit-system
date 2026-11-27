"""
Mandatory Section 15 & Section 16 End-to-End Benchmark Test.

Executes all 9 benchmark operations through real FastAPI routes and PostgreSQL
transactions and verifies every expected inventory, variance, GST, shortage,
payment, costing, and report output.
"""

from datetime import date
from decimal import Decimal
from tests.conftest import auth_headers


def test_mandatory_benchmark_end_to_end(client):
    prod_hdrs = auth_headers(client, "production")
    admin_hdrs = auth_headers(client, "admin")
    sales_a_hdrs = auth_headers(client, "salesman_a")
    sales_b_hdrs = auth_headers(client, "salesman_b")
    acct_hdrs = auth_headers(client, "accountant")
    owner_hdrs = auth_headers(client, "owner")

    # Fetch benchmark master records
    suppliers = client.get("/api/suppliers", headers=prod_hdrs).json()
    flour_supplier = next(s for s in suppliers if "Flour" in s["name"])

    materials = {m["code"]: m for m in client.get("/api/materials", headers=prod_hdrs).json()}
    flour = materials["RM-FLOUR"]
    oil = materials["RM-OIL"]
    spice = materials["RM-SPICE"]

    products = {p["code"]: p for p in client.get("/api/products", headers=admin_hdrs).json()}
    mur200 = products["FG-MUR-200"]
    assert Decimal(mur200["physical_stock"]) == Decimal("50.0000")

    boms = client.get(f"/api/bom?product_id={mur200['id']}", headers=prod_hdrs).json()
    bom_v1 = boms[0]

    customers_all = client.get("/api/customers", headers=admin_hdrs).json()
    retailer_a = next(c for c in customers_all if c["name"] == "Retailer A")
    distributor_b = next(c for c in customers_all if c["name"] == "Distributor B")

    # ------------------------------------------------------------------
    # Step 1: Purchase 60 kg flour at Rs 45/kg
    # ------------------------------------------------------------------
    pur_resp = client.post(
        "/api/purchases",
        headers=prod_hdrs,
        json={
            "supplier_id": flour_supplier["id"],
            "material_id": flour["id"],
            "invoice_number": "KAF-2026-101",
            "purchase_date": date(2026, 11, 26).isoformat(),
            "quantity": "60",
            "unit": "kg",
            "unit_rate": "45.00",
        },
    )
    assert pur_resp.status_code == 201, pur_resp.text

    mats_after_pur = {m["code"]: m for m in client.get("/api/materials", headers=prod_hdrs).json()}
    assert Decimal(mats_after_pur["RM-FLOUR"]["current_stock"]) == Decimal("160.0000")
    assert Decimal(mats_after_pur["RM-FLOUR"]["current_avg_rate"]) == Decimal("43.125000")

    # ------------------------------------------------------------------
    # Step 2 & 3: Production Run (1 batch Murukku 200 g)
    # Issue: Flour 40 kg, Oil 10.5 L, Spice 1.2 kg
    # Output: Good 188 packets, Damaged pouches 6, Cartons 9
    # ------------------------------------------------------------------
    run_resp = client.post(
        "/api/production/runs",
        headers=prod_hdrs,
        json={
            "product_id": mur200["id"],
            "bom_id": bom_v1["id"],
            "run_date": date(2026, 11, 26).isoformat(),
            "batches": "1",
            "raw_consumptions": [
                {"material_id": flour["id"], "actual_qty": "40"},
                {"material_id": oil["id"], "actual_qty": "10.5"},
                {"material_id": spice["id"], "actual_qty": "1.2"},
            ],
            "actual_good_packets": "188",
            "damaged_pouches": "6",
            "wastage_qty": "0",
            "actual_cartons_used": "9",
        },
    )
    assert run_resp.status_code == 201, run_resp.text
    run_data = run_resp.json()
    run_id = run_data["id"]

    # Verify inventory closing balances after production
    mats_after_prod = {m["code"]: m for m in client.get("/api/materials", headers=prod_hdrs).json()}
    assert Decimal(mats_after_prod["RM-FLOUR"]["current_stock"]) == Decimal("120.0000")
    assert Decimal(mats_after_prod["RM-OIL"]["current_stock"]) == Decimal("19.5000")
    assert Decimal(mats_after_prod["RM-SPICE"]["current_stock"]) == Decimal("3.8000")
    assert Decimal(mats_after_prod["PM-POUCH-200"]["current_stock"]) == Decimal("306.0000")
    assert Decimal(mats_after_prod["PM-CARTON"]["current_stock"]) == Decimal("21.0000")

    prods_after_prod = {p["code"]: p for p in client.get("/api/products", headers=admin_hdrs).json()}
    assert Decimal(prods_after_prod["FG-MUR-200"]["physical_stock"]) == Decimal("238.0000")

    # Verify Variances
    assert Decimal(run_data["expected_output"]) == Decimal("200.0000")
    assert Decimal(run_data["actual_good_packets"]) == Decimal("188.0000")
    assert Decimal(run_data["yield_variance_pct"]) == Decimal("-6.00")
    assert run_data["yield_flagged"] is True

    cons_by_name = {c["material_name"]: c for c in run_data["consumptions"]}
    assert Decimal(cons_by_name["Cooking oil"]["variance_pct"]) == Decimal("5.00")
    assert cons_by_name["Cooking oil"]["is_flagged"] is True

    assert Decimal(cons_by_name["Carton"]["variance_pct"]) == Decimal("-10.00")
    assert cons_by_name["Carton"]["is_flagged"] is True

    assert Decimal(cons_by_name["200 g pouch"]["actual_qty"]) == Decimal("194.0000")
    assert Decimal(cons_by_name["200 g pouch"]["variance_pct"]) == Decimal("-3.00")
    assert cons_by_name["200 g pouch"]["is_flagged"] is False

    # ------------------------------------------------------------------
    # Step 4: Salesman A Order for Retailer A (150 packets)
    # ------------------------------------------------------------------
    ord_a_resp = client.post(
        "/api/orders",
        headers=sales_a_hdrs,
        json={
            "customer_id": retailer_a["id"],
            "order_date": date(2026, 11, 26).isoformat(),
            "idempotency_key": "bench-order-retailer-a",
            "items": [{"product_id": mur200["id"], "quantity": "150"}],
        },
    )
    assert ord_a_resp.status_code == 201, ord_a_resp.text
    order_a_id = ord_a_resp.json()["id"]

    # ------------------------------------------------------------------
    # Step 5: Admin Approval, GST Invoice (CGST + SGST), and Dispatch
    # ------------------------------------------------------------------
    assert client.post(f"/api/orders/{order_a_id}/approve", headers=admin_hdrs).status_code == 200
    inv_a_resp = client.post(
        f"/api/invoices/from-order/{order_a_id}?invoice_date=2026-11-26",
        headers=admin_hdrs,
    )
    assert inv_a_resp.status_code == 201, inv_a_resp.text
    inv_a = inv_a_resp.json()
    assert inv_a["invoice_number"] == "INV/2026-27/0001"
    assert inv_a["tax_type"] == "CGST_SGST"
    assert Decimal(inv_a["taxable_value"]) == Decimal("7500.00")
    assert Decimal(inv_a["cgst_amount"]) == Decimal("187.50")
    assert Decimal(inv_a["sgst_amount"]) == Decimal("187.50")
    assert Decimal(inv_a["igst_amount"]) == Decimal("0.00")
    assert Decimal(inv_a["grand_total"]) == Decimal("7875.00")

    # Download Invoice PDF
    pdf_resp = client.get(f"/api/invoices/{inv_a['id']}/pdf", headers=admin_hdrs)
    assert pdf_resp.status_code == 200
    assert pdf_resp.content[:4] == b"%PDF"

    # Dispatch Retailer A order
    disp_resp = client.post(f"/api/invoices/{inv_a['id']}/dispatch", headers=admin_hdrs)
    assert disp_resp.status_code == 200
    assert disp_resp.json()["dispatch_status"] == "dispatched"

    prods_after_disp = {p["code"]: p for p in client.get("/api/products", headers=admin_hdrs).json()}
    assert Decimal(prods_after_disp["FG-MUR-200"]["physical_stock"]) == Decimal("88.0000")
    assert Decimal(prods_after_disp["FG-MUR-200"]["available_stock"]) == Decimal("88.0000")

    # ------------------------------------------------------------------
    # Step 6: Salesman B Order for Distributor B (120 packets) -> Blocked!
    # ------------------------------------------------------------------
    ord_b_resp = client.post(
        "/api/orders",
        headers=sales_b_hdrs,
        json={
            "customer_id": distributor_b["id"],
            "order_date": date(2026, 11, 26).isoformat(),
            "items": [{"product_id": mur200["id"], "quantity": "120"}],
        },
    )
    assert ord_b_resp.status_code == 201
    order_b = ord_b_resp.json()
    assert Decimal(order_b["items"][0]["available_stock"]) == Decimal("88.0000")
    assert Decimal(order_b["items"][0]["shortage_qty"]) == Decimal("32.0000")

    approve_b = client.post(f"/api/orders/{order_b['id']}/approve", headers=admin_hdrs)
    assert approve_b.status_code == 409
    shortage_info = approve_b.json()["detail"]["shortages"][0]
    assert Decimal(shortage_info["requested"]) == Decimal("120.0000")
    assert Decimal(shortage_info["available"]) == Decimal("88.0000")
    assert Decimal(shortage_info["shortage"]) == Decimal("32.0000")

    # ------------------------------------------------------------------
    # Step 7: Payment of Rs 4,000 from Retailer A -> Outstanding Rs 3,875
    # ------------------------------------------------------------------
    pay_resp = client.post(
        "/api/payments",
        headers=admin_hdrs,
        json={
            "customer_id": retailer_a["id"],
            "invoice_id": inv_a["id"],
            "payment_date": date(2026, 11, 26).isoformat(),
            "amount": "4000.00",
            "payment_method": "neft",
            "reference_number": "NEFT-TRCH-9081",
        },
    )
    assert pay_resp.status_code == 201
    inv_a_after_pay = client.get(f"/api/invoices/{inv_a['id']}", headers=admin_hdrs).json()
    assert Decimal(inv_a_after_pay["paid_amount"]) == Decimal("4000.00")
    assert Decimal(inv_a_after_pay["outstanding_amount"]) == Decimal("3875.00")

    # ------------------------------------------------------------------
    # Step 8: Production Overheads (Labour 1,200 + Gas/power 600)
    # Total Cost = 5,855; Cost per packet = 5,855 / 188 = 31.14
    # ------------------------------------------------------------------
    ovh_resp = client.patch(
        f"/api/production/runs/{run_id}/overheads",
        headers=prod_hdrs,
        json={"labour_cost": "1200.00", "gas_cost": "600.00", "power_cost": "0.00"},
    )
    assert ovh_resp.status_code == 200, ovh_resp.text
    cost_breakdown = client.get(f"/api/costing/runs/{run_id}", headers=owner_hdrs).json()
    assert Decimal(cost_breakdown["raw_material_cost"]) == Decimal("3435.00")  # 1725 + 1470 + 240
    assert Decimal(cost_breakdown["packaging_cost"]) == Decimal("620.00")      # 485 + 135
    assert Decimal(cost_breakdown["labour_cost"]) == Decimal("1200.00")
    assert Decimal(cost_breakdown["gas_cost"]) == Decimal("600.00")
    assert Decimal(cost_breakdown["total_production_cost"]) == Decimal("5855.00")
    assert Decimal(cost_breakdown["cost_per_packet"]) == Decimal("31.14")

    # ------------------------------------------------------------------
    # Step 9: Monthly Reports & Exports (JSON, CSV, Excel, PDF)
    # ------------------------------------------------------------------
    for rtype in [
        "sales_register",
        "sales_by_customer",
        "sales_by_product",
        "sales_by_salesman",
        "gst_summary",
        "purchase_register",
        "purchases_by_supplier",
        "purchases_by_material",
        "inventory_summary",
        "production_variance",
        "costing_summary",
        "payment_register",
        "receivables_ageing",
    ]:
        r_json = client.get(f"/api/reports/{rtype}", headers=acct_hdrs)
        assert r_json.status_code == 200, f"Report {rtype} failed: {r_json.text}"

    # Verify exports work
    assert client.get("/api/reports/gst_summary?export=csv", headers=acct_hdrs).status_code == 200
    xlsx = client.get("/api/reports/costing_summary?export=excel", headers=acct_hdrs)
    assert xlsx.status_code == 200
    assert len(xlsx.content) > 100
    pdf = client.get("/api/reports/sales_register?export=pdf", headers=acct_hdrs)
    assert pdf.status_code == 200
    assert pdf.content[:4] == b"%PDF"

    # Verify Reconciliation & Audit Trail & Owner Dashboard
    rec = client.get("/api/inventory/reconcile", headers=acct_hdrs).json()
    assert rec["is_fully_consistent"] is True

    audit_entries = client.get("/api/audit", headers=acct_hdrs).json()
    assert len(audit_entries) >= 6

    dash = client.get("/api/dashboard/owner", headers=owner_hdrs).json()
    assert Decimal(dash["kpis"]["outstanding_dues"]) == Decimal("3875.00")
    assert Decimal(dash["kpis"]["total_sales"]) == Decimal("7875.00")
