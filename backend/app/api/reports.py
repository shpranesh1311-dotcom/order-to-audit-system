from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import UserRole, require_roles
from app.models.user import User
from app.services.report_service import (
    build_report,
    export_report_csv,
    export_report_excel,
)
from app.utils.pdf_generator import generate_report_pdf


router = APIRouter(
    prefix="/api/reports",
    tags=["Monthly Accounting & Audit Reports"],
)


SUPPORTED_REPORTS = {
    # Frontend report options
    "sales_register",
    "purchase_register",
    "gst_summary",
    "gst_sales_detail",
    "gst_purchase_detail",
    "inventory_summary",
    "stock_ledger",
    "production_report",
    "costing_report",
    "payment_collection",
    "outstanding_balances",
    "variance_analysis",
    "profit_loss_summary",

    # Existing service report names
    "sales_by_customer",
    "sales_by_product",
    "sales_by_salesman",
    "purchases_by_supplier",
    "purchases_by_material",
    "production_variance",
    "costing_summary",
    "payment_register",
    "receivables_ageing",
}


@router.get(
    "/{report_type}",
    summary="Generate live PostgreSQL report (JSON, CSV, Excel, or PDF)",
)
def get_report(
    report_type: str,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    material_id: int | None = Query(default=None, ge=1),
    export: str | None = Query(
        default=None,
        pattern="^(csv|excel|pdf)$",
    ),
    db: Session = Depends(get_db),
    _: User = Depends(
        require_roles(
            UserRole.ADMIN,
            UserRole.ACCOUNTANT,
            UserRole.OWNER,
            UserRole.PRODUCTION,
        )
    ),
):
    if report_type not in SUPPORTED_REPORTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unknown report_type '{report_type}'. "
                f"Supported: {sorted(SUPPORTED_REPORTS)}"
            ),
        )

    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date cannot be later than end_date.",
        )

    data = build_report(
        db,
        report_type,
        start_date=start_date,
        end_date=end_date,
        material_id=material_id,
    )

    if export == "csv":
        content = export_report_csv(data)
        return Response(
            content=content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{report_type}.csv"'
            },
        )

    if export == "excel":
        content = export_report_excel(data)
        return Response(
            content=content,
            media_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
            headers={
                "Content-Disposition": f'attachment; filename="{report_type}.xlsx"'
            },
        )

    if export == "pdf":
        content = generate_report_pdf(data)
        return Response(
            content=content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{report_type}.pdf"'
            },
        )

    return data