from datetime import date
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from app.core.database import get_db
from app.core.permissions import UserRole, require_roles
from app.models.sales import CreditNote, Invoice, SalesReturn
from app.models.user import User
from app.schemas.sales import (
    CreditNoteCreate,
    CreditNoteRead,
    InvoiceItemRead,
    InvoiceRead,
    SalesReturnCreate,
    SalesReturnRead,
)
from app.services.invoice_service import (
    create_credit_note,
    dispatch_invoice,
    generate_invoice_for_order,
    get_invoice,
    record_sales_return,
)
from app.services.payment_service import get_invoice_outstanding
from app.utils.pdf_generator import generate_invoice_pdf

router = APIRouter(prefix="/api/invoices", tags=["GST Billing & Returns"])


def _to_invoice_read(db: Session, inv: Invoice) -> InvoiceRead:
    paid, outstanding = get_invoice_outstanding(db, inv)
    return InvoiceRead(
        id=inv.id,
        invoice_number=inv.invoice_number,
        financial_year=inv.financial_year,
        order_id=inv.order_id,
        customer_id=inv.customer_id,
        invoice_date=inv.invoice_date,
        seller_name=inv.seller_name,
        seller_gstin=inv.seller_gstin,
        seller_address=inv.seller_address,
        seller_state=inv.seller_state,
        buyer_name=inv.buyer_name,
        buyer_gstin=inv.buyer_gstin,
        buyer_address=inv.buyer_address,
        buyer_state=inv.buyer_state,
        place_of_supply=inv.place_of_supply,
        tax_type=inv.tax_type,
        taxable_value=inv.taxable_value,
        cgst_amount=inv.cgst_amount,
        sgst_amount=inv.sgst_amount,
        igst_amount=inv.igst_amount,
        total_tax=inv.total_tax,
        grand_total=inv.grand_total,
        status=inv.status,
        dispatch_status=inv.dispatch_status,
        dispatched_at=inv.dispatched_at,
        created_at=inv.created_at,
        paid_amount=paid,
        outstanding_amount=outstanding,
        items=[InvoiceItemRead.model_validate(it) for it in inv.items],
    )


@router.get("", response_model=list[InvoiceRead], summary="List GST invoices")
def list_invoices(
    customer_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN, UserRole.ACCOUNTANT, UserRole.OWNER)),
):
    stmt = (
        select(Invoice)
        .options(joinedload(Invoice.items), joinedload(Invoice.payments))
        .order_by(Invoice.invoice_date.desc(), Invoice.id.desc())
    )
    if customer_id is not None:
        stmt = stmt.where(Invoice.customer_id == customer_id)
    invoices = db.execute(stmt).unique().scalars().all()
    return [_to_invoice_read(db, inv) for inv in invoices]


@router.get("/credit-notes", response_model=list[CreditNoteRead], summary="List credit notes")
def list_credit_notes(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN, UserRole.ACCOUNTANT, UserRole.OWNER)),
):
    rows = (
        db.execute(
            select(CreditNote)
            .options(joinedload(CreditNote.invoice), joinedload(CreditNote.customer))
            .order_by(CreditNote.id.desc())
        )
        .scalars()
        .all()
    )
    return [
        CreditNoteRead(
            id=cn.id,
            credit_note_number=cn.credit_note_number,
            financial_year=cn.financial_year,
            invoice_id=cn.invoice_id,
            invoice_number=cn.invoice.invoice_number if cn.invoice else None,
            customer_id=cn.customer_id,
            customer_name=cn.customer.name if cn.customer else None,
            credit_note_date=cn.credit_note_date,
            reason=cn.reason,
            taxable_value=cn.taxable_value,
            cgst_amount=cn.cgst_amount,
            sgst_amount=cn.sgst_amount,
            igst_amount=cn.igst_amount,
            total_amount=cn.total_amount,
            status=cn.status,
            created_at=cn.created_at,
        )
        for cn in rows
    ]


