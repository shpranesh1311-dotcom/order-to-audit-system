from datetime import date
from decimal import Decimal
from tests.conftest import auth_headers


def test_insufficient_raw_material_blocks_production_atomically(client):
    prod_hdrs = auth_headers(client, "production")
    products = client.get("/api/products", headers=prod_hdrs).json()
    mur200 = next(p for p in products if p["code"] == "FG-MUR-200")
    boms = client.get(f"/api/bom?product_id={mur200['id']}", headers=prod_hdrs).json()
    bom = boms[0]
    materials = client.get("/api/materials", headers=prod_hdrs).json()
    flour = next(m for m in materials if m["code"] == "RM-FLOUR")
    oil = next(m for m in materials if m["code"] == "RM-OIL")
    spice = next(m for m in materials if m["code"] == "RM-SPICE")

    # Request 5 batches -> needs 200 kg flour, only 100 kg available
    resp = client.post(
        "/api/production/runs",
        headers=prod_hdrs,
        json={
            "product_id": mur200["id"],
            "bom_id": bom["id"],
            "batches": 5,
            "raw_consumptions": [
                {"material_id": flour["id"], "actual_qty": 200},
                {"material_id": oil["id"], "actual_qty": 50},
                {"material_id": spice["id"], "actual_qty": 6},
            ],
            "actual_good_packets": 1000,
            "damaged_pouches": 0,
            "actual_cartons_used": 50,
        },
    )
    assert resp.status_code == 409

    # Ensure zero partial deductions occurred
    materials_after = client.get("/api/materials", headers=prod_hdrs).json()
    oil_after = next(m for m in materials_after if m["code"] == "RM-OIL")
    assert Decimal(oil_after["current_stock"]) == Decimal("30.0000")


def test_credit_note_and_sales_return_inspection_separation(client):
    admin_hdrs = auth_headers(client, "admin")
    sales_hdrs = auth_headers(client, "salesman_a")

    custs = client.get("/api/customers", headers=sales_hdrs).json()
    retailer_a = next(c for c in custs if c["name"] == "Retailer A")
    prods = client.get("/api/products", headers=sales_hdrs).json()
    mur200 = next(p for p in prods if p["code"] == "FG-MUR-200")

    # Order 20 packets (opening stock 50)
    ord_resp = client.post(
        "/api/orders",
        headers=sales_hdrs,
        json={
            "customer_id": retailer_a["id"],
            "idempotency_key": "offline-key-100",
            "items": [{"product_id": mur200["id"], "quantity": 20}],
        },
    )
    assert ord_resp.status_code == 201
    order_id = ord_resp.json()["id"]

    # Duplicate offline sync with same idempotency_key must not create second order
    dup_resp = client.post(
        "/api/orders",
        headers=sales_hdrs,
        json={
            "customer_id": retailer_a["id"],
            "idempotency_key": "offline-key-100",
            "items": [{"product_id": mur200["id"], "quantity": 20}],
        },
    )
    assert dup_resp.status_code == 201
    assert dup_resp.json()["id"] == order_id

    assert client.post(f"/api/orders/{order_id}/approve", headers=admin_hdrs).status_code == 200
    inv = client.post(f"/api/invoices/from-order/{order_id}", headers=admin_hdrs).json()
    assert client.post(f"/api/invoices/{inv['id']}/dispatch", headers=admin_hdrs).status_code == 200

    # Stock is now 50 - 20 = 30
    mur_after_dispatch = next(
        p for p in client.get("/api/products", headers=admin_hdrs).json() if p["code"] == "FG-MUR-200"
    )
    assert Decimal(mur_after_dispatch["physical_stock"]) == Decimal("30.0000")

    # Create Credit Note -> must NOT change physical stock
    cn_resp = client.post(
        "/api/invoices/credit-notes",
        headers=admin_hdrs,
        json={
            "invoice_id": inv["id"],
            "reason": "Damaged transit outer box for 5 packets",
            "taxable_value": 250.00,
        },
    )
    assert cn_resp.status_code == 201
    mur_after_cn = next(
        p for p in client.get("/api/products", headers=admin_hdrs).json() if p["code"] == "FG-MUR-200"
    )
    assert Decimal(mur_after_cn["physical_stock"]) == Decimal("30.0000")

    # Physical sales return: 5 returned -> 3 usable, 2 damaged -> only 3 restored to stock
    ret_resp = client.post(
        "/api/invoices/sales-returns",
        headers=admin_hdrs,
        json={
            "invoice_id": inv["id"],
            "product_id": mur200["id"],
            "credit_note_id": cn_resp.json()["id"],
            "returned_qty": 5,
            "usable_qty": 3,
            "damaged_qty": 2,
            "remarks": "3 sealed packets restocked, 2 crushed packets scrapped",
        },
    )
    assert ret_resp.status_code == 201
    assert ret_resp.json()["stock_restored"] is True

    mur_after_ret = next(
        p for p in client.get("/api/products", headers=admin_hdrs).json() if p["code"] == "FG-MUR-200"
    )
    assert Decimal(mur_after_ret["physical_stock"]) == Decimal("33.0000")

    # Verify stock reconciliation consistency
    rec = client.get("/api/inventory/reconcile", headers=admin_hdrs).json()
    assert rec["is_fully_consistent"] is True


def test_duplicate_purchase_and_overpayment_rejected(client):
    prod_hdrs = auth_headers(client, "production")
    admin_hdrs = auth_headers(client, "admin")
    suppliers = client.get("/api/suppliers", headers=prod_hdrs).json()
    materials = client.get("/api/materials", headers=prod_hdrs).json()
    flour = next(m for m in materials if m["code"] == "RM-FLOUR")

    p1 = client.post(
        "/api/purchases",
        headers=prod_hdrs,
        json={
            "supplier_id": suppliers[0]["id"],
            "material_id": flour["id"],
            "invoice_number": "SUP-INV-001",
            "purchase_date": date.today().isoformat(),
            "quantity": 10,
            "unit": "kg",
            "unit_rate": 45,
        },
    )
    assert p1.status_code == 201

    # Duplicate supplier invoice + material rejected
    p2 = client.post(
        "/api/purchases",
        headers=prod_hdrs,
        json={
            "supplier_id": suppliers[0]["id"],
            "material_id": flour["id"],
            "invoice_number": "SUP-INV-001",
            "purchase_date": date.today().isoformat(),
            "quantity": 10,
            "unit": "kg",
            "unit_rate": 45,
        },
    )
    assert p2.status_code == 409

    # Create order & invoice to test overpayment prevention
    sales_hdrs = auth_headers(client, "salesman_a")
    custs = client.get("/api/customers", headers=sales_hdrs).json()
    retailer_a = next(c for c in custs if c["name"] == "Retailer A")
    mur200 = next(
        p for p in client.get("/api/products", headers=sales_hdrs).json() if p["code"] == "FG-MUR-200"
    )
    ord_id = client.post(
        "/api/orders",
        headers=sales_hdrs,
        json={"customer_id": retailer_a["id"], "items": [{"product_id": mur200["id"], "quantity": 10}]},
    ).json()["id"]
    client.post(f"/api/orders/{ord_id}/approve", headers=admin_hdrs)
    inv = client.post(f"/api/invoices/from-order/{ord_id}", headers=admin_hdrs).json()

    overpay = client.post(
        "/api/payments",
        headers=admin_hdrs,
        json={
            "customer_id": retailer_a["id"],
            "invoice_id": inv["id"],
            "amount": 99999.00,
            "payment_method": "upi",
        },
    )
    assert overpay.status_code == 400
