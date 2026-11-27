from tests.conftest import auth_headers


def test_all_demo_roles_can_login(client):
    for uname, expected_role in [
        ("salesman_a", "salesman"),
        ("salesman_b", "salesman"),
        ("admin", "admin"),
        ("production", "production"),
        ("accountant", "accountant"),
        ("owner", "owner"),
    ]:
        resp = client.post("/api/auth/login", json={"username": uname, "password": "demo123"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["user"]["role"] == expected_role
        assert body["access_token"]


def test_invalid_login_and_unauthenticated(client):
    bad = client.post("/api/auth/login", json={"username": "admin", "password": "wrongpassword"})
    assert bad.status_code == 401

    unauth = client.get("/api/orders")
    assert unauth.status_code == 401


def test_rbac_restrictions(client):
    sales_hdrs = auth_headers(client, "salesman_a")
    acct_hdrs = auth_headers(client, "accountant")
    prod_hdrs = auth_headers(client, "production")

    # Salesman cannot access production, purchases, or reports
    assert client.get("/api/materials", headers=sales_hdrs).status_code == 403
    assert client.get("/api/production/runs", headers=sales_hdrs).status_code == 403
    assert client.get("/api/reports/sales_register", headers=sales_hdrs).status_code == 403

    # Accountant is strictly read-only
    assert client.get("/api/reports/sales_register", headers=acct_hdrs).status_code == 200
    assert client.get("/api/audit", headers=acct_hdrs).status_code == 200
    assert (
        client.post(
            "/api/customers",
            headers=acct_hdrs,
            json={
                "name": "Unauthorized Cust",
                "customer_type": "retailer",
                "state": "Tamil Nadu",
                "address": "Test Street",
                "contact_number": "9999999999",
            },
        ).status_code
        == 403
    )

    # Production cannot approve orders or record payments
    assert client.post("/api/orders/1/approve", headers=prod_hdrs).status_code == 403
    assert client.get("/api/payments", headers=prod_hdrs).status_code == 403
