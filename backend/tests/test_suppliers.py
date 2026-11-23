from datetime import date, timedelta

from .conftest import HIRING_MANAGER, SOURCING_MANAGER

TODAY = date.today()


def d(days: int) -> str:
    return (TODAY + timedelta(days=days)).isoformat()


def make_supplier(client, name="TechCorp", **extra):
    r = client.post("/api/suppliers", json={"name": name, **extra}, headers=SOURCING_MANAGER)
    assert r.status_code == 201, r.text
    return r.json()


def make_contract(client, supplier_id, reference="FA-2026-001", valid_from=-30, valid_to=300, status="ACTIVE"):
    r = client.post(
        "/api/framework-contracts",
        json={
            "supplier_id": supplier_id,
            "reference": reference,
            "valid_from": d(valid_from),
            "valid_to": d(valid_to),
            "status": status,
        },
        headers=SOURCING_MANAGER,
    )
    assert r.status_code == 201, r.text
    return r.json()


def get_supplier(client, supplier_id):
    return client.get(f"/api/suppliers/{supplier_id}").json()


# ---------- suppliers ----------

def test_sourcing_manager_can_create_supplier(client):
    s = make_supplier(client)
    assert s["name"] == "TechCorp"
    assert s["active"] is True
    assert len(s["id"]) == 36  # generated supplier ID (UUID)
    assert s["contracts"] == []


def test_other_roles_cannot_change_suppliers_or_contracts(client):
    r = client.post("/api/suppliers", json={"name": "TechCorp"}, headers=HIRING_MANAGER)
    assert r.status_code == 403
    s = make_supplier(client)
    assert client.patch(f"/api/suppliers/{s['id']}", json={"name": "X"}, headers=HIRING_MANAGER).status_code == 403
    assert client.post(f"/api/suppliers/{s['id']}/deactivate", headers=HIRING_MANAGER).status_code == 403
    body = {"supplier_id": s["id"], "reference": "FA-1", "valid_from": d(0), "valid_to": d(10)}
    assert client.post("/api/framework-contracts", json=body, headers=HIRING_MANAGER).status_code == 403
    c = make_contract(client, s["id"])
    assert client.post(f"/api/framework-contracts/{c['id']}/terminate", headers=HIRING_MANAGER).status_code == 403
    assert client.patch(f"/api/framework-contracts/{c['id']}", json={"reference": "Z"}, headers=HIRING_MANAGER).status_code == 403


def test_other_roles_can_read(client):
    s = make_supplier(client)
    assert client.get("/api/suppliers", headers=HIRING_MANAGER).status_code == 200
    assert client.get(f"/api/suppliers/{s['id']}", headers=HIRING_MANAGER).status_code == 200
    assert client.get("/api/framework-contracts", headers=HIRING_MANAGER).status_code == 200


def test_supplier_id_can_be_taken_over_from_group_7(client):
    s = make_supplier(client, "Supplier From G7", supplier_id="sup-01")
    assert s["id"] == "sup-01"
    r = client.post("/api/suppliers", json={"name": "Other", "supplier_id": "sup-01"}, headers=SOURCING_MANAGER)
    assert r.status_code == 409
    for bad in ["has space", "../x", "a/b", "-start"]:
        r = client.post("/api/suppliers", json={"name": "Other", "supplier_id": bad}, headers=SOURCING_MANAGER)
        assert r.status_code == 422, bad
    assert get_supplier(client, "sup-01")["name"] == "Supplier From G7"


def test_duplicate_name_is_rejected_case_insensitive(client):
    make_supplier(client, "TechCorp")
    r = client.post("/api/suppliers", json={"name": "techcorp"}, headers=SOURCING_MANAGER)
    assert r.status_code == 409


def test_empty_name_is_rejected(client):
    r = client.post("/api/suppliers", json={"name": "  "}, headers=SOURCING_MANAGER)
    assert r.status_code == 422


