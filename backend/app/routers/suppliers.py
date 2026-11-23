"""US-02: Manage Suppliers and Framework Contracts."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..audit import log
from ..auth import User, require_sourcing_manager
from ..contract_rules import current_contract, effective_status, not_selectable_reason
from ..database import get_db
from ..models import FrameworkContract, Supplier, new_id
from ..schemas import NameIn
from ..schemas_suppliers import ContractCreate, ContractOut, ContractUpdate, SupplierCreate, SupplierOut

router = APIRouter(prefix="/api", tags=["Suppliers and framework contracts (US-02)"])


# ---------- helpers ----------

def contract_out(contract: FrameworkContract, today: date) -> ContractOut:
    return ContractOut(
        id=contract.id,
        supplier_id=contract.supplier_id,
        reference=contract.reference,
        title=contract.title,
        valid_from=contract.valid_from,
        valid_to=contract.valid_to,
        status=effective_status(contract, today),
    )


def supplier_out(supplier: Supplier) -> SupplierOut:
    today = date.today()
    reason = not_selectable_reason(supplier, today)
    current = current_contract(supplier, today)
    return SupplierOut(
        id=supplier.id,
        name=supplier.name,
        active=supplier.active,
        selectable=reason is None,
        not_selectable_reason=reason,
        current_contract=contract_out(current, today) if current else None,
        contracts=[contract_out(c, today) for c in supplier.contracts],
    )


def get_supplier_or_404(db: Session, supplier_id: str) -> Supplier:
    supplier = db.get(Supplier, supplier_id)
    if supplier is None:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return supplier


def get_contract_or_404(db: Session, contract_id: str) -> FrameworkContract:
    contract = db.get(FrameworkContract, contract_id)
    if contract is None:
        raise HTTPException(status_code=404, detail="Framework contract not found")
    return contract


def supplier_name_taken(db: Session, name: str, exclude_id: str | None = None) -> bool:
    q = select(Supplier).where(func.lower(Supplier.name) == name.lower())
    if exclude_id:
        q = q.where(Supplier.id != exclude_id)
    return db.scalar(q) is not None


def reference_taken(db: Session, supplier_id: str, reference: str, exclude_id: str | None = None) -> bool:
    """The same supplier cannot have the same contract reference twice. Other suppliers can (shared contract such as fc-2027)."""
    q = select(FrameworkContract).where(
        FrameworkContract.supplier_id == supplier_id, func.lower(FrameworkContract.reference) == reference.lower()
    )
    if exclude_id:
        q = q.where(FrameworkContract.id != exclude_id)
    return db.scalar(q) is not None


def find_overlapping_active(
    db: Session, supplier_id: str, valid_from: date, valid_to: date, exclude_id: str | None = None
) -> FrameworkContract | None:
    """Another ACTIVE contract of the same supplier whose period overlaps. A supplier has one valid contract at a time."""
    q = select(FrameworkContract).where(
        FrameworkContract.supplier_id == supplier_id,
        FrameworkContract.base_status == "ACTIVE",
        FrameworkContract.valid_from <= valid_to,
        FrameworkContract.valid_to >= valid_from,
    )
    if exclude_id:
        q = q.where(FrameworkContract.id != exclude_id)
    return db.scalar(q)


def reject_overlap(db: Session, supplier_id: str, valid_from: date, valid_to: date, exclude_id: str | None = None) -> None:
    other = find_overlapping_active(db, supplier_id, valid_from, valid_to, exclude_id)
    if other is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Overlaps with the active contract {other.reference} ({other.valid_from} to {other.valid_to})",
        )


# ---------- suppliers ----------

@router.get("/suppliers", response_model=list[SupplierOut])
def list_suppliers(active: bool | None = None, selectable: bool | None = None, db: Session = Depends(get_db)):
    """`selectable=true` returns only suppliers that can receive requests (active supplier and a valid contract today)."""
    q = select(Supplier).options(selectinload(Supplier.contracts)).order_by(func.lower(Supplier.name))
    if active is not None:
        q = q.where(Supplier.active == active)
    result = [supplier_out(s) for s in db.scalars(q).all()]
    if selectable is not None:
        result = [s for s in result if s.selectable == selectable]
    return result


@router.post("/suppliers", response_model=SupplierOut, status_code=201)
def create_supplier(body: SupplierCreate, user: User = Depends(require_sourcing_manager), db: Session = Depends(get_db)):
    if supplier_name_taken(db, body.name):
        raise HTTPException(status_code=409, detail="A supplier with this name already exists")
    if body.supplier_id and db.get(Supplier, body.supplier_id) is not None:
        raise HTTPException(status_code=409, detail="A supplier with this supplier ID already exists")
    supplier = Supplier(id=body.supplier_id or new_id(), name=body.name)
    db.add(supplier)
    db.flush()
    log(db, user, "supplier", supplier.id, "CREATE", f"name={supplier.name}")
    db.commit()
    db.refresh(supplier)
    return supplier_out(supplier)


@router.get("/suppliers/{supplier_id}", response_model=SupplierOut)
def get_supplier(supplier_id: str, db: Session = Depends(get_db)):
    return supplier_out(get_supplier_or_404(db, supplier_id))


@router.patch("/suppliers/{supplier_id}", response_model=SupplierOut)
def rename_supplier(
    supplier_id: str, body: NameIn, user: User = Depends(require_sourcing_manager), db: Session = Depends(get_db)
):
    supplier = get_supplier_or_404(db, supplier_id)
    if supplier_name_taken(db, body.name, exclude_id=supplier.id):
        raise HTTPException(status_code=409, detail="A supplier with this name already exists")
    old = supplier.name
    supplier.name = body.name
    log(db, user, "supplier", supplier.id, "UPDATE", f"name: {old} -> {body.name}")
    db.commit()
    db.refresh(supplier)
    return supplier_out(supplier)


@router.post("/suppliers/{supplier_id}/deactivate", response_model=SupplierOut)
def deactivate_supplier(supplier_id: str, user: User = Depends(require_sourcing_manager), db: Session = Depends(get_db)):
    supplier = get_supplier_or_404(db, supplier_id)
    supplier.active = False
    log(db, user, "supplier", supplier.id, "DEACTIVATE")
    db.commit()
    db.refresh(supplier)
    return supplier_out(supplier)


@router.post("/suppliers/{supplier_id}/activate", response_model=SupplierOut)
def activate_supplier(supplier_id: str, user: User = Depends(require_sourcing_manager), db: Session = Depends(get_db)):
    supplier = get_supplier_or_404(db, supplier_id)
    supplier.active = True
    log(db, user, "supplier", supplier.id, "ACTIVATE")
    db.commit()
    db.refresh(supplier)
    return supplier_out(supplier)


# ---------- framework contracts ----------

@router.get("/framework-contracts", response_model=list[ContractOut])
def list_contracts(supplier_id: str | None = None, db: Session = Depends(get_db)):
    q = select(FrameworkContract).order_by(FrameworkContract.valid_from.desc())
    if supplier_id:
        q = q.where(FrameworkContract.supplier_id == supplier_id)
    today = date.today()
    return [contract_out(c, today) for c in db.scalars(q).all()]


@router.post("/framework-contracts", response_model=ContractOut, status_code=201)
def create_contract(body: ContractCreate, user: User = Depends(require_sourcing_manager), db: Session = Depends(get_db)):
    supplier = get_supplier_or_404(db, body.supplier_id)
    if reference_taken(db, supplier.id, body.reference):
        raise HTTPException(status_code=409, detail="This supplier already has a contract with this reference")
    if body.status == "ACTIVE":
        reject_overlap(db, supplier.id, body.valid_from, body.valid_to)
    contract = FrameworkContract(
        supplier_id=supplier.id,
        reference=body.reference,
        title=body.title,
        valid_from=body.valid_from,
        valid_to=body.valid_to,
        base_status=body.status,
    )
    db.add(contract)
    db.flush()
    log(
        db, user, "framework_contract", contract.id, "CREATE",
        f"supplier={supplier.name}, reference={contract.reference}, {contract.valid_from} to {contract.valid_to}, status={contract.base_status}"
        + (f", title={contract.title}" if contract.title else ""),
    )
    db.commit()
    db.refresh(contract)
    return contract_out(contract, date.today())


@router.get("/framework-contracts/{contract_id}", response_model=ContractOut)
def get_contract(contract_id: str, db: Session = Depends(get_db)):
    return contract_out(get_contract_or_404(db, contract_id), date.today())


@router.patch("/framework-contracts/{contract_id}", response_model=ContractOut)
def update_contract(
    contract_id: str, body: ContractUpdate, user: User = Depends(require_sourcing_manager), db: Session = Depends(get_db)
):
    contract = get_contract_or_404(db, contract_id)
    if contract.base_status == "TERMINATED":
        raise HTTPException(status_code=409, detail="A terminated contract cannot be changed")
    new_reference = body.reference if body.reference is not None else contract.reference
    new_from = body.valid_from or contract.valid_from
    new_to = body.valid_to or contract.valid_to
    new_title = body.title if "title" in body.model_fields_set else contract.title
    if new_to < new_from:
        raise HTTPException(status_code=422, detail="valid_to must not be before valid_from")
    if new_reference.lower() != contract.reference.lower() and reference_taken(
        db, contract.supplier_id, new_reference, exclude_id=contract.id
    ):
        raise HTTPException(status_code=409, detail="This supplier already has a contract with this reference")
    if contract.base_status == "ACTIVE":
        reject_overlap(db, contract.supplier_id, new_from, new_to, exclude_id=contract.id)
    changes = []
    if new_reference != contract.reference:
        changes.append(f"reference: {contract.reference} -> {new_reference}")
    if new_from != contract.valid_from:
        changes.append(f"valid_from: {contract.valid_from} -> {new_from}")
    if new_to != contract.valid_to:
        changes.append(f"valid_to: {contract.valid_to} -> {new_to}")
    if new_title != contract.title:
        changes.append(f"title: {contract.title or '-'} -> {new_title or '-'}")
    contract.reference, contract.valid_from, contract.valid_to = new_reference, new_from, new_to
    contract.title = new_title
    log(db, user, "framework_contract", contract.id, "UPDATE", "; ".join(changes) or "no change")
    db.commit()
    db.refresh(contract)
    return contract_out(contract, date.today())


@router.post("/framework-contracts/{contract_id}/activate", response_model=ContractOut)
def activate_contract(contract_id: str, user: User = Depends(require_sourcing_manager), db: Session = Depends(get_db)):
    contract = get_contract_or_404(db, contract_id)
    if contract.base_status == "TERMINATED":
        raise HTTPException(status_code=409, detail="A terminated contract cannot be activated again")
    if contract.base_status != "ACTIVE":
        reject_overlap(db, contract.supplier_id, contract.valid_from, contract.valid_to, exclude_id=contract.id)
        contract.base_status = "ACTIVE"
        log(db, user, "framework_contract", contract.id, "ACTIVATE")
        db.commit()
        db.refresh(contract)
    return contract_out(contract, date.today())


@router.post("/framework-contracts/{contract_id}/terminate", response_model=ContractOut)
def terminate_contract(contract_id: str, user: User = Depends(require_sourcing_manager), db: Session = Depends(get_db)):
    contract = get_contract_or_404(db, contract_id)
    if contract.base_status != "TERMINATED":
        contract.base_status = "TERMINATED"
        log(db, user, "framework_contract", contract.id, "TERMINATE")
        db.commit()
        db.refresh(contract)
    return contract_out(contract, date.today())
