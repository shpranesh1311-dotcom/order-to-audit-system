from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=4, max_length=128)


class UserCreate(BaseModel):
    username: str = Field(..., min_length=2, max_length=64)
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=120)
    password: str = Field(..., min_length=6, max_length=128)
    role: str = Field(..., pattern="^(salesman|admin|production|accountant|owner)$")
    phone: str | None = None


class UserRead(ORMModel):
    id: int
    username: str
    email: str
    full_name: str
    role: str
    phone: str | None
    is_active: bool
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int
    user: UserRead


class FactorySettingsRead(ORMModel):
    id: int
    factory_name: str
    address: str
    gstin: str
    state: str
    default_variance_tolerance_pct: Decimal
    updated_at: datetime


class FactorySettingsUpdate(BaseModel):
    factory_name: str | None = None
    address: str | None = None
    gstin: str | None = None
    state: str | None = None
    default_variance_tolerance_pct: Decimal | None = Field(default=None, ge=0, le=50)
