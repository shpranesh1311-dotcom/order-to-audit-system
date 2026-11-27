from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from app.core.audit import log_audit
from app.core.database import get_db
from app.core.permissions import UserRole, get_current_user, require_roles
from app.models.master import PriceList, Product
from app.models.user import User
from app.schemas.master import PriceListCreate, PriceListRead, ProductCreate, ProductRead, ProductUpdate
from app.services.order_service import resolve_product_price
from app.services.stock_service import get_fg_availability, record_stock_movement

router = APIRouter(prefix="/api/products", tags=["Products & Pricing"])


@router.get("", response_model=list[ProductRead], summary="List products with live stock & optional customer price")
def list_products(
    search: str | None = Query(default=None),
    customer_id: int | None = Query(default=None),
    active_only: bool = Query(default=False),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(Product).order_by(Product.id)
    if active_only:
        stmt = stmt.where(Product.is_active.is_(True))
    if search:
        like = f"%{search.strip()}%"
        stmt = stmt.where(Product.name.ilike(like) | Product.code.ilike(like) | Product.category.ilike(like))
    products = db.execute(stmt).scalars().all()
    today = date.today()
    out: list[ProductRead] = []
    for p in products:
        fg = get_fg_availability(db, p.id)
        item = ProductRead.model_validate(p)
        if customer_id is not None:
            item.selling_price = resolve_product_price(db, p, customer_id, today)
        item.physical_stock = fg["physical_stock"]
        item.reserved_stock = fg["reserved_stock"]
        item.available_stock = fg["available_stock"]
        out.append(item)
    return out


@router.post("", response_model=ProductRead, status_code=status.HTTP_201_CREATED, summary="Create product (Admin)")
def create_product(
    payload: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    existing = db.execute(select(Product).where(Product.code == payload.code)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Product code already exists")

    data = payload.model_dump(exclude={"opening_stock", "opening_cost_rate"})
    prod = Product(**data, is_active=True)
    db.add(prod)
    db.flush()

    db.add(
        PriceList(
            product_id=prod.id,
            customer_id=None,
            price=prod.selling_price,
            effective_date=date.today(),
            created_by=current_user.id,
        )
    )

    if payload.opening_stock > Decimal("0"):
        record_stock_movement(
            db,
            item_category="finished_good",
            product_id=prod.id,
            transaction_type="opening",
            direction="IN",
            quantity=payload.opening_stock,
            unit=prod.unit,
            rate=payload.opening_cost_rate,
            source_doc_type="opening_stock",
            source_doc_id=prod.id,
            source_doc_ref=f"OPEN-{prod.code}",
            user_id=current_user.id,
            remarks="Opening finished goods stock",
        )

    log_audit(
        db,
        user_id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        action="CREATE",
        entity_type="product",
        entity_id=prod.id,
        updated_values={"code": prod.code, "name": prod.name, "selling_price": prod.selling_price},
    )
    db.commit()
    db.refresh(prod)
    fg = get_fg_availability(db, prod.id)
    res = ProductRead.model_validate(prod)
    res.physical_stock = fg["physical_stock"]
    res.reserved_stock = fg["reserved_stock"]
    res.available_stock = fg["available_stock"]
    return res


@router.patch("/{product_id}", response_model=ProductRead, summary="Update product (Admin)")
def update_product(
    product_id: int,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    prod = db.get(Product, product_id)
    if not prod:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    updates = payload.model_dump(exclude_unset=True)
    prev = {k: getattr(prod, k) for k in updates}
    for field, val in updates.items():
        setattr(prod, field, val)
    if "selling_price" in updates:
        db.add(
            PriceList(
                product_id=prod.id,
                customer_id=None,
                price=prod.selling_price,
                effective_date=date.today(),
                created_by=current_user.id,
            )
        )
    log_audit(
        db,
        user_id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        action="EDIT",
        entity_type="product",
        entity_id=prod.id,
        previous_values=prev,
        updated_values=updates,
    )
    db.commit()
    db.refresh(prod)
    fg = get_fg_availability(db, prod.id)
    res = ProductRead.model_validate(prod)
    res.physical_stock = fg["physical_stock"]
    res.reserved_stock = fg["reserved_stock"]
    res.available_stock = fg["available_stock"]
    return res


@router.get("/price-lists", response_model=list[PriceListRead], summary="View price history")
def list_prices(
    product_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = (
        select(PriceList)
        .options(joinedload(PriceList.product), joinedload(PriceList.customer))
        .order_by(PriceList.effective_date.desc(), PriceList.id.desc())
    )
    if product_id is not None:
        stmt = stmt.where(PriceList.product_id == product_id)
    rows = db.execute(stmt).scalars().all()
    out = []
    for r in rows:
        item = PriceListRead.model_validate(r)
        item.product_name = r.product.name if r.product else None
        item.customer_name = r.customer.name if r.customer else "Standard Price"
        out.append(item)
    return out


@router.post("/price-lists", response_model=PriceListRead, status_code=status.HTTP_201_CREATED, summary="Add price list entry (Admin)")
def add_price_entry(
    payload: PriceListCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    prod = db.get(Product, payload.product_id)
    if not prod:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    entry = PriceList(**payload.model_dump(), created_by=current_user.id)
    db.add(entry)
    if payload.customer_id is None and payload.effective_date <= date.today():
        prod.selling_price = payload.price
    db.flush()
    log_audit(
        db,
        user_id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        action="PRICE_UPDATE",
        entity_type="price_list",
        entity_id=entry.id,
        updated_values=payload.model_dump(),
    )
    db.commit()
    db.refresh(entry)
    return PriceListRead(
        **PriceListRead.model_validate(entry).model_dump(exclude={"product_name", "customer_name"}),
        product_name=prod.name,
        customer_name="Standard Price" if entry.customer_id is None else f"Customer #{entry.customer_id}",
    )
