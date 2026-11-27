from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.audit import log_audit
from app.core.database import get_db
from app.core.permissions import UserRole, get_current_user, require_roles
from app.core.security import hash_password
from app.models.user import FactorySettings, User
from app.schemas.common import FactorySettingsRead, FactorySettingsUpdate, UserCreate, UserRead

router = APIRouter(prefix="/api/users", tags=["Users & Settings"])


@router.get("", response_model=list[UserRead], summary="List users (Admin/Owner)")
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN, UserRole.OWNER)),
):
    return db.execute(select(User).order_by(User.id)).scalars().all()


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED, summary="Create user (Admin)")
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    existing = db.execute(select(User).where(User.username == payload.username)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists")
    user = User(
        username=payload.username,
        email=payload.email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        role=payload.role,
        phone=payload.phone,
        is_active=True,
    )
    db.add(user)
    db.flush()
    log_audit(
        db,
        user_id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        action="CREATE",
        entity_type="user",
        entity_id=user.id,
        updated_values={"username": user.username, "role": user.role},
    )
    db.commit()
    db.refresh(user)
    return user


@router.get("/factory-settings", response_model=FactorySettingsRead, summary="Get factory GST & tolerance settings")
def get_factory_settings(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    settings = db.execute(select(FactorySettings)).scalar_one_or_none()
    if not settings:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Factory settings not configured")
    return settings


@router.patch("/factory-settings", response_model=FactorySettingsRead, summary="Update factory settings (Admin)")
def update_factory_settings(
    payload: FactorySettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    settings = db.execute(select(FactorySettings)).scalar_one_or_none()
    if not settings:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Factory settings not configured")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(settings, field, value)
    log_audit(
        db,
        user_id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        action="EDIT",
        entity_type="factory_settings",
        entity_id=settings.id,
        updated_values=payload.model_dump(exclude_unset=True),
    )
    db.commit()
    db.refresh(settings)
    return settings
