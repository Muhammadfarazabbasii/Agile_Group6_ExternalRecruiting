"""Database tables for US-01 (from our ERD): seniority_level, role_category, role, audit_log."""
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
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
    entity_id: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(30))
    detail: Mapped[str] = mapped_column(Text, default="")


class Supplier(Base):
    """US-02: pre-selected supplier. `id` is the shared supplierId used with Group 7.

    Group 7 uses short text IDs such as `sup-01`, so the ID is text (up to 64 characters), not only a UUID.
    If we create a supplier ourselves, the ID is a generated UUID.
    """

    __tablename__ = "supplier"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(150), unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    contracts: Mapped[list["FrameworkContract"]] = relationship(
        back_populates="supplier", order_by="FrameworkContract.valid_from.desc()"
    )


class FrameworkContract(Base):
    """US-02: master agreement of a supplier.

    `reference` is the contract ID that we share with Group 7 (for example `fc-2027`). Several suppliers can sign the
    same framework contract, so the reference is unique per supplier, not for the whole table.
    `base_status` is what a person set: DRAFT, ACTIVE or TERMINATED.
    The status shown to users (ACTIVE, SCHEDULED, EXPIRED ...) is calculated from the dates,
    see contract_rules.py, so expired contracts show as expired without any job.
    """

    __tablename__ = "framework_contract"
    __table_args__ = (UniqueConstraint("supplier_id", "reference"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    supplier_id: Mapped[str] = mapped_column(ForeignKey("supplier.id"))
    reference: Mapped[str] = mapped_column(String(100))
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    valid_from: Mapped[date] = mapped_column(Date)
    valid_to: Mapped[date] = mapped_column(Date)
    base_status: Mapped[str] = mapped_column(String(20), default="DRAFT")

    supplier: Mapped[Supplier] = relationship(back_populates="contracts")
