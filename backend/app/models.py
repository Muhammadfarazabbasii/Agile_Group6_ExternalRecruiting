"""Database tables for US-01 (from our ERD): seniority_level, role_category, role, audit_log."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def new_id() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SeniorityLevel(Base):
    __tablename__ = "seniority_level"

    code: Mapped[str] = mapped_column(String(20), primary_key=True)  # JUNIOR / SENIOR / EXPERT
    label: Mapped[str] = mapped_column(String(50))
    sort_order: Mapped[int] = mapped_column(Integer)


class RoleCategory(Base):
    __tablename__ = "role_category"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    roles: Mapped[list["Role"]] = relationship(back_populates="category")


class Role(Base):
    __tablename__ = "role"
    __table_args__ = (UniqueConstraint("category_id", "name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    category_id: Mapped[str] = mapped_column(ForeignKey("role_category.id"))
    name: Mapped[str] = mapped_column(String(100))
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    category: Mapped[RoleCategory] = relationship(back_populates="roles")


class AuditLog(Base):
    """Who changed what and when (acceptance criterion: audit trail)."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    actor: Mapped[str] = mapped_column(String(100))
    entity: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[str] = mapped_column(String(36))
    action: Mapped[str] = mapped_column(String(30))
    detail: Mapped[str] = mapped_column(Text, default="")
