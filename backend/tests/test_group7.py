"""US-02: take-over of suppliers and framework contracts from Group 7. Group 7 is replaced by a fake server."""
import json
from datetime import date, timedelta
from pathlib import Path

import httpx
import pytest

from app.group7_client import Group7Client, Group7Error, get_group7_client, map_contract_status
from app.main import app
from tests.conftest import HIRING_MANAGER, SOURCING_MANAGER

TODAY = date(2026, 11, 23)


def iso(offset: int) -> str:
    return (date.today() + timedelta(days=offset)).isoformat()


def group7_data():
    suppliers = [
        {"id": "sup-01", "name": "Nordlicht IT Consulting", "status": "active"},
        {"id": "sup-02", "name": "Alpen Experts", "status": "active"},
        {"id": "sup-03", "name": "Old Supplier", "status": "inactive"},
        {"id": "sup-04", "name": "No Contract GmbH", "status": "active"},
    ]
    contracts = [
        {
            "id": "fc-2027", "title": "IT Expert Services 2027", "startDate": iso(-30), "endDate": iso(300),
            "status": "active",
            "participations": [
                {"id": "part-01", "contractId": "fc-2027", "supplierId": "sup-01", "status": "active"},
                {"id": "part-02", "contractId": "fc-2027", "supplierId": "sup-02", "status": "invited"},
                {"id": "part-03", "contractId": "fc-2027", "supplierId": "sup-03", "status": "withdrawn"},
            ],
        }
    ]
    return suppliers, contracts


def make_transport(suppliers, contracts, fail=None):
    def handler(request: httpx.Request) -> httpx.Response:
        if fail:
            return httpx.Response(fail)
        path = request.url.path
        if path.endswith("/suppliers"):
            return httpx.Response(200, json=suppliers)
        if path.endswith("/framework-contracts"):
            return httpx.Response(200, json=contracts)
        return httpx.Response(404)
    return httpx.MockTransport(handler)


@pytest.fixture()
def g7(client):
    state = {"data": group7_data(), "fail": None}

    def override():
        s, c = state["data"]
        return Group7Client(base_url="http://group7.test/api/v1", transport=make_transport(s, c, state["fail"]))

    app.dependency_overrides[get_group7_client] = override
    yield state
    app.dependency_overrides.pop(get_group7_client, None)


# ---------- status mapping ----------

@pytest.mark.parametrize(
    "contract,part,end,expected",
    [
        ("active", "active", TODAY + timedelta(days=5), "ACTIVE"),
        ("active", "invited", TODAY + timedelta(days=5), "DRAFT"),
        ("active", "rates_submitted", TODAY + timedelta(days=5), "DRAFT"),
        ("active", "withdrawn", TODAY + timedelta(days=5), "TERMINATED"),
        ("draft", "active", TODAY + timedelta(days=5), "DRAFT"),
        ("rate_collection", "active", TODAY + timedelta(days=5), "DRAFT"),
        ("ended", "active", TODAY - timedelta(days=1), "ACTIVE"),      # runs out by date, shown as EXPIRED
        ("ended", "active", TODAY + timedelta(days=5), "TERMINATED"),   # ended early
        ("ended", "withdrawn", TODAY - timedelta(days=1), "TERMINATED"),
        ("something-new", "active", TODAY + timedelta(days=5), "DRAFT"),
        (None, None, TODAY, "DRAFT"),
    ],
)
def test_status_mapping(contract, part, end, expected):
    assert map_contract_status(contract, part, end, TODAY) == expected


def test_all_group7_status_values_are_known_to_us():
    """Contract test: if Group 7 adds a status value, this test fails and we must decide how to map it."""
    spec = json.loads((Path(__file__).parents[2] / "docs/group7/openapi.json").read_text(encoding="utf-8"))
    schemas = spec["components"]["schemas"]
    known_contract = {"draft", "rate_collection", "active", "ended"}
    known_part = {"invited", "rates_submitted", "active", "withdrawn"}
    assert set(schemas["FrameworkContract"]["properties"]["status"]["enum"]) == known_contract
    assert set(schemas["ContractParticipation"]["properties"]["status"]["enum"]) == known_part
    assert set(schemas["Supplier"]["properties"]["status"]["enum"]) == {"active", "inactive"}
    for field in ("id", "title", "startDate", "endDate", "status", "participations"):
        assert field in schemas["FrameworkContract"]["properties"]
    assert "supplierId" in schemas["ContractParticipation"]["properties"]


