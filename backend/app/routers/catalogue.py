"""US-01: Maintain Role Catalogue (role categories, roles, seniority levels)."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..audit import log
from ..auth import User, require_sourcing_manager
from ..database import get_db
from ..models import AuditLog, Role, RoleCategory, SeniorityLevel
from ..schemas import (
    AuditOut,
    CatalogueOut,
    CategoryOut,
    NameIn,
    RoleCreate,
    RoleOut,
    SeniorityOut,
)

router = APIRouter(prefix="/api", tags=["Role catalogue (US-01)"])


# ---------- helpers ----------

def get_category_or_404(db: Session, category_id: str) -> RoleCategory:
    category = db.get(RoleCategory, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Role category not found")
    return category


def get_role_or_404(db: Session, role_id: str) -> Role:
    role = db.get(Role, role_id)
    if role is None:
        raise HTTPException(status_code=404, detail="Role not found")
    return role


def role_out(role: Role) -> RoleOut:
    return RoleOut(
        id=role.id,
        category_id=role.category_id,
        category_name=role.category.name,
        name=role.name,
        active=role.active,
    )


def category_name_taken(db: Session, name: str, exclude_id: str | None = None) -> bool:
    q = select(RoleCategory).where(func.lower(RoleCategory.name) == name.lower())
    if exclude_id:
        q = q.where(RoleCategory.id != exclude_id)
    return db.scalar(q) is not None


def role_name_taken(db: Session, category_id: str, name: str, exclude_id: str | None = None) -> bool:
    q = select(Role).where(Role.category_id == category_id, func.lower(Role.name) == name.lower())
    if exclude_id:
        q = q.where(Role.id != exclude_id)
    return db.scalar(q) is not None


# ---------- seniority levels (fixed list, read only) ----------

@router.get("/seniority-levels", response_model=list[SeniorityOut])
def list_seniority_levels(db: Session = Depends(get_db)):
    return db.scalars(select(SeniorityLevel).order_by(SeniorityLevel.sort_order)).all()


# ---------- role categories ----------

@router.get("/role-categories", response_model=list[CategoryOut])
def list_categories(active: bool | None = None, db: Session = Depends(get_db)):
    q = select(RoleCategory).order_by(RoleCategory.name)
    if active is not None:
        q = q.where(RoleCategory.active == active)
    return db.scalars(q).all()


@router.post("/role-categories", response_model=CategoryOut, status_code=201)
def create_category(body: NameIn, user: User = Depends(require_sourcing_manager), db: Session = Depends(get_db)):
    if category_name_taken(db, body.name):
        raise HTTPException(status_code=409, detail="A role category with this name already exists")
    category = RoleCategory(name=body.name)
    db.add(category)
    db.flush()
    log(db, user, "role_category", category.id, "CREATE", f"name={category.name}")
    db.commit()
    db.refresh(category)
    return category


@router.patch("/role-categories/{category_id}", response_model=CategoryOut)
def rename_category(
    category_id: str, body: NameIn, user: User = Depends(require_sourcing_manager), db: Session = Depends(get_db)
):
    category = get_category_or_404(db, category_id)
    if category_name_taken(db, body.name, exclude_id=category.id):
        raise HTTPException(status_code=409, detail="A role category with this name already exists")
    old = category.name
    category.name = body.name
    log(db, user, "role_category", category.id, "UPDATE", f"name: {old} -> {body.name}")
    db.commit()
    db.refresh(category)
    return category


@router.post("/role-categories/{category_id}/deactivate", response_model=CategoryOut)
def deactivate_category(
    category_id: str, user: User = Depends(require_sourcing_manager), db: Session = Depends(get_db)
):
    """Deactivates the category and all its roles (they cannot be used in new requests)."""
    category = get_category_or_404(db, category_id)
    category.active = False
    count = 0
    for role in category.roles:
        if role.active:
            role.active = False
            count += 1
            log(db, user, "role", role.id, "DEACTIVATE", f"because category '{category.name}' was deactivated")
    log(db, user, "role_category", category.id, "DEACTIVATE", f"{count} role(s) deactivated too")
    db.commit()
    db.refresh(category)
    return category


@router.post("/role-categories/{category_id}/activate", response_model=CategoryOut)
def activate_category(
    category_id: str, user: User = Depends(require_sourcing_manager), db: Session = Depends(get_db)
):
    """Activates only the category. Its roles stay inactive until activated one by one."""
    category = get_category_or_404(db, category_id)
    category.active = True
    log(db, user, "role_category", category.id, "ACTIVATE")
    db.commit()
    db.refresh(category)
    return category


# ---------- roles ----------

@router.get("/roles", response_model=list[RoleOut])
def list_roles(active: bool | None = None, category_id: str | None = None, db: Session = Depends(get_db)):
    q = select(Role).join(RoleCategory).order_by(RoleCategory.name, Role.name)
    if active is not None:
        q = q.where(Role.active == active)
    if category_id:
        q = q.where(Role.category_id == category_id)
    return [role_out(r) for r in db.scalars(q).all()]


@router.post("/roles", response_model=RoleOut, status_code=201)
def create_role(body: RoleCreate, user: User = Depends(require_sourcing_manager), db: Session = Depends(get_db)):
    category = get_category_or_404(db, body.category_id)
    if not category.active:
        raise HTTPException(status_code=409, detail="Cannot add a role to an inactive category")
    if role_name_taken(db, category.id, body.name):
        raise HTTPException(status_code=409, detail="This role already exists in the category")
    role = Role(category_id=category.id, name=body.name)
    db.add(role)
    db.flush()
    log(db, user, "role", role.id, "CREATE", f"name={role.name}, category={category.name}")
    db.commit()
    db.refresh(role)
    return role_out(role)


@router.patch("/roles/{role_id}", response_model=RoleOut)
def rename_role(role_id: str, body: NameIn, user: User = Depends(require_sourcing_manager), db: Session = Depends(get_db)):
    role = get_role_or_404(db, role_id)
    if role_name_taken(db, role.category_id, body.name, exclude_id=role.id):
        raise HTTPException(status_code=409, detail="This role already exists in the category")
    old = role.name
    role.name = body.name
    log(db, user, "role", role.id, "UPDATE", f"name: {old} -> {body.name}")
    db.commit()
    db.refresh(role)
    return role_out(role)


@router.post("/roles/{role_id}/deactivate", response_model=RoleOut)
def deactivate_role(role_id: str, user: User = Depends(require_sourcing_manager), db: Session = Depends(get_db)):
    role = get_role_or_404(db, role_id)
    role.active = False
    log(db, user, "role", role.id, "DEACTIVATE")
    db.commit()
    db.refresh(role)
    return role_out(role)


@router.post("/roles/{role_id}/activate", response_model=RoleOut)
def activate_role(role_id: str, user: User = Depends(require_sourcing_manager), db: Session = Depends(get_db)):
    role = get_role_or_404(db, role_id)
    if not role.category.active:
        raise HTTPException(status_code=409, detail="Activate the category first")
    role.active = True
    log(db, user, "role", role.id, "ACTIVATE")
    db.commit()
    db.refresh(role)
    return role_out(role)


# ---------- catalogue for other groups ----------

@router.get("/catalogue", response_model=CatalogueOut, tags=["Catalogue for other groups"])
def get_catalogue(db: Session = Depends(get_db)):
    """Active categories with their active roles, plus the seniority levels.
    Groups 1, 3 and 7 use this to get the same roleId and level codes."""
    categories = db.scalars(
        select(RoleCategory).where(RoleCategory.active.is_(True)).order_by(RoleCategory.name)
    ).all()
    levels = db.scalars(select(SeniorityLevel).order_by(SeniorityLevel.sort_order)).all()
    return CatalogueOut(
        categories=[
            {
                "id": c.id,
                "name": c.name,
                "roles": [{"id": r.id, "name": r.name} for r in sorted(c.roles, key=lambda r: r.name) if r.active],
            }
            for c in categories
        ],
        seniority_levels=levels,
    )


# ---------- audit trail ----------

@router.get("/audit-log", response_model=list[AuditOut])
def list_audit_log(
    limit: int = 50,
    entity: list[str] | None = Query(default=None, description="Only these entities, e.g. role, supplier"),
    _: User = Depends(require_sourcing_manager),
    db: Session = Depends(get_db),
):
    limit = max(1, min(limit, 500))
    q = select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
    if entity:
        q = q.where(AuditLog.entity.in_(entity))
    return db.scalars(q).all()