def test_rename_supplier(client):
    s = make_supplier(client)
    other = make_supplier(client, "Other GmbH")
    r = client.patch(f"/api/suppliers/{s['id']}", json={"name": "TechCorp AG"}, headers=SOURCING_MANAGER)
    assert r.json()["name"] == "TechCorp AG"
    r = client.patch(f"/api/suppliers/{s['id']}", json={"name": other["name"]}, headers=SOURCING_MANAGER)
    assert r.status_code == 409


def test_deactivate_and_activate_supplier(client):
    s = make_supplier(client)
    r = client.post(f"/api/suppliers/{s['id']}/deactivate", headers=SOURCING_MANAGER)
    assert r.json()["active"] is False
    assert client.get("/api/suppliers?active=true").json() == []
    r = client.post(f"/api/suppliers/{s['id']}/activate", headers=SOURCING_MANAGER)
    assert r.json()["active"] is True


def test_unknown_ids_return_404(client):
    assert client.get("/api/suppliers/nope").status_code == 404
    assert client.patch("/api/suppliers/nope", json={"name": "x"}, headers=SOURCING_MANAGER).status_code == 404
    assert client.get("/api/framework-contracts/nope").status_code == 404
    assert client.post("/api/framework-contracts/nope/terminate", headers=SOURCING_MANAGER).status_code == 404
    body = {"supplier_id": "nope", "reference": "FA-1", "valid_from": d(0), "valid_to": d(10)}
    assert client.post("/api/framework-contracts", json=body, headers=SOURCING_MANAGER).status_code == 404


# ---------- framework contracts ----------

def test_contract_has_reference_dates_and_status(client):
    s = make_supplier(client)
    c = make_contract(client, s["id"])
    assert c["reference"] == "FA-2026-001"
    assert c["valid_from"] == d(-30)
    assert c["valid_to"] == d(300)
    assert c["status"] == "ACTIVE"


def test_valid_to_before_valid_from_is_rejected(client):
    s = make_supplier(client)
    body = {"supplier_id": s["id"], "reference": "FA-1", "valid_from": d(10), "valid_to": d(0)}
    assert client.post("/api/framework-contracts", json=body, headers=SOURCING_MANAGER).status_code == 422


def test_same_reference_is_allowed_for_different_suppliers(client):
    # Group 7: one framework contract (fc-2027) with many participating suppliers
    a = make_supplier(client, "A")
    b = make_supplier(client, "B")
    make_contract(client, a["id"], reference="fc-2027")
    body = {"supplier_id": b["id"], "reference": "fc-2027", "valid_from": d(0), "valid_to": d(10)}
    assert client.post("/api/framework-contracts", json=body, headers=SOURCING_MANAGER).status_code == 201


def test_duplicate_reference_for_same_supplier_is_rejected(client):
    a = make_supplier(client, "A")
    make_contract(client, a["id"], reference="FA-1")
    body = {"supplier_id": a["id"], "reference": "fa-1", "valid_from": d(50), "valid_to": d(60)}
    assert client.post("/api/framework-contracts", json=body, headers=SOURCING_MANAGER).status_code == 409


def test_contract_title_can_be_set_changed_and_removed(client):
    s = make_supplier(client)
    body = {"supplier_id": s["id"], "reference": "fc-2027", "title": "  IT Experts 2027 ", "valid_from": d(0), "valid_to": d(10)}
    c = client.post("/api/framework-contracts", json=body, headers=SOURCING_MANAGER).json()
    assert c["title"] == "IT Experts 2027"
    r = client.patch(f"/api/framework-contracts/{c['id']}", json={"title": "New"}, headers=SOURCING_MANAGER)
    assert r.json()["title"] == "New"
    r = client.patch(f"/api/framework-contracts/{c['id']}", json={"title": ""}, headers=SOURCING_MANAGER)
    assert r.json()["title"] is None


def test_new_contract_defaults_to_draft(client):
    s = make_supplier(client)
    body = {"supplier_id": s["id"], "reference": "FA-1", "valid_from": d(-5), "valid_to": d(100)}
    r = client.post("/api/framework-contracts", json=body, headers=SOURCING_MANAGER)
    assert r.json()["status"] == "DRAFT"


