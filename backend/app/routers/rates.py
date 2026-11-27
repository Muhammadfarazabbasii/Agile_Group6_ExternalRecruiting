"""US-04: Maximum daily rate per contract version, role and seniority level.

Rules (checked here and tested in tests/test_rates.py):
- Exactly one rate per version + role + level. A second one is refused (409), and the database enforces it too.
- Role, level, rate and currency are mandatory. The rate must be above zero.
- Rates of an ACTIVE or SUPERSEDED version cannot be changed (409). Reading them is always allowed.
- A role and level without a rate is not allowed for the supplier. The lookup endpoint answers 404 for it.
- Only the Sourcing Manager may write. Everybody may read.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import version_rules as rules
from ..audit import log
from ..auth import User, require_sourcing_manager
from ..database import get_db
from ..models import ContractRate, ContractVersion, Role
from ..routers.versions import SENIORITY_ORDER, get_version_or_404
from ..schemas_versions import RateIn, RateOut, RateUpdate, Seniority

router = APIRouter(prefix="/api", tags=["Maximum daily rates (US-04)"])


# ---------- helpers ----------

def rate_out(rate: ContractRate) -> RateOut:
    return RateOut(
        role_id=rate.role_id,
        role_name=rate.role.name,
        seniority=rate.seniority_code,
        max_daily_rate=rate.max_daily_rate,
        currency=rate.currency,
    )


def rate_or_404(db: Session, rate_id: str) -> ContractRate:
    rate = db.get(ContractRate, rate_id)
    if rate is None:
        raise HTTPException(status_code=404, detail="Maximum daily rate not found")
    return rate


def refuse_if_locked(version: ContractVersion) -> None:
    if not rules.is_editable(version.status):
        raise HTTPException(
            status_code=409,
            detail=f"A {version.status} version cannot be changed. Its rates are read only",
        )


def describe(rate: ContractRate) -> str:
    return f"{rate.role.name} / {rate.seniority_code}: {rate.max_daily_rate} {rate.currency}"


# ---------- read (all roles) ----------

@router.get("/contract-versions/{version_id}/rates", response_model=list[RateOut])
def list_rates(version_id: str, db: Session = Depends(get_db)):
    """All maximum daily rates of a version. Missing role/level combinations are not allowed."""
    version = get_version_or_404(db, version_id)
    rates = sorted(version.rates, key=lambda r: (r.role.name.lower(), SENIORITY_ORDER[r.seniority_code]))
    return [rate_out(r) for r in rates]


@router.get("/contract-versions/{version_id}/max-rate", response_model=RateOut)
def get_max_rate(
    version_id: str,
    role_id: str = Query(description="Role ID from GET /api/catalogue"),
    seniority: Seniority = Query(description="JUNIOR, SENIOR or EXPERT"),
    db: Session = Depends(get_db),
):
    """The maximum daily rate for one role and level in one version. 404 means: not allowed for this supplier."""
    get_version_or_404(db, version_id)
    rate = db.scalar(
        select(ContractRate).where(
            ContractRate.contract_version_id == version_id,
            ContractRate.role_id == role_id,
            ContractRate.seniority_code == seniority,
        )
    )
    if rate is None:
        raise HTTPException(
            status_code=404,
            detail="Not allowed: this version has no maximum daily rate for this role and seniority level",
        )
    return rate_out(rate)


@router.get("/contract-rates/{rate_id}", response_model=RateOut)
def get_rate(rate_id: str, db: Session = Depends(get_db)):
    return rate_out(rate_or_404(db, rate_id))


# ---------- change (Sourcing Manager only, only while the version is DRAFT or IN_NEGOTIATION) ----------

@router.post("/contract-versions/{version_id}/rates", response_model=RateOut, status_code=201)
def create_rate(
    version_id: str,
    body: RateIn,
    user: User = Depends(require_sourcing_manager),
    db: Session = Depends(get_db),
):
    version = get_version_or_404(db, version_id)
    refuse_if_locked(version)

    role = db.get(Role, body.role_id)
    if role is None:
        raise HTTPException(status_code=422, detail=f"Role {body.role_id} does not exist")
    if not role.active:
        raise HTTPException(status_code=422, detail=f"Role '{role.name}' is deactivated and cannot get a rate")

    exists = db.scalar(
        select(ContractRate.id).where(
            ContractRate.contract_version_id == version.id,
            ContractRate.role_id == body.role_id,
            ContractRate.seniority_code == body.seniority,
        )
    )
    if exists is not None:
        raise HTTPException(
            status_code=409,
            detail=f"A rate for {role.name} / {body.seniority} already exists in this version. Change it instead",
        )

    rate = ContractRate(
        contract_version_id=version.id,
        role_id=body.role_id,
        seniority_code=body.seniority,
        max_daily_rate=body.max_daily_rate,
        currency=body.currency,
    )
    db.add(rate)
    db.flush()
    log(db, user, "contract_version", version.id, "RATE_ADD", f"version {version.version_number}: {describe(rate)}")
    db.commit()
    db.refresh(rate)
    return rate_out(rate)


@router.patch("/contract-rates/{rate_id}", response_model=RateOut)
def update_rate(
    rate_id: str,
    body: RateUpdate,
    user: User = Depends(require_sourcing_manager),
    db: Session = Depends(get_db),
):
    rate = rate_or_404(db, rate_id)
    version = rate.version
    refuse_if_locked(version)

    before = describe(rate)
    if body.max_daily_rate is not None:
        rate.max_daily_rate = body.max_daily_rate
    if body.currency is not None:
        rate.currency = body.currency
    log(
        db, user, "contract_version", version.id, "RATE_CHANGE",
        f"version {version.version_number}: {before} -> {describe(rate)}",
    )
    db.commit()
    db.refresh(rate)
    return rate_out(rate)


@router.delete("/contract-rates/{rate_id}", status_code=204)
def delete_rate(
    rate_id: str,
    user: User = Depends(require_sourcing_manager),
    db: Session = Depends(get_db),
):
    """Removes a rate. The role and level become 'not allowed' in this version."""
    rate = rate_or_404(db, rate_id)
    version = rate.version
    refuse_if_locked(version)

    log(db, user, "contract_version", version.id, "RATE_DELETE", f"version {version.version_number}: {describe(rate)} removed")
    db.delete(rate)
    db.commit()
    return Response(status_code=204)
