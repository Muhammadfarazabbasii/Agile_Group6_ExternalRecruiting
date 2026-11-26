"""Reads suppliers and framework contracts from Group 7 (Expert Supplier) and maps them to our data (US-02).

Group 7's contract: docs/group7/openapi.yaml (draft 0.1.0). We only read:
  GET /suppliers                      -> [{id, name, status: active|inactive}]
  GET /framework-contracts            -> [{id, title, startDate, endDate, status: draft|rate_collection|active|ended,
                                           participations: [{supplierId, status: invited|rates_submitted|active|withdrawn}]}]

Group 7 always includes the participations in the list (agreed with them), so we do not call
GET /framework-contracts/{id} any more.

Mapping to our model:
  Group 7 supplier id          -> Supplier.id (kept as it is, for example sup-01)
  Group 7 framework contract id -> FrameworkContract.reference (for example fc-2027), one row per participating supplier.
                                   Matched on the pair (contract id, supplier id), as Group 7 offers carry both
  startDate / endDate          -> valid_from / valid_to
  title                        -> title
  status of contract + participation -> base status, see map_contract_status
"""
import os
from datetime import date

import httpx

DEFAULT_BASE_URL = "http://localhost:8080/api/v1"


class Group7Error(Exception):
    """Group 7 could not be reached or sent something we cannot read."""


class Group7Client:
    def __init__(self, base_url: str | None = None, timeout: float = 5.0, transport: httpx.BaseTransport | None = None):
        self.base_url = (base_url or os.getenv("GROUP7_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout
        self.transport = transport  # tests pass a fake transport here

    def _get(self, path: str):
        kwargs = {"timeout": self.timeout}
        if self.transport is not None:
            kwargs["transport"] = self.transport
        try:
            with httpx.Client(**kwargs) as http:
                response = http.get(self.base_url + path)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            raise Group7Error(f"Group 7 answered {e.response.status_code} for {path}") from e
        except httpx.HTTPError as e:
            raise Group7Error(f"Group 7 API is not reachable at {self.base_url}") from e
        except ValueError as e:
            raise Group7Error(f"Group 7 sent an answer for {path} that is not JSON") from e

    def _get_list(self, path: str) -> list[dict]:
        data = self._get(path)
        if not isinstance(data, list):
            raise Group7Error(f"Group 7 answer for {path} is not a list")
        return [x for x in data if isinstance(x, dict)]

    def list_suppliers(self) -> list[dict]:
        return self._get_list("/suppliers")

    def list_framework_contracts(self) -> list[dict]:
        # The list already carries the participations (agreed with Group 7), so one request is enough.
        return self._get_list("/framework-contracts")


def get_group7_client() -> Group7Client:
    """FastAPI dependency. Tests replace it with a fake."""
    return Group7Client()


# ---------- mapping ----------

def map_contract_status(contract_status: str | None, participation_status: str | None, valid_to: date, today: date) -> str:
    """Our base status (DRAFT, ACTIVE or TERMINATED) for a supplier that takes part in a Group 7 framework contract.

    - participation withdrawn: TERMINATED
    - participation invited or rates_submitted (not signed yet): DRAFT
    - participation active, contract draft or rate_collection: DRAFT
    - participation active, contract active: ACTIVE (our end date rule still shows EXPIRED later by itself)
    - participation active, contract ended: ACTIVE if the end date has passed (shows EXPIRED), otherwise TERMINATED
    - anything we do not know: DRAFT, so an unknown value never makes a supplier selectable
    """
    if participation_status == "withdrawn":
        return "TERMINATED"
    if participation_status != "active":
        return "DRAFT"
    if contract_status == "active":
        return "ACTIVE"
    if contract_status == "ended":
        return "ACTIVE" if valid_to < today else "TERMINATED"
    return "DRAFT"


def _parse_date(value) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def build_overview(suppliers: list[dict], contracts: list[dict], today: date) -> list[dict]:
    """One entry per Group 7 supplier with the framework contracts it takes part in, already mapped to our model."""
    by_supplier: dict[str, list[dict]] = {}
    for contract in contracts:
        reference = str(contract.get("id") or "").strip()
        for part in contract.get("participations") or []:
            if not isinstance(part, dict) or not part.get("supplierId"):
                continue
            valid_from = _parse_date(contract.get("startDate"))
            valid_to = _parse_date(contract.get("endDate"))
            problem = None
            if not reference:
                problem = "Contract has no ID"
            elif valid_from is None or valid_to is None:
                problem = "Contract has no valid start or end date"
            elif valid_to < valid_from:
                problem = "End date is before start date"
            mapped = None if problem else map_contract_status(contract.get("status"), part.get("status"), valid_to, today)
            by_supplier.setdefault(str(part["supplierId"]), []).append(
                {
                    "reference": reference,
                    "title": (contract.get("title") or None),
                    "valid_from": valid_from,
                    "valid_to": valid_to,
                    "group7_contract_status": contract.get("status"),
                    "participation_status": part.get("status"),
                    "mapped_status": mapped,
                    "problem": problem,
                }
            )
    overview = []
    for supplier in suppliers:
        supplier_id = str(supplier.get("id") or "").strip()
        if not supplier_id:
            continue
        overview.append(
            {
                "supplier_id": supplier_id,
                "name": str(supplier.get("name") or "").strip(),
                "group7_status": supplier.get("status"),
                "contracts": by_supplier.get(supplier_id, []),
            }
        )
    return overview
