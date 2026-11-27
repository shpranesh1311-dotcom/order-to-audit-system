from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field
from app.schemas.common import ORMModel


class BomItemCreate(BaseModel):
    material_id: int
    quantity: Decimal = Field(..., gt=0)
    unit: str = Field(..., min_length=1, max_length=24)


class BomCreate(BaseModel):
    product_id: int
    name: str = Field(..., min_length=2, max_length=160)
    expected_output_qty: Decimal = Field(..., gt=0)
    notes: str | None = None
    items: list[BomItemCreate] = Field(..., min_length=1)


class BomItemRead(ORMModel):
    id: int
    material_id: int
    material_name: str | None = None
    material_type: str | None = None
    quantity: Decimal
    unit: str


class BomRead(ORMModel):
    id: int
    product_id: int
    product_name: str | None = None
    version: int
    name: str
    expected_output_qty: Decimal
    is_active: bool
    notes: str | None
    created_at: datetime
    items: list[BomItemRead]


class BomPlannedLine(BaseModel):
    material_id: int
    material_name: str
    material_type: str
    planned_qty: Decimal
    unit: str
    available_stock: Decimal
    avg_rate: Decimal


class BomPlanResponse(BaseModel):
    bom_id: int
    product_id: int
    product_name: str
    version: int
    batches: Decimal
    expected_output_qty: Decimal
    items: list[BomPlannedLine]
