from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, Field
from app.schemas.common import ORMModel


class OrderItemCreate(BaseModel):
    product_id: int
    quantity: Decimal = Field(..., gt=0)
    unit_price: Decimal | None = Field(default=None, gt=0)


class OrderCreate(BaseModel):
    customer_id: int
    order_date: date | None = None
    notes: str | None = None
    idempotency_key: str | None = None
    offline_created_at: datetime | None = None
    items: list[OrderItemCreate] = Field(..., min_length=1)


class OrderUpdate(BaseModel):
    notes: str | None = None
    items: list[OrderItemCreate] = Field(..., min_length=1)


class OrderRejectRequest(BaseModel):
    reason: str = Field(..., min_length=2, max_length=500)


class OrderItemRead(ORMModel):
    id: int
    product_id: int
    product_name: str | None = None
    quantity: Decimal
    unit_price: Decimal
    gst_rate: Decimal
    line_subtotal: Decimal
    available_stock: Decimal | None = None
    shortage_qty: Decimal | None = None


class OrderRead(ORMModel):
    id: int
    order_number: str
    customer_id: int
    customer_name: str | None = None
    customer_state: str | None = None
    salesman_id: int
    salesman_name: str | None = None
    order_date: date
    status: str
    subtotal: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    notes: str | None
    rejection_reason: str | None
    idempotency_key: str | None
    approved_at: datetime | None
    invoiced_at: datetime | None
    dispatched_at: datetime | None
    created_at: datetime
    items: list[OrderItemRead] = []
    invoice_id: int | None = None
    invoice_number: str | None = None


class InvoiceItemRead(ORMModel):
    id: int
    product_id: int
    product_name: str
    hsn_code: str
    quantity: Decimal
    unit_price: Decimal
    taxable_value: Decimal
    gst_rate: Decimal
    cgst_rate: Decimal
    cgst_amount: Decimal
    sgst_rate: Decimal
    sgst_amount: Decimal
    igst_rate: Decimal
    igst_amount: Decimal
    total_amount: Decimal


class InvoiceRead(ORMModel):
    id: int
    invoice_number: str
    financial_year: str
    order_id: int
    customer_id: int
    invoice_date: date
    seller_name: str
    seller_gstin: str
    seller_address: str
    seller_state: str
    buyer_name: str
    buyer_gstin: str | None
    buyer_address: str
    buyer_state: str
    place_of_supply: str
    tax_type: str
    taxable_value: Decimal
    cgst_amount: Decimal
    sgst_amount: Decimal
    igst_amount: Decimal
    total_tax: Decimal
    grand_total: Decimal
    status: str
    dispatch_status: str
    dispatched_at: datetime | None
    created_at: datetime
    paid_amount: Decimal = Decimal("0.00")
    outstanding_amount: Decimal = Decimal("0.00")
    items: list[InvoiceItemRead] = []


class CreditNoteCreate(BaseModel):
    invoice_id: int
    credit_note_date: date | None = None
    reason: str = Field(..., min_length=3, max_length=500)
    taxable_value: Decimal | None = Field(default=None, gt=0)


class CreditNoteRead(ORMModel):
    id: int
    credit_note_number: str
    financial_year: str
    invoice_id: int
    invoice_number: str | None = None
    customer_id: int
    customer_name: str | None = None
    credit_note_date: date
    reason: str
    taxable_value: Decimal
    cgst_amount: Decimal
    sgst_amount: Decimal
    igst_amount: Decimal
    total_amount: Decimal
    status: str
    created_at: datetime


class SalesReturnCreate(BaseModel):
    invoice_id: int
    product_id: int
    credit_note_id: int | None = None
    return_date: date | None = None
    returned_qty: Decimal = Field(..., gt=0)
    usable_qty: Decimal = Field(..., ge=0)
    damaged_qty: Decimal = Field(..., ge=0)
    remarks: str | None = None


class SalesReturnRead(ORMModel):
    id: int
    return_number: str
    credit_note_id: int | None
    invoice_id: int
    customer_id: int
    product_id: int
    product_name: str | None = None
    return_date: date
    returned_qty: Decimal
    usable_qty: Decimal
    damaged_qty: Decimal
    inspection_status: str
    stock_restored: bool
    remarks: str | None
    created_at: datetime


class PaymentCreate(BaseModel):
    customer_id: int
    invoice_id: int
    payment_date: date | None = None
    amount: Decimal = Field(..., gt=0)
    payment_method: str = Field(..., pattern="^(cash|upi|neft|rtgs|cheque|bank_transfer)$")
    reference_number: str | None = None
    notes: str | None = None
    idempotency_key: str | None = None


class PaymentRead(ORMModel):
    id: int
    payment_number: str
    customer_id: int
    customer_name: str | None = None
    invoice_id: int
    invoice_number: str | None = None
    payment_date: date
    amount: Decimal
    payment_method: str
    reference_number: str | None
    notes: str | None
    created_at: datetime
