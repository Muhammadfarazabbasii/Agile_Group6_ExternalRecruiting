"""Data shapes for contract versions, rates and the version comparison (US-03)."""
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Seniority = Literal["JUNIOR", "SENIOR", "EXPERT"]
VersionStatus = Literal["DRAFT", "IN_NEGOTIATION", "ACTIVE", "SUPERSEDED"]
# US-04: rates are in one currency for now. To accept more, add the code here (team decision).
Currency = Literal["EUR"]


class VersionCreate(BaseModel):
    """A new negotiation round. copy_previous=true starts from the rates and travel cap of the latest version."""

    status: Literal["DRAFT", "IN_NEGOTIATION"] = "DRAFT"
    version_date: date | None = None  # default: today
    copy_previous: bool = False


class RateIn(BaseModel):
    """US-04: one maximum daily rate. Role, level, rate and currency are all mandatory; the rate must be above zero."""

    role_id: str
    seniority: Seniority
    max_daily_rate: float = Field(gt=0, le=100000)
    currency: Currency


class RateUpdate(BaseModel):
    """US-04: change the rate and/or the currency of one existing rate. At least one field is needed."""

    max_daily_rate: float | None = Field(default=None, gt=0, le=100000)
    currency: Currency | None = None

    @model_validator(mode="after")
    def something_to_change(self):
        if self.max_daily_rate is None and self.currency is None:
            raise ValueError("give max_daily_rate or currency to change")
        return self


class RatesIn(BaseModel):
    """Replaces all rates of a version. A role and level can appear only once."""

    travel_surcharge_cap: float | None = Field(default=None, ge=0, le=100000)
    rates: list[RateIn]

    @model_validator(mode="after")
    def no_duplicate_role_and_level(self):
        keys = [(r.role_id, r.seniority) for r in self.rates]
        if len(keys) != len(set(keys)):
            raise ValueError("each role and seniority level can only appear once")
        return self


class StatusIn(BaseModel):
    status: Literal["IN_NEGOTIATION", "ACTIVE"]


class RateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    role_id: str
    role_name: str
    seniority: str
    max_daily_rate: float
    currency: str


class VersionOut(BaseModel):
    id: str
    framework_contract_id: str
    version_number: int
    version_date: date
    status: VersionStatus
    travel_surcharge_cap: float | None
    editable: bool
    rates: list[RateOut]


class CompareRow(BaseModel):
    role_id: str
    role_name: str
    seniority: str
    from_rate: float | None
    to_rate: float | None
    change: Literal["added", "removed", "changed", "unchanged"]
    delta: float | None  # to_rate - from_rate, when both exist


class CompareOut(BaseModel):
    from_version: int
    to_version: int
    travel_surcharge_cap_from: float | None
    travel_surcharge_cap_to: float | None
    rows: list[CompareRow]
