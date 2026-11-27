import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core.database import Base, get_db
from app.main import app as fastapi_app
import app.models  # noqa: F401
from scripts.seed import seed_data


settings = get_settings()
TEST_DB_URL = os.getenv("TEST_DATABASE_URL", settings.TEST_DATABASE_URL)

if TEST_DB_URL.startswith("sqlite"):
    raise RuntimeError("Tests must run against PostgreSQL, not SQLite")

test_engine = create_engine(TEST_DB_URL, pool_pre_ping=True, future=True)
TestSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False, expire_on_commit=False)


def _truncate_all(db):
    tables = [
        "audit_logs",
        "payments",
        "sales_returns",
        "credit_notes",
        "invoice_items",
        "invoices",
        "invoice_sequences",
        "stock_reservations",
        "order_items",
        "orders",
        "production_consumptions",
        "production_runs",
        "purchases",
        "stock_ledger",
        "stock_balances",
        "bom_items",
        "boms",
        "price_lists",
        "materials",
        "suppliers",
        "customers",
        "products",
        "factory_settings",
        "users",
    ]
    for t in tables:
        db.execute(text(f"TRUNCATE TABLE {t} RESTART IDENTITY CASCADE"))
    db.commit()


@pytest.fixture(scope="session", autouse=True)
def setup_test_schema():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture()
def db_session():
    db = TestSessionLocal()
    try:
        _truncate_all(db)
        seed_data(db)
        yield db
    finally:
        db.close()


@pytest.fixture()
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    fastapi_app.dependency_overrides[get_db] = override_get_db
    with TestClient(fastapi_app) as c:
        yield c
    fastapi_app.dependency_overrides.clear()


def auth_headers(client: TestClient, username: str, password: str = "demo123") -> dict[str, str]:
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
