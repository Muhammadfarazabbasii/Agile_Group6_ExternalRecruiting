"""Shapes of the data that goes in and out of the API (this becomes the OpenAPI spec)."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


def _clean(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("must not be empty")
    return value


class NameIn(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = _clean(v)
        if len(v) > 100:
            raise ValueError("must be at most 100 characters")
        return v


class RoleCreate(NameIn):
    category_id: str


class SeniorityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    code: str
    label: str


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    active: bool


class RoleOut(BaseModel):
    id: str
    category_id: str
    category_name: str
    name: str
    active: bool


class CatalogueRole(BaseModel):
    id: str
    name: str


class CatalogueCategory(BaseModel):
    id: str
    name: str
    roles: list[CatalogueRole]


class CatalogueOut(BaseModel):
    """Read-only view for other groups: only active entries."""
    categories: list[CatalogueCategory]
    seniority_levels: list[SeniorityOut]


class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    actor: str
    entity: str
    entity_id: str
    action: str
    detail: str
