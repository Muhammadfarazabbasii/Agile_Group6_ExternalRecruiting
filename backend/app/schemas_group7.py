"""Data shapes for the Group 7 preview and import (US-02)."""
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from .schemas_suppliers import ID_PATTERN


class Group7ContractOut(BaseModel):
    reference: str
    title: str | None
    valid_from: date | None
    valid_to: date | None
    group7_contract_status: str | None
    participation_status: str | None
    mapped_status: Literal["DRAFT", "ACTIVE", "TERMINATED"] | None
    problem: str | None


class Group7SupplierOut(BaseModel):
    supplier_id: str
    name: str
    group7_status: str | None
    already_registered: bool
    contracts: list[Group7ContractOut]


class ImportRequest(BaseModel):
    supplier_ids: list[str] = Field(min_length=1, max_length=200)

    @field_validator("supplier_ids")
    @classmethod
    def ids_ok(cls, values: list[str]) -> list[str]:
        cleaned = []
        for v in values:
            v = v.strip()
            if not ID_PATTERN.match(v):
                raise ValueError(f"invalid supplier ID: {v[:30]}")
            if v not in cleaned:
                cleaned.append(v)
        return cleaned


class ImportContractResult(BaseModel):
    reference: str
    result: Literal["imported", "skipped"]
    message: str


class ImportSupplierResult(BaseModel):
    supplier_id: str
    name: str | None
    result: Literal["created", "existing", "skipped", "not_found"]
    message: str
    contracts: list[ImportContractResult]
