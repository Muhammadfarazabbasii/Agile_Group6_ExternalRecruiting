"""US-03: contract versions (negotiation rounds) with rates, status transitions, the one-ACTIVE rule and comparison."""
from datetime import date, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app import version_rules as rules
from app.database import SessionLocal
from app.models import ContractVersion
from tests.conftest import HIRING_MANAGER, SOURCING_MANAGER

TODAY = date.today()


def d(days: int) -> str:
    return (TODAY + timedelta(days=days)).isoformat()


# ---------- unit tests: status rules (no database) ----------

@pytest.mark.parametrize(
    "current,target,allowed",
    [
        ("DRAFT", "IN_NEGOTIATION", True),
        ("DRAFT", "ACTIVE", True),
        ("DRAFT", "DRAFT", False),
        ("DRAFT", "SUPERSEDED", False),
        ("IN_NEGOTIATION", "ACTIVE", True),
        ("IN_NEGOTIATION", "DRAFT", False),
        ("IN_NEGOTIATION", "IN_NEGOTIATION", False),
        ("IN_NEGOTIATION", "SUPERSEDED", False),
        ("ACTIVE", "IN_NEGOTIATION", False),
        ("ACTIVE", "DRAFT", False),
        ("ACTIVE", "ACTIVE", False),
        ("ACTIVE", "SUPERSEDED", False),  # only happens when a newer version is activated
        ("SUPERSEDED", "ACTIVE", False),  # superseded is final
        ("SUPERSEDED", "IN_NEGOTIATION", False),
        ("SUPERSEDED", "SUPERSEDED", False),
        ("UNKNOWN", "ACTIVE", False),
    ],
)
def test_transition_table(current, target, allowed):
    assert rules.can_transition(current, target) is allowed
    assert (rules.transition_error(current, target) is None) is allowed


def test_transition_errors_explain_the_reason():
    assert "superseded" in rules.transition_error("SUPERSEDED", "ACTIVE").lower()
    assert "newer version" in rules.transition_error("ACTIVE", "IN_NEGOTIATION")
    assert rules.transition_error("ACTIVE", "ACTIVE") is not None
    assert rules.transition_error("DRAFT", "IN_NEGOTIATION") is None


@pytest.mark.parametrize("status,editable", [("DRAFT", True), ("IN_NEGOTIATION", True), ("ACTIVE", False), ("SUPERSEDED", False)])
def test_only_draft_and_negotiation_versions_are_editable(status, editable):
    assert rules.is_editable(status) is editable


# ---------- API helpers ----------

@pytest.fixture()
def roles(client):
    cat = client.post("/api/role-categories", json={"name": "Development"}, headers=SOURCING_MANAGER).json()
    backend = client.post("/api/roles", json={"category_id": cat["id"], "name": "Backend"}, headers=SOURCING_MANAGER).json()
    frontend = client.post("/api/roles", json={"category_id": cat["id"], "name": "Frontend"}, headers=SOURCING_MANAGER).json()
    return {"Backend": backend["id"], "Frontend": frontend["id"]}


@pytest.fixture()
def contract(client):
    s = client.post("/api/suppliers", json={"name": "TechCorp"}, headers=SOURCING_MANAGER).json()
    body = {"supplier_id": s["id"], "reference": "fc-2027", "valid_from": d(-30), "valid_to": d(300)}
    return client.post("/api/framework-contracts", json=body, headers=SOURCING_MANAGER).json()


def new_version(client, contract_id, headers=SOURCING_MANAGER, **body):
    return client.post(f"/api/framework-contracts/{contract_id}/versions", json=body, headers=headers)


def move(client, version_id, status, headers=SOURCING_MANAGER):
    return client.post(f"/api/contract-versions/{version_id}/status", json={"status": status}, headers=headers)


