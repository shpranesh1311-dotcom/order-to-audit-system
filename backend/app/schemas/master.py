from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, Field
from app.schemas.common import ORMModel


class ProductCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=40)
    name: str = Field(..., min_length=2, max_length=150)
    category: str = Field(..., min_length=2, max_length=80)
    description: str | None = None
    pack_size: Decimal = Field(..., gt=0)
    pack_unit: str = Field(default="g", max_length=20)
    carton_capacity: int = Field(default=20, gt=0)
    unit: str = Field(default="packet", max_length=30)
    selling_price: Decimal = Field(..., gt=0)
    hsn_code: str = Field(..., min_length=4, max_length=20)
    gst_rate: Decimal = Field(default=Decimal("5.00"), ge=0, le=28)
    reorder_level: Decimal = Field(default=Decimal("50"), ge=0)
    opening_stock: Decimal = Field(default=Decimal("0"), ge=0)
    opening_cost_rate: Decimal = Field(default=Decimal("0"), ge=0)


class ProductUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    description: str | None = None
    pack_size: Decimal | None = Field(default=None, gt=0)
    pack_unit: str | None = None
    carton_capacity: int | None = Field(default=None, gt=0)
    selling_price: Decimal | None = Field(default=None, gt=0)
    hsn_code: str | None = None
    gst_rate: Decimal | None = Field(default=None, ge=0, le=28)
    reorder_level: Decimal | None = Field(default=None, ge=0)
    is_active: bool | None = None


class ProductRead(ORMModel):
    id: int
    code: str
    name: str
    category: str
    description: str | None
    pack_size: Decimal
    pack_unit: str
    carton_capacity: int
    unit: str
    selling_price: Decimal
    hsn_code: str
    gst_rate: Decimal
    reorder_level: Decimal
    is_active: bool
    created_at: datetime
    physical_stock: Decimal = Decimal("0.0000")
    reserved_stock: Decimal = Decimal("0.0000")
    available_stock: Decimal = Decimal("0.0000")


class PriceListCreate(BaseModel):
    product_id: int
    customer_id: int | None = None
    price: Decimal = Field(..., gt=0)
    effective_date: date


class PriceListRead(ORMModel):
    id: int
    product_id: int
    customer_id: int | None
    price: Decimal
    effective_date: date
    created_at: datetime
    product_name: str | None = None
    customer_name: str | None = None


class CustomerCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=160)
    customer_type: str = Field(..., pattern="^(retailer|distributor)$")
    gstin: str | None = Field(default=None, max_length=20)
    state: str = Field(..., min_length=2, max_length=80)
    address: str = Field(..., min_length=4)
    contact_number: str = Field(..., min_length=6, max_length=32)
    email: str | None = None
    assigned_salesman_id: int | None = None
    credit_limit: Decimal = Field(default=Decimal("50000.00"), ge=0)
    payment_terms: str = Field(default="Net 15 Days", max_length=80)


class CustomerUpdate(BaseModel):
    name: str | None = None
    customer_type: str | None = Field(default=None, pattern="^(retailer|distributor)$")
    gstin: str | None = None
    state: str | None = None
    address: str | None = None
    contact_number: str | None = None
    email: str | None = None
    assigned_salesman_id: int | None = None
    credit_limit: Decimal | None = Field(default=None, ge=0)
    payment_terms: str | None = None
    is_active: bool | None = None


class CustomerRead(ORMModel):
    id: int
    name: str
    customer_type: str
    gstin: str | None
    state: str
    address: str
    contact_number: str
    email: str | None
    assigned_salesman_id: int | None
    credit_limit: Decimal
    payment_terms: str
    is_active: bool
    created_at: datetime


class SupplierCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=160)
    gstin: str | None = Field(default=None, max_length=20)
    address: str = Field(..., min_length=4)
    contact_number: str = Field(..., min_length=6, max_length=32)
    email: str | None = None
    state: str = Field(..., min_length=2, max_length=80)


class SupplierUpdate(BaseModel):
    name: str | None = None
    gstin: str | None = None
    address: str | None = None
    contact_number: str | None = None
    email: str | None = None
    state: str | None = None
    is_active: bool | None = None


class SupplierRead(ORMModel):
    id: int
    name: str
    gstin: str | None
    address: str
    contact_number: str
    email: str | None
    state: str
    is_active: bool
    created_at: datetime


class MaterialCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=40)
    name: str = Field(..., min_length=2, max_length=150)
    material_type: str = Field(..., pattern="^(raw|packaging)$")
    category: str = Field(..., min_length=2, max_length=80)
    base_unit: str = Field(..., min_length=1, max_length=24)
    opening_qty: Decimal = Field(default=Decimal("0"), ge=0)
    opening_rate: Decimal = Field(default=Decimal("0"), ge=0)
    reorder_level: Decimal = Field(default=Decimal("10"), ge=0)
    density_kg_per_litre: Decimal | None = Field(default=None, gt=0)


class MaterialUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    reorder_level: Decimal | None = Field(default=None, ge=0)
    density_kg_per_litre: Decimal | None = Field(default=None, gt=0)
    is_active: bool | None = None


class MaterialRead(ORMModel):
    id: int
    code: str
    name: str
    material_type: str
    category: str
    base_unit: str
    opening_qty: Decimal
    opening_rate: Decimal
    current_avg_rate: Decimal
    reorder_level: Decimal
    density_kg_per_litre: Decimal | None
    is_active: bool
    created_at: datetime
    current_stock: Decimal = Decimal("0.0000")
