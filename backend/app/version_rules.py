"""Status rules for contract versions (US-03). Pure functions with no database, so they can be unit tested directly.

Allowed moves:
- DRAFT -> IN_NEGOTIATION or ACTIVE
- IN_NEGOTIATION -> ACTIVE
- ACTIVE -> SUPERSEDED, but only automatically, when a newer version of the same framework contract is activated
- SUPERSEDED -> nothing (terminal)

- ACTIVE and SUPERSEDED versions are read-only: their rates and cap cannot be changed (see is_editable).
"""

DRAFT = "DRAFT"
IN_NEGOTIATION = "IN_NEGOTIATION"
ACTIVE = "ACTIVE"
SUPERSEDED = "SUPERSEDED"

STATUSES = (DRAFT, IN_NEGOTIATION, ACTIVE, SUPERSEDED)

# Moves a person can trigger with POST /api/contract-versions/{id}/status
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    DRAFT: frozenset({IN_NEGOTIATION, ACTIVE}),
    IN_NEGOTIATION: frozenset({ACTIVE}),
    ACTIVE: frozenset(),
    SUPERSEDED: frozenset(),
}

EDITABLE_STATUSES = frozenset({DRAFT, IN_NEGOTIATION})


def can_transition(current: str, target: str) -> bool:
    """True if a person may move a version from `current` to `target`."""
    return target in ALLOWED_TRANSITIONS.get(current, frozenset())


def transition_error(current: str, target: str) -> str | None:
    """None if the move is allowed. Otherwise the reason, in words for the user."""
    if can_transition(current, target):
        return None
    if current == SUPERSEDED:
        return "A superseded version cannot change status"
    if current == ACTIVE:
        return "An active version cannot change status. It is superseded when a newer version is activated"
    if current == target:
        return f"The version is already {target}"
    return f"A version cannot move from {current} to {target}"


def is_editable(status: str) -> bool:
    """Rates and the travel cap can only be changed while the version is DRAFT or IN_NEGOTIATION."""
    return status in EDITABLE_STATUSES