def test_expired_contract_is_shown_as_expired_automatically(client):
    s = make_supplier(client)
    make_contract(client, s["id"], valid_from=-400, valid_to=-1)  # ended yesterday, nobody touched it
    c = get_supplier(client, s["id"])["contracts"][0]
    assert c["status"] == "EXPIRED"


def test_contract_that_has_not_started_is_scheduled(client):
    s = make_supplier(client)
    make_contract(client, s["id"], valid_from=5, valid_to=100)
    assert get_supplier(client, s["id"])["contracts"][0]["status"] == "SCHEDULED"


def test_contract_valid_on_last_day_is_still_active(client):
    s = make_supplier(client)
    make_contract(client, s["id"], valid_from=-10, valid_to=0)
    assert get_supplier(client, s["id"])["contracts"][0]["status"] == "ACTIVE"


def test_activate_and_terminate_contract(client):
    s = make_supplier(client)
    c = make_contract(client, s["id"], status="DRAFT")
    assert client.post(f"/api/framework-contracts/{c['id']}/activate", headers=SOURCING_MANAGER).json()["status"] == "ACTIVE"
    assert client.post(f"/api/framework-contracts/{c['id']}/terminate", headers=SOURCING_MANAGER).json()["status"] == "TERMINATED"
    r = client.post(f"/api/framework-contracts/{c['id']}/activate", headers=SOURCING_MANAGER)
    assert r.status_code == 409
    r = client.patch(f"/api/framework-contracts/{c['id']}", json={"reference": "NEW"}, headers=SOURCING_MANAGER)
    assert r.status_code == 409


def test_update_contract_dates_and_reference(client):
    s = make_supplier(client)
    c = make_contract(client, s["id"])
    r = client.patch(
        f"/api/framework-contracts/{c['id']}",
        json={"reference": "FA-2026-001-B", "valid_to": d(500)},
        headers=SOURCING_MANAGER,
    )
    assert r.status_code == 200
    assert r.json()["reference"] == "FA-2026-001-B"
    assert r.json()["valid_to"] == d(500)
    r = client.patch(f"/api/framework-contracts/{c['id']}", json={"valid_to": d(-100)}, headers=SOURCING_MANAGER)
    assert r.status_code == 422


def test_supplier_cannot_have_two_overlapping_active_contracts(client):
    s = make_supplier(client)
    make_contract(client, s["id"], reference="FA-1", valid_from=-30, valid_to=100)
    body = {"supplier_id": s["id"], "reference": "FA-2", "valid_from": d(50), "valid_to": d(200), "status": "ACTIVE"}
    assert client.post("/api/framework-contracts", json=body, headers=SOURCING_MANAGER).status_code == 409
    # a draft may overlap, but cannot be activated while the other one is active
    body["status"] = "DRAFT"
    draft = client.post("/api/framework-contracts", json=body, headers=SOURCING_MANAGER).json()
    assert client.post(f"/api/framework-contracts/{draft['id']}/activate", headers=SOURCING_MANAGER).status_code == 409
    # a contract that starts after the first one ends is fine (renewal)
    make_contract(client, s["id"], reference="FA-3", valid_from=101, valid_to=400)


# ---------- who can receive requests ----------

def test_supplier_without_contract_is_not_selectable(client):
    s = make_supplier(client)
    assert s["selectable"] is False
    assert s["not_selectable_reason"] == "No framework contract"


def test_supplier_with_valid_contract_is_selectable(client):
    s = make_supplier(client)
    make_contract(client, s["id"])
    s = get_supplier(client, s["id"])
    assert s["selectable"] is True
    assert s["not_selectable_reason"] is None
    assert s["current_contract"]["reference"] == "FA-2026-001"