def put_rates(client, version_id, rates, cap=None, headers=SOURCING_MANAGER):
    return client.put(
        f"/api/contract-versions/{version_id}/rates",
        json={"travel_surcharge_cap": cap, "rates": rates},
        headers=headers,
    )


def rate(role_id, seniority, amount):
    return {"role_id": role_id, "seniority": seniority, "max_daily_rate": amount}


def audit(client):
    return client.get("/api/audit-log?entity=contract_version", headers=SOURCING_MANAGER).json()


# ---------- creating versions ----------

def test_first_version_is_number_1_draft_and_dated_today(client, contract):
    r = new_version(client, contract["id"])
    assert r.status_code == 201, r.text
    v = r.json()
    assert v["version_number"] == 1
    assert v["status"] == "DRAFT"
    assert v["version_date"] == TODAY.isoformat()
    assert v["rates"] == []
    assert v["editable"] is True


def test_versions_are_numbered_in_order_and_listed_oldest_first(client, contract):
    for _ in range(3):
        assert new_version(client, contract["id"]).status_code == 201
    numbers = [v["version_number"] for v in client.get(f"/api/framework-contracts/{contract['id']}/versions").json()]
    assert numbers == [1, 2, 3]


def test_version_can_be_started_as_in_negotiation(client, contract):
    v = new_version(client, contract["id"], status="IN_NEGOTIATION").json()
    assert v["status"] == "IN_NEGOTIATION"


def test_version_cannot_be_created_as_active_or_superseded(client, contract):
    assert new_version(client, contract["id"], status="ACTIVE").status_code == 422
    assert new_version(client, contract["id"], status="SUPERSEDED").status_code == 422


def test_unknown_contract_gives_404(client):
    assert new_version(client, "nope").status_code == 404
    assert client.get("/api/framework-contracts/nope/versions").status_code == 404


def test_copy_previous_copies_rates_and_travel_cap(client, contract, roles):
    v1 = new_version(client, contract["id"]).json()
    put_rates(client, v1["id"], [rate(roles["Backend"], "SENIOR", 900), rate(roles["Backend"], "JUNIOR", 700)], cap=50)
    r = new_version(client, contract["id"], copy_previous=True)
    assert r.status_code == 201, r.text
    v2 = r.json()
    assert v2["version_number"] == 2
    assert v2["travel_surcharge_cap"] == 50
    assert sorted((x["seniority"], x["max_daily_rate"]) for x in v2["rates"]) == [("JUNIOR", 700), ("SENIOR", 900)]
    assert v2["id"] != v1["id"]
    # the copy is a new starting point: changing it does not change version 1
    put_rates(client, v2["id"], [rate(roles["Backend"], "SENIOR", 850)])
    v1_again = client.get(f"/api/contract-versions/{v1['id']}").json()
    assert sorted((x["seniority"], x["max_daily_rate"]) for x in v1_again["rates"]) == [("JUNIOR", 700), ("SENIOR", 900)]
    assert "copied 2 rate(s) from version 1" in next(e for e in audit(client) if e["action"] == "CREATE" and "version 2" in e["detail"])["detail"]


def test_copy_without_a_previous_version_is_rejected(client, contract):
    r = new_version(client, contract["id"], copy_previous=True)
    assert r.status_code == 409


def test_copy_leaves_out_rates_of_deactivated_roles(client, contract, roles):
    v1 = new_version(client, contract["id"]).json()
    put_rates(client, v1["id"], [rate(roles["Backend"], "SENIOR", 900), rate(roles["Frontend"], "SENIOR", 800)])
    client.post(f"/api/roles/{roles['Frontend']}/deactivate", headers=SOURCING_MANAGER)
    v2 = new_version(client, contract["id"], copy_previous=True).json()
    assert [x["role_name"] for x in v2["rates"]] == ["Backend"]
    assert any("1 skipped because the role is deactivated" in e["detail"] for e in audit(client))


