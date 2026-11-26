"""US-03: Negotiate Contract Versions. Each negotiation round is a version with its own price limits (rates)."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .. import version_rules as rules
from ..audit import log
from ..auth import User, require_sourcing_manager
from ..database import get_db
from ..models import ContractRate, ContractVersion, Role
from ..routers.suppliers import get_contract_or_404
from ..schemas_versions import (
    CompareOut,
    CompareRow,
    RateOut,
    RatesIn,
    StatusIn,
    VersionCreate,
    VersionOut,
)

router = APIRouter(prefix="/api", tags=["Contract versions and negotiation (US-03)"])

SENIORITY_ORDER = {"JUNIOR": 1, "SENIOR": 2, "EXPERT": 3}


# ---------- helpers ----------

def get_version_or_404(db: Session, version_id: str) -> ContractVersion:
    version = db.get(ContractVersion, version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="Contract version not found")
    return version


def version_by_number(contract, number: int) -> ContractVersion:
    for version in contract.versions:
        if version.version_number == number:
            return version
    raise HTTPException(status_code=404, detail=f"Version {number} not found for this framework contract")


def latest_version(db: Session, contract_id: str) -> ContractVersion | None:
    return db.scalar(
        select(ContractVersion)
        .where(ContractVersion.framework_contract_id == contract_id)
        .order_by(ContractVersion.version_number.desc())
        .limit(1)
    )


def version_out(version: ContractVersion) -> VersionOut:
    rates = sorted(version.rates, key=lambda r: (r.role.name.lower(), SENIORITY_ORDER[r.seniority_code]))
    return VersionOut(
        id=version.id,
        framework_contract_id=version.framework_contract_id,
        version_number=version.version_number,
        version_date=version.version_date,
        status=version.status,
        travel_surcharge_cap=version.travel_surcharge_cap,
        editable=rules.is_editable(version.status),
        rates=[
            RateOut(
                role_id=r.role_id,
                role_name=r.role.name,
                seniority=r.seniority_code,
                max_daily_rate=r.max_daily_rate,
                currency=r.currency,
            )
            for r in rates
        ],
    )


def copy_terms(db: Session, source: ContractVersion, target: ContractVersion) -> tuple[int, int]:
    """Copies the travel cap and the rates of an earlier version. Rates of deactivated roles are left out.
    Returns (copied, skipped)."""
    target.travel_surcharge_cap = source.travel_surcharge_cap
    copied = skipped = 0
    for rate in source.rates:
        if not rate.role.active:
            skipped += 1
            continue
        db.add(
            ContractRate(
                contract_version_id=target.id,
                role_id=rate.role_id,
                seniority_code=rate.seniority_code,
                max_daily_rate=rate.max_daily_rate,
                currency=rate.currency,
            )
        )
        copied += 1
    return copied, skipped


# ---------- read (all roles) ----------

@router.get("/framework-contracts/{contract_id}/versions", response_model=list[VersionOut])
def list_versions(contract_id: str, db: Session = Depends(get_db)):
    """All versions of a framework contract, oldest first. Old versions stay readable."""
    contract = get_contract_or_404(db, contract_id)
    return [version_out(v) for v in contract.versions]


@router.get("/contract-versions/{version_id}", response_model=VersionOut)
def get_version(version_id: str, db: Session = Depends(get_db)):
    return version_out(get_version_or_404(db, version_id))


@router.get("/framework-contracts/{contract_id}/versions/compare", response_model=CompareOut)
def compare_versions(contract_id: str, from_version: int, to_version: int, db: Session = Depends(get_db)):
    """Rate by rate comparison of two versions (by version number), e.g. version 1 against version 2."""
    contract = get_contract_or_404(db, contract_id)
    before = version_by_number(contract, from_version)
    after = version_by_number(contract, to_version)
    rates_before = {(r.role_id, r.seniority_code): r for r in before.rates}
    rates_after = {(r.role_id, r.seniority_code): r for r in after.rates}

    rows = []
    for key in set(rates_before) | set(rates_after):
        old, new = rates_before.get(key), rates_after.get(key)
        from_rate = old.max_daily_rate if old else None
        to_rate = new.max_daily_rate if new else None
        if from_rate is None:
            change = "added"
        elif to_rate is None:
            change = "removed"
        elif from_rate != to_rate:
            change = "changed"
        else:
            change = "unchanged"
        delta = round(to_rate - from_rate, 2) if from_rate is not None and to_rate is not None else None
        role = (new or old).role
        rows.append(
            CompareRow(
                role_id=role.id,
                role_name=role.name,
                seniority=(new or old).seniority_code,
                from_rate=from_rate,
                to_rate=to_rate,
                change=change,
                delta=delta,
            )
        )
    rows.sort(key=lambda r: (r.role_name.lower(), SENIORITY_ORDER[r.seniority]))
    return CompareOut(
        from_version=before.version_number,
        to_version=after.version_number,
        travel_surcharge_cap_from=before.travel_surcharge_cap,
        travel_surcharge_cap_to=after.travel_surcharge_cap,
        rows=rows,
    )


# ---------- change (Sourcing Manager only) ----------

@router.post("/framework-contracts/{contract_id}/versions", response_model=VersionOut, status_code=201)
def create_version(
    contract_id: str,
    body: VersionCreate,
    user: User = Depends(require_sourcing_manager),
    db: Session = Depends(get_db),
):
    """Starts a new negotiation round. copy_previous=true copies the rates and travel cap of the latest version."""
    contract = get_contract_or_404(db, contract_id)
    if contract.base_status == "TERMINATED":
        raise HTTPException(status_code=409, detail="A terminated framework contract cannot get new versions")
    previous = latest_version(db, contract.id)
    if body.copy_previous and previous is None:
        raise HTTPException(status_code=409, detail="There is no previous version to copy from")

    number = previous.version_number + 1 if previous else 1
    version = ContractVersion(
        framework_contract_id=contract.id,
        version_number=number,
        version_date=body.version_date or date.today(),
        status=body.status,
    )
    db.add(version)
    db.flush()
    detail = f"{contract.reference}, version {number}, status {body.status}"
    if body.copy_previous:
        copied, skipped = copy_terms(db, previous, version)
        detail += f", copied {copied} rate(s) from version {previous.version_number}"
        if skipped:
            detail += f", {skipped} skipped because the role is deactivated"
    log(db, user, "contract_version", version.id, "CREATE", detail)
    db.commit()
    db.refresh(version)
    return version_out(version)


@router.put("/contract-versions/{version_id}/rates", response_model=VersionOut)
def save_rates(
    version_id: str,
    body: RatesIn,
    user: User = Depends(require_sourcing_manager),
    db: Session = Depends(get_db),
):
    """Replaces the rates and travel cap of a version. Only while it is DRAFT or IN_NEGOTIATION."""
    version = get_version_or_404(db, version_id)
    if not rules.is_editable(version.status):
        raise HTTPException(status_code=409, detail=f"A {version.status} version cannot be changed")

    for item in body.rates:
        role = db.get(Role, item.role_id)
        if role is None:
            raise HTTPException(status_code=422, detail=f"Role {item.role_id} does not exist")
        if not role.active:
            raise HTTPException(status_code=422, detail=f"Role '{role.name}' is deactivated and cannot get a rate")

    db.execute(delete(ContractRate).where(ContractRate.contract_version_id == version.id))
    db.flush()
    for item in body.rates:
        db.add(
            ContractRate(
                contract_version_id=version.id,
                role_id=item.role_id,
                seniority_code=item.seniority,
                max_daily_rate=item.max_daily_rate,
            )
        )
    version.travel_surcharge_cap = body.travel_surcharge_cap
    db.flush()
    db.expire(version, ["rates"])
    cap = body.travel_surcharge_cap if body.travel_surcharge_cap is not None else "none"
    log(
        db, user, "contract_version", version.id, "UPDATE",
        f"version {version.version_number}: {len(body.rates)} rate(s) saved, travel cap {cap}",
    )
    db.commit()
    db.refresh(version)
    return version_out(version)


@router.post("/contract-versions/{version_id}/status", response_model=VersionOut)
def change_status(
    version_id: str,
    body: StatusIn,
    user: User = Depends(require_sourcing_manager),
    db: Session = Depends(get_db),
):
    """Moves a version to IN_NEGOTIATION or ACTIVE (rules in version_rules.py).
    Activating a version sets the previous ACTIVE version of the same framework contract to SUPERSEDED."""
    version = get_version_or_404(db, version_id)
    contract = version.contract
    if contract.base_status == "TERMINATED":
        raise HTTPException(status_code=409, detail="The framework contract is terminated, so its versions cannot change")
    problem = rules.transition_error(version.status, body.status)
    if problem:
        raise HTTPException(status_code=409, detail=problem)

    old_status = version.status
    if body.status == rules.ACTIVE:
        current = db.scalar(
            select(ContractVersion).where(
                ContractVersion.framework_contract_id == contract.id,
                ContractVersion.status == rules.ACTIVE,
            )
        )
        if current is not None:
            current.status = rules.SUPERSEDED
            log(
                db, user, "contract_version", current.id, "SUPERSEDE",
                f"version {current.version_number} superseded by version {version.version_number} of {contract.reference}",
            )
            # The old version must leave the "one ACTIVE" index before the new one gets ACTIVE.
            db.flush()
        version.status = rules.ACTIVE
        replaces = f", replaces version {current.version_number}" if current is not None else ""
        log(db, user, "contract_version", version.id, "ACTIVATE", f"version {version.version_number} of {contract.reference}{replaces}")
    else:
        version.status = body.status
        log(db, user, "contract_version", version.id, "STATUS", f"{old_status} -> {body.status}")
    db.commit()
    db.refresh(version)
    return version_out(version)
