"""US-02: take over suppliers and their framework contracts from Group 7 (Expert Supplier).

The Sourcing Manager first looks at what Group 7 has (preview), then chooses which suppliers become
pre-selected suppliers of ours. Nothing is imported automatically.
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..audit import log
from ..auth import User, require_sourcing_manager
from ..database import get_db
from ..group7_client import Group7Client, Group7Error, build_overview, get_group7_client
from ..models import FrameworkContract, Supplier
from ..routers.suppliers import find_overlapping_active, reference_taken
from ..schemas_group7 import (
    Group7SupplierOut,
    ImportContractResult,
    ImportRequest,
    ImportSupplierResult,
)

router = APIRouter(prefix="/api/group7", tags=["Group 7 integration (US-02)"])


def load_overview(client: Group7Client) -> list[dict]:
    try:
        return build_overview(client.list_suppliers(), client.list_framework_contracts(), date.today())
    except Group7Error as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/suppliers", response_model=list[Group7SupplierOut])
def preview_group7_suppliers(
    _: User = Depends(require_sourcing_manager),
    client: Group7Client = Depends(get_group7_client),
    db: Session = Depends(get_db),
):
    """What Group 7 has: suppliers and the framework contracts they take part in, already mapped to our statuses.
    `already_registered` is true if the supplier is in our pool. 502 if Group 7 cannot be reached."""
    overview = load_overview(client)
    registered = set(db.scalars(select(Supplier.id)).all())
    return [{**entry, "already_registered": entry["supplier_id"] in registered} for entry in overview]


@router.post("/import-suppliers", response_model=list[ImportSupplierResult])
def import_group7_suppliers(
    body: ImportRequest,
    user: User = Depends(require_sourcing_manager),
    client: Group7Client = Depends(get_group7_client),
    db: Session = Depends(get_db),
):
    """Register the chosen Group 7 suppliers and their framework contracts. Safe to repeat: what exists is not changed."""
    overview = {entry["supplier_id"]: entry for entry in load_overview(client)}
    results = []
    for supplier_id in body.supplier_ids:
        entry = overview.get(supplier_id)
        if entry is None:
            results.append(ImportSupplierResult(supplier_id=supplier_id, name=None, result="not_found",
                                                message="Group 7 has no supplier with this ID", contracts=[]))
            continue
        results.append(import_one(db, user, entry))
    db.commit()
    return results


def import_one(db: Session, user: User, entry: dict) -> ImportSupplierResult:
    supplier_id = entry["supplier_id"]
    name = entry["name"][:150]
    supplier = db.get(Supplier, supplier_id)
    if supplier is not None:
        outcome, message = "existing", "Supplier is already in our pool. Name and status were not changed"
    elif not name:
        return ImportSupplierResult(supplier_id=supplier_id, name=None, result="skipped",
                                    message="Group 7 sent no name for this supplier", contracts=[])
    else:
        same_name = db.scalar(select(Supplier).where(func.lower(Supplier.name) == name.lower()))
        if same_name is not None:
            return ImportSupplierResult(
                supplier_id=supplier_id, name=name, result="skipped", contracts=[],
                message=f"We already have a supplier named {name} with another ID ({same_name.id})",
            )
        supplier = Supplier(id=supplier_id, name=name, active=entry["group7_status"] == "active")
        db.add(supplier)
        db.flush()
        log(db, user, "supplier", supplier.id, "IMPORT", f"name={name}, from Group 7 (status {entry['group7_status']})")
        outcome, message = "created", "Supplier registered"

    contract_results = []
    for c in entry["contracts"]:
        contract_results.append(import_contract(db, user, supplier, c))
    return ImportSupplierResult(supplier_id=supplier_id, name=supplier.name, result=outcome, message=message,
                                contracts=contract_results)


def import_contract(db: Session, user: User, supplier: Supplier, c: dict) -> ImportContractResult:
    reference = c["reference"] or "(no ID)"

    def skipped(message: str) -> ImportContractResult:
        return ImportContractResult(reference=reference, result="skipped", message=message)

    if c["problem"]:
        return skipped(c["problem"])
    if reference_taken(db, supplier.id, c["reference"]):
        return skipped("Supplier already has this contract. It was not changed")
    status = c["mapped_status"]
    if status == "ACTIVE":
        other = find_overlapping_active(db, supplier.id, c["valid_from"], c["valid_to"])
        if other is not None:
            return skipped(f"Overlaps with the active contract {other.reference} ({other.valid_from} to {other.valid_to})")
    contract = FrameworkContract(
        supplier_id=supplier.id,
        reference=c["reference"],
        title=c["title"],
        valid_from=c["valid_from"],
        valid_to=c["valid_to"],
        base_status=status,
    )
    db.add(contract)
    db.flush()
    log(
        db, user, "framework_contract", contract.id, "IMPORT",
        f"supplier={supplier.name}, reference={contract.reference}, {contract.valid_from} to {contract.valid_to}, "
        f"status={status} (Group 7: contract {c['group7_contract_status']}, participation {c['participation_status']})",
    )
    return ImportContractResult(reference=reference, result="imported", message=f"Registered as {status}")