def test_reasons_for_not_selectable(client):
    draft = make_supplier(client, "Draft Ltd")
    make_contract(client, draft["id"], reference="D-1", status="DRAFT")
    expired = make_supplier(client, "Expired Ltd")
    make_contract(client, expired["id"], reference="E-1", valid_from=-400, valid_to=-1)
    future = make_supplier(client, "Future Ltd")
    make_contract(client, future["id"], reference="F-1", valid_from=10, valid_to=100)
    ended = make_supplier(client, "Terminated Ltd")
    c = make_contract(client, ended["id"], reference="T-1")
    client.post(f"/api/framework-contracts/{c['id']}/terminate", headers=SOURCING_MANAGER)
    inactive = make_supplier(client, "Inactive Ltd")
    make_contract(client, inactive["id"], reference="I-1")
    client.post(f"/api/suppliers/{inactive['id']}/deactivate", headers=SOURCING_MANAGER)

    reasons = {s["name"]: s["not_selectable_reason"] for s in client.get("/api/suppliers").json()}
    assert reasons["Draft Ltd"] == "Framework contract is still a draft"
    assert reasons["Expired Ltd"] == "Framework contract has expired"
    assert reasons["Future Ltd"] == "Framework contract has not started yet"
    assert reasons["Terminated Ltd"] == "Framework contract was terminated"
    assert reasons["Inactive Ltd"] == "Supplier is deactivated"


def test_list_filter_selectable(client):
    good = make_supplier(client, "Good Ltd")
    make_contract(client, good["id"], reference="G-1")
    make_supplier(client, "No Contract Ltd")
    expired = make_supplier(client, "Expired Ltd")
    make_contract(client, expired["id"], reference="E-1", valid_from=-400, valid_to=-1)

    only_good = client.get("/api/suppliers?selectable=true").json()
    assert [s["name"] for s in only_good] == ["Good Ltd"]
    not_good = client.get("/api/suppliers?selectable=false").json()
    assert {s["name"] for s in not_good} == {"No Contract Ltd", "Expired Ltd"}


def test_deactivated_supplier_with_valid_contract_is_not_selectable(client):
    s = make_supplier(client)
    make_contract(client, s["id"])
    client.post(f"/api/suppliers/{s['id']}/deactivate", headers=SOURCING_MANAGER)
    assert client.get("/api/suppliers?selectable=true").json() == []


def test_list_contracts_by_supplier(client):
    a = make_supplier(client, "A")
    b = make_supplier(client, "B")
    make_contract(client, a["id"], reference="A-1")
    make_contract(client, b["id"], reference="B-1")
    refs = [c["reference"] for c in client.get(f"/api/framework-contracts?supplier_id={a['id']}").json()]
    assert refs == ["A-1"]


# ---------- audit trail ----------

def test_audit_trail_records_every_change(client):
    s = make_supplier(client)
    c = make_contract(client, s["id"], status="DRAFT")
    client.patch(f"/api/framework-contracts/{c['id']}", json={"valid_to": d(400)}, headers=SOURCING_MANAGER)
    client.post(f"/api/framework-contracts/{c['id']}/activate", headers=SOURCING_MANAGER)
    client.post(f"/api/framework-contracts/{c['id']}/terminate", headers=SOURCING_MANAGER)
    client.post(f"/api/suppliers/{s['id']}/deactivate", headers=SOURCING_MANAGER)

    entries = client.get("/api/audit-log?entity=supplier&entity=framework_contract", headers=SOURCING_MANAGER).json()
    assert [(e["entity"], e["action"]) for e in entries] == [
        ("supplier", "DEACTIVATE"),
        ("framework_contract", "TERMINATE"),
        ("framework_contract", "ACTIVATE"),
        ("framework_contract", "UPDATE"),
        ("framework_contract", "CREATE"),
        ("supplier", "CREATE"),
    ]
    assert all(e["actor"] == "Anna" for e in entries)
    update = next(e for e in entries if e["action"] == "UPDATE")
    assert "valid_to" in update["detail"]


def test_audit_log_entity_filter_separates_stories(client):
    make_supplier(client)
    client.post("/api/role-categories", json={"name": "Development"}, headers=SOURCING_MANAGER)
    only_roles = client.get("/api/audit-log?entity=role_category", headers=SOURCING_MANAGER).json()
    assert [e["entity"] for e in only_roles] == ["role_category"]
    assert len(client.get("/api/audit-log", headers=SOURCING_MANAGER).json()) == 2
