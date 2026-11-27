from decimal import Decimal
from typing import Any
from sqlalchemy.orm import Session


def _serialize_for_json(data: dict[str, Any] | None) -> dict[str, Any] | None:
    if data is None:
        return None
    serialized: dict[str, Any] = {}
    for k, v in data.items():
        if isinstance(v, Decimal):
            serialized[k] = str(v)
        elif hasattr(v, "isoformat"):
            serialized[k] = v.isoformat()
        elif isinstance(v, dict):
            serialized[k] = _serialize_for_json(v)
        elif isinstance(v, list):
            serialized[k] = [
                _serialize_for_json(item) if isinstance(item, dict) else (str(item) if isinstance(item, Decimal) else item)
                for item in v
            ]
        else:
            serialized[k] = v
    return serialized


def log_audit(
    db: Session,
    *,
    user_id: int | None,
    username: str,
    role: str,
    action: str,
    entity_type: str,
    entity_id: str | int,
    previous_values: dict[str, Any] | None = None,
    updated_values: dict[str, Any] | None = None,
    remarks: str | None = None,
) -> None:
    from app.models.audit import AuditLog

    entry = AuditLog(
        user_id=user_id,
        username=username,
        role=role,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        previous_values=_serialize_for_json(previous_values),
        updated_values=_serialize_for_json(updated_values),
        remarks=remarks,
    )
    db.add(entry)
