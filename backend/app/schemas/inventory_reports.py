from datetime import date, datetime
from decimal import Decimal
from typing import Any
from pydantic import BaseModel
from app.schemas.common import ORMModel


class StockLedgerRead(ORMModel):
    id: int
    item_category: str
    material_id: int | None
    product_id: int | None
    item_name: str | None = None
    transaction_type: str
    direction: str
    quantity: Decimal
    signed_quantity: Decimal
    unit: str
    rate: Decimal
    total_value: Decimal
    batch_number: str | None
    expiry_date: date | None
    source_doc_type: str
    source_doc_id: int
    source_doc_ref: str | None
    remarks: str | None
    created_at: datetime


class StockAdjustmentCreate(BaseModel):
    item_category: str
    material_id: int | None = None
    product_id: int | None = None
    direction: str
    quantity: Decimal
    remarks: str


class AuditLogRead(ORMModel):
    id: int
    user_id: int | None
    username: str
    role: str
    action: str
    entity_type: str
    entity_id: str
    previous_values: dict[str, Any] | None
    updated_values: dict[str, Any] | None
    remarks: str | None
    created_at: datetime