@router.post("/credit-notes", response_model=CreditNoteRead, status_code=status.HTTP_201_CREATED, summary="Create accounting credit note (does not touch physical stock)")
def create_credit_note_endpoint(
    payload: CreditNoteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    cn = create_credit_note(db, payload, current_user)
    return CreditNoteRead(
        id=cn.id,
        credit_note_number=cn.credit_note_number,
        financial_year=cn.financial_year,
        invoice_id=cn.invoice_id,
        invoice_number=cn.invoice.invoice_number if cn.invoice else None,
        customer_id=cn.customer_id,
        customer_name=cn.customer.name if cn.customer else None,
        credit_note_date=cn.credit_note_date,
        reason=cn.reason,
        taxable_value=cn.taxable_value,
        cgst_amount=cn.cgst_amount,
        sgst_amount=cn.sgst_amount,
        igst_amount=cn.igst_amount,
        total_amount=cn.total_amount,
        status=cn.status,
        created_at=cn.created_at,
    )


@router.get("/sales-returns", response_model=list[SalesReturnRead], summary="List physical sales returns")
def list_sales_returns(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN, UserRole.ACCOUNTANT, UserRole.OWNER)),
):
    rows = (
        db.execute(
            select(SalesReturn).options(joinedload(SalesReturn.product)).order_by(SalesReturn.id.desc())
        )
        .scalars()
        .all()
    )
    return [
        SalesReturnRead(
            id=r.id,
            return_number=r.return_number,
            credit_note_id=r.credit_note_id,
            invoice_id=r.invoice_id,
            customer_id=r.customer_id,
            product_id=r.product_id,
            product_name=r.product.name if r.product else None,
            return_date=r.return_date,
            returned_qty=r.returned_qty,
            usable_qty=r.usable_qty,
            damaged_qty=r.damaged_qty,
            inspection_status=r.inspection_status,
            stock_restored=r.stock_restored,
            remarks=r.remarks,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.post("/sales-returns", response_model=SalesReturnRead, status_code=status.HTTP_201_CREATED, summary="Record inspected physical sales return")
def create_sales_return_endpoint(
    payload: SalesReturnCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    r = record_sales_return(db, payload, current_user)
    return SalesReturnRead(
        id=r.id,
        return_number=r.return_number,
        credit_note_id=r.credit_note_id,
        invoice_id=r.invoice_id,
        customer_id=r.customer_id,
        product_id=r.product_id,
        product_name=r.product.name if r.product else None,
        return_date=r.return_date,
        returned_qty=r.returned_qty,
        usable_qty=r.usable_qty,
        damaged_qty=r.damaged_qty,
        inspection_status=r.inspection_status,
        stock_restored=r.stock_restored,
        remarks=r.remarks,
        created_at=r.created_at,
    )


@router.get("/{invoice_id}", response_model=InvoiceRead, summary="Get GST invoice detail")
def read_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN, UserRole.ACCOUNTANT, UserRole.OWNER)),
):
    return _to_invoice_read(db, get_invoice(db, invoice_id))


@router.post("/from-order/{order_id}", response_model=InvoiceRead, status_code=status.HTTP_201_CREATED, summary="Generate GST invoice from approved order (Admin)")
def generate_invoice_endpoint(
    order_id: int,
    invoice_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    inv = generate_invoice_for_order(db, order_id, current_user, invoice_date=invoice_date)
    return _to_invoice_read(db, inv)


@router.post("/{invoice_id}/dispatch", response_model=InvoiceRead, summary="Record dispatch & deduct finished goods stock (Admin)")
def dispatch_invoice_endpoint(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    inv = dispatch_invoice(db, invoice_id, current_user)
    return _to_invoice_read(db, inv)


@router.get("/{invoice_id}/pdf", summary="Download GST Tax Invoice PDF")
def download_invoice_pdf(
    invoice_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN, UserRole.ACCOUNTANT, UserRole.OWNER)),
):
    inv = get_invoice(db, invoice_id)
    pdf_bytes = generate_invoice_pdf(inv)
    safe_name = inv.invoice_number.replace("/", "-")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.pdf"'},
    )
