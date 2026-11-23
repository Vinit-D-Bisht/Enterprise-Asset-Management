from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import AuditLog, Notification


def record_audit(
    db: Session,
    actor_id: UUID | None,
    action: str,
    entity_type: str,
    entity_id: UUID | str,
    details: dict[str, Any] | None = None,
) -> None:
    db.add(
        AuditLog(
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            details=details or {},
        )
    )


def notify(db: Session, user_id: UUID, title: str, message: str) -> None:
    db.add(Notification(user_id=user_id, title=title, message=message))