# ---------- preview ----------

def test_preview_shows_group7_suppliers_with_mapped_contracts(client, g7):
    r = client.get("/api/group7/suppliers", headers=SOURCING_MANAGER)
    assert r.status_code == 200
    by_id = {s["supplier_id"]: s for s in r.json()}
    assert len(by_id) == 4
    s1 = by_id["sup-01"]
    assert s1["already_registered"] is False
    assert s1["contracts"][0]["reference"] == "fc-2027"
    assert s1["contracts"][0]["mapped_status"] == "ACTIVE"
    assert by_id["sup-02"]["contracts"][0]["mapped_status"] == "DRAFT"
    assert by_id["sup-03"]["contracts"][0]["mapped_status"] == "TERMINATED"
    assert by_id["sup-04"]["contracts"] == []


def test_preview_is_only_for_sourcing_manager(client, g7):
    assert client.get("/api/group7/suppliers", headers=HIRING_MANAGER).status_code == 403


def test_preview_when_group7_is_down_gives_502(client, g7):
    g7["fail"] = 503
    r = client.get("/api/group7/suppliers", headers=SOURCING_MANAGER)
    assert r.status_code == 502
    assert "Group 7" in r.json()["detail"]


def test_client_reports_unreachable_server():
    def boom(request):
        raise httpx.ConnectError("refused")

    with pytest.raises(Group7Error):
        Group7Client(base_url="http://x.test", transport=httpx.MockTransport(boom)).list_suppliers()


def test_client_rejects_answer_that_is_not_a_list():
    t = httpx.MockTransport(lambda request: httpx.Response(200, json={"oops": 1}))
    with pytest.raises(Group7Error):
        Group7Client(base_url="http://x.test", transport=t).list_suppliers()


# ---------- import ----------

def test_import_creates_supplier_and_contract_with_group7_ids(client, g7):
    r = client.post("/api/group7/import-suppliers", json={"supplier_ids": ["sup-01"]}, headers=SOURCING_MANAGER)
    assert r.status_code == 200
    result = r.json()[0]
    assert result["result"] == "created"
    assert result["contracts"][0]["result"] == "imported"
    s = client.get("/api/suppliers/sup-01", headers=HIRING_MANAGER).json()
    assert s["name"] == "Nordlicht IT Consulting"
    assert s["contracts"][0]["reference"] == "fc-2027"
    assert s["contracts"][0]["title"] == "IT Expert Services 2027"
    assert s["contracts"][0]["status"] == "ACTIVE"
    assert s["selectable"] is True


def test_imported_supplier_with_invited_participation_is_not_selectable(client, g7):
    client.post("/api/group7/import-suppliers", json={"supplier_ids": ["sup-02"]}, headers=SOURCING_MANAGER)
    s = client.get("/api/suppliers/sup-02", headers=HIRING_MANAGER).json()
    assert s["contracts"][0]["status"] == "DRAFT"
    assert s["selectable"] is False


def test_inactive_group7_supplier_is_imported_as_inactive(client, g7):
    client.post("/api/group7/import-suppliers", json={"supplier_ids": ["sup-03"]}, headers=SOURCING_MANAGER)
    s = client.get("/api/suppliers/sup-03", headers=HIRING_MANAGER).json()
    assert s["active"] is False
    assert s["selectable"] is False


def test_import_twice_changes_nothing(client, g7):
    body = {"supplier_ids": ["sup-01", "sup-04"]}
    client.post("/api/group7/import-suppliers", json=body, headers=SOURCING_MANAGER)
    r = client.post("/api/group7/import-suppliers", json=body, headers=SOURCING_MANAGER).json()
    assert [x["result"] for x in r] == ["existing", "existing"]
    assert r[0]["contracts"][0]["result"] == "skipped"
    s = client.get("/api/suppliers/sup-01", headers=HIRING_MANAGER).json()
    assert len(s["contracts"]) == 1


