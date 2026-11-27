from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.permissions import UserRole, require_roles
from app.models.audit import AuditLog
from app.models.user import User
from app.schemas.inventory_reports import AuditLogRead

router = APIRouter(prefix="/api/audit", tags=["Audit Trail"])


@router.get("", response_model=list[AuditLogRead], summary="View immutable audit trail")
def list_audit_logs(
    entity_type: str | None = Query(default=None),
    action: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN, UserRole.ACCOUNTANT, UserRole.OWNER)),
):
    stmt = select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    return db.execute(stmt).scalars().all()
