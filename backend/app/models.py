"""Database tables for US-01 (from our ERD): seniority_level, role_category, role, audit_log."""
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, text
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
    versions: Mapped[list["ContractVersion"]] = relationship(
        back_populates="contract", order_by="ContractVersion.version_number"
    )


class ContractVersion(Base):
    """US-03: one negotiation round of a framework contract, with the price limits agreed in that round.

    `status` is DRAFT, IN_NEGOTIATION, ACTIVE or SUPERSEDED. The moves between them are in version_rules.py.
    The partial unique index allows at most one ACTIVE version per framework contract. The database enforces it,
    not only the code.
    """

    __tablename__ = "contract_version"
    __table_args__ = (
        UniqueConstraint("framework_contract_id", "version_number"),
        Index(
            "uq_one_active_version_per_contract",
            "framework_contract_id",
            unique=True,
            sqlite_where=text("status = 'ACTIVE'"),
            postgresql_where=text("status = 'ACTIVE'"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    framework_contract_id: Mapped[str] = mapped_column(ForeignKey("framework_contract.id"))
    version_number: Mapped[int] = mapped_column(Integer)
    version_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")
    travel_surcharge_cap: Mapped[float | None] = mapped_column(Numeric(10, 2, asdecimal=False), nullable=True)

    contract: Mapped[FrameworkContract] = relationship(back_populates="versions")
    rates: Mapped[list["ContractRate"]] = relationship(
        back_populates="version", cascade="all, delete-orphan", order_by="ContractRate.id"
    )


class ContractRate(Base):
    """US-03: maximum daily rate for one role and seniority level within one contract version."""

    __tablename__ = "contract_rate"
    __table_args__ = (UniqueConstraint("contract_version_id", "role_id", "seniority_code"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    contract_version_id: Mapped[str] = mapped_column(ForeignKey("contract_version.id"))
    role_id: Mapped[str] = mapped_column(ForeignKey("role.id"))
    seniority_code: Mapped[str] = mapped_column(ForeignKey("seniority_level.code"))
    max_daily_rate: Mapped[float] = mapped_column(Numeric(10, 2, asdecimal=False))
    currency: Mapped[str] = mapped_column(String(3), default="EUR")

    version: Mapped[ContractVersion] = relationship(back_populates="rates")
    role: Mapped[Role] = relationship()