def test_terminated_contract_gets_no_new_versions(client, contract):
    client.post(f"/api/framework-contracts/{contract['id']}/terminate", headers=SOURCING_MANAGER)
    assert new_version(client, contract["id"]).status_code == 409


# ---------- rates ----------

def test_rates_replace_all_previous_rates(client, contract, roles):
    v = new_version(client, contract["id"]).json()
    put_rates(client, v["id"], [rate(roles["Backend"], "SENIOR", 900), rate(roles["Frontend"], "JUNIOR", 500)], cap=40)
    r = put_rates(client, v["id"], [rate(roles["Backend"], "EXPERT", 1100)])
    assert r.status_code == 200, r.text
    body = r.json()
    assert [(x["role_name"], x["seniority"], x["max_daily_rate"]) for x in body["rates"]] == [("Backend", "EXPERT", 1100)]
    assert body["travel_surcharge_cap"] is None  # the cap was not sent this time, so it is cleared


def test_rates_are_validated(client, contract, roles):
    v = new_version(client, contract["id"]).json()
    bad = [
        [rate(roles["Backend"], "SENIOR", 900), rate(roles["Backend"], "SENIOR", 800)],  # same role and level twice
        [rate(roles["Backend"], "SENIOR", 0)],  # not above zero
        [rate(roles["Backend"], "LEAD", 900)],  # unknown seniority level
        [rate("no-such-role", "SENIOR", 900)],  # unknown role
    ]
    for rates in bad:
        assert put_rates(client, v["id"], rates).status_code == 422, rates
    assert put_rates(client, v["id"], [], cap=-5).status_code == 422


def test_deactivated_role_cannot_get_a_rate(client, contract, roles):
    v = new_version(client, contract["id"]).json()
    client.post(f"/api/roles/{roles['Frontend']}/deactivate", headers=SOURCING_MANAGER)
    r = put_rates(client, v["id"], [rate(roles["Frontend"], "SENIOR", 800)])
    assert r.status_code == 422
    assert "deactivated" in r.json()["detail"]


# ---------- status transitions and the one-ACTIVE rule ----------

def test_negotiation_then_activation_follows_the_rules(client, contract):
    v = new_version(client, contract["id"]).json()
    assert move(client, v["id"], "IN_NEGOTIATION").json()["status"] == "IN_NEGOTIATION"
    r = move(client, v["id"], "ACTIVE")
    assert r.status_code == 200
    assert r.json()["status"] == "ACTIVE"
    assert r.json()["editable"] is False


def test_illegal_transitions_are_refused(client, contract):
    v1 = new_version(client, contract["id"]).json()
    move(client, v1["id"], "ACTIVE")
    assert move(client, v1["id"], "IN_NEGOTIATION").status_code == 409  # active cannot go back
    assert move(client, v1["id"], "ACTIVE").status_code == 409  # already active
    v2 = new_version(client, contract["id"], status="IN_NEGOTIATION").json()
    assert move(client, v2["id"], "IN_NEGOTIATION").status_code == 409  # already in negotiation
    assert move(client, v1["id"], "SUPERSEDED").status_code == 422  # a person can never set superseded


def test_activating_a_new_version_supersedes_the_previous_active_one(client, contract):
    v1 = new_version(client, contract["id"]).json()
    move(client, v1["id"], "ACTIVE")
    v2 = new_version(client, contract["id"]).json()
    move(client, v2["id"], "ACTIVE")

    statuses = {v["version_number"]: v["status"] for v in client.get(f"/api/framework-contracts/{contract['id']}/versions").json()}
    assert statuses == {1: "SUPERSEDED", 2: "ACTIVE"}
    assert move(client, v1["id"], "ACTIVE").status_code == 409  # superseded is final

    actions = [(e["action"], e["entity_id"]) for e in audit(client)]
    assert ("SUPERSEDE", v1["id"]) in actions
    assert ("ACTIVATE", v2["id"]) in actions


