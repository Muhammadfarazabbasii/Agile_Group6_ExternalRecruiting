"""Audit trail helper shared by all stories: who changed what and when."""
from sqlalchemy.orm import Session

from .auth import User
from .models import AuditLog


def log(db: Session, user: User, entity: str, entity_id: str, action: str, detail: str = "") -> None:
    db.add(AuditLog(actor=user.name, entity=entity, entity_id=entity_id, action=action, detail=detail))
