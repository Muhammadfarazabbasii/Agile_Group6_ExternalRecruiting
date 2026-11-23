"""Data shapes for suppliers and framework contracts (US-02)."""
import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, field_validator, model_validator

from .schemas import NameIn

ContractStatus = Literal["DRAFT", "ACTIVE", "SCHEDULED", "EXPIRED", "TERMINATED"]


# Group 7 uses IDs such as sup-01 and fc-2027. A generated ID is a UUID, which also fits this pattern.
ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")


def _clean_title(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if len(value) > 200:
        raise ValueError("must be at most 200 characters")
    return value or None


def _clean_reference(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("must not be empty")
    if len(value) > 100:
        raise ValueError("must be at most 100 characters")
    return value


class SupplierCreate(NameIn):
    """supplier_id is optional. Send it only if Group 7 already has an ID for this supplier (for example sup-01)."""

    supplier_id: str | None = None

    @field_validator("supplier_id")
    @classmethod
    def must_be_valid_id(cls, v: str | None) -> str | None:
        if v is None or not v.strip():
            return None
        v = v.strip()
        if not ID_PATTERN.match(v):
            raise ValueError("must be 1 to 64 characters: letters, digits, dot, dash, underscore or colon")
        return v


class ContractCreate(BaseModel):
    supplier_id: str
    reference: str
    title: str | None = None
    valid_from: date
    valid_to: date
    status: Literal["DRAFT", "ACTIVE"] = "DRAFT"

    @field_validator("reference")
    @classmethod
    def reference_ok(cls, v: str) -> str:
        return _clean_reference(v)

    @field_validator("title")
    @classmethod
    def title_ok(cls, v: str | None) -> str | None:
        return _clean_title(v)

    @model_validator(mode="after")
    def dates_in_order(self):
        if self.valid_to < self.valid_from:
            raise ValueError("valid_to must not be before valid_from")
        return self


class ContractUpdate(BaseModel):
    """All fields optional. title: send an empty text to remove it."""

    reference: str | None = None
    title: str | None = None
    valid_from: date | None = None
    valid_to: date | None = None

    @field_validator("title")
    @classmethod
    def title_ok(cls, v: str | None) -> str | None:
        return _clean_title(v)

    @field_validator("reference")
    @classmethod
    def reference_ok(cls, v: str | None) -> str | None:
        return None if v is None else _clean_reference(v)


class ContractOut(BaseModel):
    id: str
    supplier_id: str
    reference: str
    title: str | None = None
    valid_from: date
    valid_to: date
    status: ContractStatus


class SupplierOut(BaseModel):
    id: str  # this is the shared supplierId
    name: str
    active: bool
    selectable: bool
    not_selectable_reason: str | None
    current_contract: ContractOut | None
    contracts: list[ContractOut]
