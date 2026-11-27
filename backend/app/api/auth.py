from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.database import get_db
from app.core.permissions import get_current_user
from app.core.security import create_access_token, verify_password
from app.models.user import User
from app.schemas.common import LoginRequest, TokenResponse, UserRead

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
settings = get_settings()


@router.post("/login", response_model=TokenResponse, summary="Authenticate user and issue JWT token")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.execute(select(User).where(User.username == payload.username.strip())).scalar_one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )
    token = create_access_token(
        subject=str(user.id),
        role=user.role,
        extra_claims={"username": user.username},
    )
    return TokenResponse(
        access_token=token,
        expires_in_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        user=UserRead.model_validate(user),
    )


@router.get("/me", response_model=UserRead, summary="Get current authenticated user")
def read_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/logout", summary="Client logout acknowledgement")
def logout(current_user: User = Depends(get_current_user)):
    return {"message": f"Logged out {current_user.username}"}
