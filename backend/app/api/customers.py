from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.audit import log_audit
from app.core.database import get_db
from app.core.permissions import UserRole, require_roles
from app.models.master import Customer
from app.models.user import User
from app.schemas.master import CustomerCreate, CustomerRead, CustomerUpdate

router = APIRouter(prefix="/api/customers", tags=["Customers"])


@router.get("", response_model=list[CustomerRead], summary="List customers (Salesmen see assigned customers)")
def list_customers(
    search: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.SALESMAN, UserRole.ADMIN, UserRole.ACCOUNTANT, UserRole.OWNER)
    ),
):
    stmt = select(Customer).order_by(Customer.name)
    if current_user.role == UserRole.SALESMAN.value:
        stmt = stmt.where(Customer.is_active.is_(True))
        stmt = stmt.where(
            (Customer.assigned_salesman_id == current_user.id) | (Customer.assigned_salesman_id.is_(None))
        )
    if search:
        like = f"%{search.strip()}%"
        stmt = stmt.where(Customer.name.ilike(like) | Customer.state.ilike(like))
    return db.execute(stmt).scalars().all()


@router.post("", response_model=CustomerRead, status_code=status.HTTP_201_CREATED, summary="Create customer (Admin)")
def create_customer(
    payload: CustomerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    cust = Customer(**payload.model_dump(), is_active=True)
    db.add(cust)
    db.flush()
    log_audit(
        db,
        user_id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        action="CREATE",
        entity_type="customer",
        entity_id=cust.id,
        updated_values={"name": cust.name, "state": cust.state, "customer_type": cust.customer_type},
    )
    db.commit()
    db.refresh(cust)
    return cust


@router.patch("/{customer_id}", response_model=CustomerRead, summary="Update customer (Admin)")
def update_customer(
    customer_id: int,
    payload: CustomerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    cust = db.get(Customer, customer_id)
    if not cust:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    updates = payload.model_dump(exclude_unset=True)
    prev = {k: getattr(cust, k) for k in updates}
    for field, val in updates.items():
        setattr(cust, field, val)
    log_audit(
        db,
        user_id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        action="EDIT",
        entity_type="customer",
        entity_id=cust.id,
        previous_values=prev,
        updated_values=updates,
    )
    db.commit()
    db.refresh(cust)
    return cust
