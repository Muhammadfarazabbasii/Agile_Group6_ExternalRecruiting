"""Business rules for framework contracts (US-02).

US-07 ("only suppliers with a valid master agreement can receive requests") uses
`not_selectable_reason` / `current_contract` from here, so the rule lives in one place.
"""
from datetime import date

from .models import FrameworkContract, Supplier


def effective_status(contract: FrameworkContract, today: date | None = None) -> str:
    """Status shown to users. DRAFT and TERMINATED are set by a person, the rest follows the dates."""
    today = today or date.today()
    if contract.base_status in ("DRAFT", "TERMINATED"):
        return contract.base_status
    if today > contract.valid_to:
        return "EXPIRED"
    if today < contract.valid_from:
        return "SCHEDULED"
    return "ACTIVE"


def current_contract(supplier: Supplier, today: date | None = None) -> FrameworkContract | None:
    """The contract that is valid today, if any."""
    for contract in supplier.contracts:
        if effective_status(contract, today) == "ACTIVE":
            return contract
    return None


def not_selectable_reason(supplier: Supplier, today: date | None = None) -> str | None:
    """None means the supplier can receive requests. Otherwise a short reason."""
    if not supplier.active:
        return "Supplier is deactivated"
    if current_contract(supplier, today) is not None:
        return None
    statuses = {effective_status(c, today) for c in supplier.contracts}
    if "SCHEDULED" in statuses:
        return "Framework contract has not started yet"
    if "EXPIRED" in statuses:
        return "Framework contract has expired"
    if "DRAFT" in statuses:
        return "Framework contract is still a draft"
    if "TERMINATED" in statuses:
        return "Framework contract was terminated"
    return "No framework contract"