def test_only_one_active_version_per_contract_at_any_time(client, contract):
    versions = [new_version(client, contract["id"]).json() for _ in range(3)]
    for v in versions:
        assert move(client, v["id"], "ACTIVE").status_code == 200
    active = [v for v in client.get(f"/api/framework-contracts/{contract['id']}/versions").json() if v["status"] == "ACTIVE"]
    assert [v["version_number"] for v in active] == [3]


def test_database_refuses_a_second_active_version(client, contract):
    """The rule is also enforced by the database (partial unique index), not only by the code."""
    v = new_version(client, contract["id"]).json()
    move(client, v["id"], "ACTIVE")
    with SessionLocal() as db:
        db.add(ContractVersion(framework_contract_id=contract["id"], version_number=99, version_date=TODAY, status="ACTIVE"))
        with pytest.raises(IntegrityError):
            db.commit()


def test_versions_of_different_contracts_can_each_be_active(client, contract):
    s = client.post("/api/suppliers", json={"name": "Other GmbH"}, headers=SOURCING_MANAGER).json()
    other = client.post(
        "/api/framework-contracts",
        json={"supplier_id": s["id"], "reference": "fc-2027", "valid_from": d(-30), "valid_to": d(300)},
        headers=SOURCING_MANAGER,
    ).json()
    a = new_version(client, contract["id"]).json()
    b = new_version(client, other["id"]).json()
    assert move(client, a["id"], "ACTIVE").status_code == 200
    assert move(client, b["id"], "ACTIVE").status_code == 200


# ---------- blocked edits ----------

def test_rates_can_be_edited_while_draft_or_in_negotiation(client, contract, roles):
    v = new_version(client, contract["id"]).json()
    assert put_rates(client, v["id"], [rate(roles["Backend"], "SENIOR", 900)]).status_code == 200
    move(client, v["id"], "IN_NEGOTIATION")
    assert put_rates(client, v["id"], [rate(roles["Backend"], "SENIOR", 880)]).status_code == 200


def test_active_and_superseded_versions_cannot_be_edited(client, contract, roles):
    v1 = new_version(client, contract["id"]).json()
    put_rates(client, v1["id"], [rate(roles["Backend"], "SENIOR", 900)], cap=50)
    move(client, v1["id"], "ACTIVE")
    r = put_rates(client, v1["id"], [rate(roles["Backend"], "SENIOR", 1)])
    assert r.status_code == 409
    v2 = new_version(client, contract["id"]).json()
    move(client, v2["id"], "ACTIVE")  # version 1 is now SUPERSEDED
    r = put_rates(client, v1["id"], [rate(roles["Backend"], "SENIOR", 1)], cap=1)
    assert r.status_code == 409
    # the old rates are still there and readable
    still = client.get(f"/api/contract-versions/{v1['id']}").json()
    assert still["status"] == "SUPERSEDED"
    assert [x["max_daily_rate"] for x in still["rates"]] == [900]
    assert still["travel_surcharge_cap"] == 50


def test_terminated_contract_versions_cannot_be_activated(client, contract):
    v = new_version(client, contract["id"]).json()
    client.post(f"/api/framework-contracts/{contract['id']}/terminate", headers=SOURCING_MANAGER)
    assert move(client, v["id"], "ACTIVE").status_code == 409


# ---------- compare ----------

def test_compare_shows_added_removed_changed_and_unchanged_rates(client, contract, roles):
    v1 = new_version(client, contract["id"]).json()
    put_rates(client, v1["id"], [rate(roles["Backend"], "SENIOR", 900), rate(roles["Backend"], "JUNIOR", 700)], cap=50)
    v2 = new_version(client, contract["id"], copy_previous=True).json()
    put_rates(
        client, v2["id"],
        [rate(roles["Backend"], "SENIOR", 850), rate(roles["Frontend"], "SENIOR", 800)],
        cap=60,
    )
    r = client.get(
        f"/api/framework-contracts/{contract['id']}/versions/compare",
        params={"from_version": 1, "to_version": 2},
        headers=HIRING_MANAGER,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["from_version"], body["to_version"]) == (1, 2)
    assert (body["travel_surcharge_cap_from"], body["travel_surcharge_cap_to"]) == (50, 60)
    rows = [(x["role_name"], x["seniority"], x["change"], x["from_rate"], x["to_rate"], x["delta"]) for x in body["rows"]]
    assert rows == [
        ("Backend", "JUNIOR", "removed", 700, None, None),
        ("Backend", "SENIOR", "changed", 900, 850, -50),
        ("Frontend", "SENIOR", "added", None, 800, None),
    ]


