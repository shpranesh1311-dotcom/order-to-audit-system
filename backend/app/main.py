import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api import (
    audit,
    auth,
    bom,
    costing,
    customers,
    dashboard,
    inventory,
    invoices,
    materials,
    orders,
    payments,
    production,
    products,
    purchases,
    reports,
    suppliers,
    users,
)
from app.core.config import get_settings
from app.core.database import engine

logging.basicConfig(level=logging.INFO)
settings = get_settings()

app = FastAPI(
    title="Order-to-Audit System API",
    description="Integrated Sales, Production, Inventory, GST Billing, Costing & Audit System for South Indian Packaged Snacks Manufacturing.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in [
    auth.router,
    users.router,
    customers.router,
    suppliers.router,
    products.router,
    materials.router,
    bom.router,
    purchases.router,
    orders.router,
    invoices.router,
    production.router,
    inventory.router,
    costing.router,
    payments.router,
    reports.router,
    dashboard.router,
    audit.router,
]:
    app.include_router(router)


@app.get("/health", tags=["System"])
def health_check():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "healthy", "database": "postgresql"}
