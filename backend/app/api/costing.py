from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.permissions import UserRole, require_roles
from app.models.user import User
from app.services.costing_service import get_product_costing_summary, get_production_cost_breakdown

router = APIRouter(prefix="/api/costing", tags=["Product Costing & Margins"])


@router.get("/products", summary="Product-wise cost per packet & margin analysis")
def product_costing(
    db: Session = Depends(get_db),
    _: User = Depends(
        require_roles(UserRole.ADMIN, UserRole.PRODUCTION, UserRole.ACCOUNTANT, UserRole.OWNER)
    ),
):
    return get_product_costing_summary(db)


@router.get("/runs/{run_id}", summary="Detailed cost breakdown for a production run")
def run_cost_breakdown(
    run_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(
        require_roles(UserRole.ADMIN, UserRole.PRODUCTION, UserRole.ACCOUNTANT, UserRole.OWNER)
    ),
):
    data = get_production_cost_breakdown(db, run_id)
    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Production run not found")
    return data
