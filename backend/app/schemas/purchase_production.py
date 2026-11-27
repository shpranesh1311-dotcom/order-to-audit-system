from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, Field
from app.schemas.common import ORMModel


class PurchaseCreate(BaseModel):
    supplier_id: int
    material_id: int
    invoice_number: str = Field(..., min_length=1, max_length=80)
    purchase_date: date
    quantity: Decimal = Field(..., gt=0)
    unit: str = Field(..., min_length=1, max_length=24)
    unit_rate: Decimal = Field(..., gt=0)
    batch_number: str | None = None
    expiry_date: date | None = None
    remarks: str | None = None
    idempotency_key: str | None = None


class PurchaseRead(ORMModel):
    id: int
    purchase_number: str
    supplier_id: int
    supplier_name: str | None = None
    material_id: int
    material_name: str | None = None
    material_type: str | None = None
    invoice_number: str
    purchase_date: date
    quantity: Decimal
    unit: str
    base_quantity: Decimal
    unit_rate: Decimal
    total_amount: Decimal
    batch_number: str | None
    expiry_date: date | None
    remarks: str | None
    created_at: datetime


class ActualMaterialInput(BaseModel):
    material_id: int
    actual_qty: Decimal = Field(..., ge=0)
    unit: str | None = None


class ProductionRunCreate(BaseModel):
    product_id: int
    bom_id: int
    run_date: date | None = None
    batches: Decimal = Field(..., gt=0)
    raw_consumptions: list[ActualMaterialInput] = Field(..., min_length=1)
    actual_good_packets: Decimal = Field(..., gt=0)
    damaged_pouches: Decimal = Field(default=Decimal("0"), ge=0)
    wastage_qty: Decimal = Field(default=Decimal("0"), ge=0)
    actual_cartons_used: Decimal = Field(default=Decimal("0"), ge=0)
    labour_cost: Decimal = Field(default=Decimal("0"), ge=0)
    gas_cost: Decimal = Field(default=Decimal("0"), ge=0)
    power_cost: Decimal = Field(default=Decimal("0"), ge=0)
    other_overhead_cost: Decimal = Field(default=Decimal("0"), ge=0)
    batch_number: str | None = None
    expiry_date: date | None = None
    remarks: str | None = None


class ProductionOverheadUpdate(BaseModel):
    labour_cost: Decimal | None = Field(default=None, ge=0)
    gas_cost: Decimal | None = Field(default=None, ge=0)
    power_cost: Decimal | None = Field(default=None, ge=0)
    other_overhead_cost: Decimal | None = Field(default=None, ge=0)
    remarks: str | None = None


class ProductionConsumptionRead(ORMModel):
    id: int
    material_id: int
    material_name: str | None = None
    material_type: str
    planned_qty: Decimal
    actual_qty: Decimal
    unit: str
    variance_qty: Decimal
    variance_pct: Decimal
    is_flagged: bool
    unit_cost: Decimal
    total_cost: Decimal


class ProductionRunRead(ORMModel):
    id: int
    run_number: str
    product_id: int
    product_name: str | None = None
    bom_id: int
    bom_version: int
    run_date: date
    batches: Decimal
    expected_output: Decimal
    actual_good_packets: Decimal
    damaged_pouches: Decimal
    wastage_qty: Decimal
    actual_cartons_used: Decimal
    yield_variance_qty: Decimal
    yield_variance_pct: Decimal
    yield_flagged: bool
    tolerance_pct: Decimal
    labour_cost: Decimal
    gas_cost: Decimal
    power_cost: Decimal
    other_overhead_cost: Decimal
    raw_material_cost: Decimal
    packaging_cost: Decimal
    total_cost: Decimal
    cost_per_packet: Decimal
    batch_number: str | None
    expiry_date: date | None
    status: str
    remarks: str | None
    created_at: datetime
    consumptions: list[ProductionConsumptionRead] = []