def test_compare_marks_unchanged_rates(client, contract, roles):
    v1 = new_version(client, contract["id"]).json()
    put_rates(client, v1["id"], [rate(roles["Backend"], "SENIOR", 900)])
    new_version(client, contract["id"], copy_previous=True)
    body = client.get(
        f"/api/framework-contracts/{contract['id']}/versions/compare", params={"from_version": 1, "to_version": 2}
    ).json()
    assert [(x["change"], x["delta"]) for x in body["rows"]] == [("unchanged", 0)]


def test_compare_with_unknown_version_gives_404(client, contract):
    new_version(client, contract["id"])
    r = client.get(f"/api/framework-contracts/{contract['id']}/versions/compare", params={"from_version": 1, "to_version": 5})
    assert r.status_code == 404


def test_single_version_can_be_read_by_id(client, contract):
    v = new_version(client, contract["id"]).json()
    assert client.get(f"/api/contract-versions/{v['id']}").json()["id"] == v["id"]
    assert client.get("/api/contract-versions/nope").status_code == 404


# ---------- role permissions ----------

def test_only_sourcing_manager_can_change_versions(client, contract, roles):
    v = new_version(client, contract["id"]).json()
    assert new_version(client, contract["id"], headers=HIRING_MANAGER).status_code == 403
    assert new_version(client, contract["id"], headers=HIRING_MANAGER, copy_previous=True).status_code == 403
    assert put_rates(client, v["id"], [rate(roles["Backend"], "SENIOR", 900)], headers=HIRING_MANAGER).status_code == 403
    assert move(client, v["id"], "IN_NEGOTIATION", headers=HIRING_MANAGER).status_code == 403
    assert move(client, v["id"], "ACTIVE", headers=HIRING_MANAGER).status_code == 403
    # nothing was changed by the refused requests
    unchanged = client.get(f"/api/contract-versions/{v['id']}").json()
    assert unchanged["status"] == "DRAFT"
    assert unchanged["rates"] == []


def test_everyone_can_read_versions_and_comparison(client, contract, roles):
    v = new_version(client, contract["id"]).json()
    put_rates(client, v["id"], [rate(roles["Backend"], "SENIOR", 900)])
    assert client.get(f"/api/framework-contracts/{contract['id']}/versions", headers=HIRING_MANAGER).status_code == 200
    assert client.get(f"/api/contract-versions/{v['id']}", headers=HIRING_MANAGER).status_code == 200
    r = client.get(
        f"/api/framework-contracts/{contract['id']}/versions/compare",
        params={"from_version": 1, "to_version": 1},
        headers=HIRING_MANAGER,
    )
    assert r.status_code == 200


# ---------- audit trail ----------

def test_every_version_change_is_in_the_audit_trail(client, contract, roles):
    v1 = new_version(client, contract["id"]).json()
    put_rates(client, v1["id"], [rate(roles["Backend"], "SENIOR", 900)], cap=50)
    move(client, v1["id"], "IN_NEGOTIATION")
    move(client, v1["id"], "ACTIVE")
    actions = [e["action"] for e in audit(client)]
    assert actions == ["ACTIVATE", "STATUS", "UPDATE", "CREATE"]
    assert all(e["actor"] == "Anna" for e in audit(client))