def test_import_does_not_overwrite_local_changes(client, g7):
    client.post("/api/group7/import-suppliers", json={"supplier_ids": ["sup-01"]}, headers=SOURCING_MANAGER)
    client.post("/api/suppliers/sup-01/deactivate", headers=SOURCING_MANAGER)
    client.post("/api/group7/import-suppliers", json={"supplier_ids": ["sup-01"]}, headers=SOURCING_MANAGER)
    assert client.get("/api/suppliers/sup-01", headers=HIRING_MANAGER).json()["active"] is False


def test_unknown_supplier_id_is_reported(client, g7):
    r = client.post("/api/group7/import-suppliers", json={"supplier_ids": ["sup-99"]}, headers=SOURCING_MANAGER)
    assert r.json()[0]["result"] == "not_found"


def test_supplier_with_same_name_but_other_id_is_skipped(client, g7):
    client.post("/api/suppliers", json={"name": "alpen experts"}, headers=SOURCING_MANAGER)
    r = client.post("/api/group7/import-suppliers", json={"supplier_ids": ["sup-02"]}, headers=SOURCING_MANAGER)
    assert r.json()[0]["result"] == "skipped"
    assert client.get("/api/suppliers/sup-02", headers=HIRING_MANAGER).status_code == 404


def test_contract_with_bad_dates_is_skipped_but_supplier_is_created(client, g7):
    g7["data"][1][0]["endDate"] = iso(-100)  # before start
    r = client.post("/api/group7/import-suppliers", json={"supplier_ids": ["sup-01"]}, headers=SOURCING_MANAGER).json()[0]
    assert r["result"] == "created"
    assert r["contracts"][0]["result"] == "skipped"
    assert client.get("/api/suppliers/sup-01", headers=HIRING_MANAGER).json()["contracts"] == []


def test_overlapping_active_contract_is_skipped(client, g7):
    client.post("/api/suppliers", json={"name": "Nordlicht IT Consulting", "supplier_id": "sup-01"}, headers=SOURCING_MANAGER)
    local = {"supplier_id": "sup-01", "reference": "local-1", "valid_from": iso(-10), "valid_to": iso(100)}
    c = client.post("/api/framework-contracts", json=local, headers=SOURCING_MANAGER).json()
    client.post(f"/api/framework-contracts/{c['id']}/activate", headers=SOURCING_MANAGER)
    r = client.post("/api/group7/import-suppliers", json={"supplier_ids": ["sup-01"]}, headers=SOURCING_MANAGER).json()[0]
    assert r["contracts"][0]["result"] == "skipped"
    assert "Overlaps" in r["contracts"][0]["message"]


def test_import_is_written_to_audit_log(client, g7):
    client.post("/api/group7/import-suppliers", json={"supplier_ids": ["sup-01"]}, headers=SOURCING_MANAGER)
    log = client.get("/api/audit-log", headers=SOURCING_MANAGER).json()
    assert sum(1 for e in log if e["action"] == "IMPORT") == 2  # supplier and contract


def test_import_only_for_sourcing_manager_and_validates_ids(client, g7):
    assert client.post("/api/group7/import-suppliers", json={"supplier_ids": ["sup-01"]}, headers=HIRING_MANAGER).status_code == 403
    assert client.post("/api/group7/import-suppliers", json={"supplier_ids": []}, headers=SOURCING_MANAGER).status_code == 422
    assert client.post("/api/group7/import-suppliers", json={"supplier_ids": ["bad id"]}, headers=SOURCING_MANAGER).status_code == 422


def test_import_when_group7_is_down_gives_502_and_changes_nothing(client, g7):
    g7["fail"] = 500
    r = client.post("/api/group7/import-suppliers", json={"supplier_ids": ["sup-01"]}, headers=SOURCING_MANAGER)
    assert r.status_code == 502
    assert client.get("/api/suppliers/sup-01", headers=HIRING_MANAGER).status_code == 404
