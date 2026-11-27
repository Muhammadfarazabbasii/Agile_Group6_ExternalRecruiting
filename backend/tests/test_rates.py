"""US-04: maximum daily rate per contract version, role and seniority level.

Covers: uniqueness (API and database), mandatory fields and rate > 0, locking of ACTIVE and SUPERSEDED versions,
the lookup 'max rate for version + role + level' (missing = not allowed), role permissions and the audit trail.
"""
from datetime import date, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.models import ContractRate
from app.schemas_versions import RateIn
from tests.conftest import HIRING_MANAGER, SOURCING_MANAGER

TODAY = date.today()


def d(days: int) -> str:
    return (TODAY + timedelta(days=days)).isoformat()


# ---------- unit tests: validation of one rate (no database) ----------

def valid(**changes):
    data = {"role_id": "r-1", "seniority": "SENIOR", "max_daily_rate": 900, "currency": "EUR"}
    data.update(changes)
    return data


def test_a_complete_rate_is_accepted():
    RateIn(**valid())


@pytest.mark.parametrize("missing", ["role_id", "seniority", "max_daily_rate", "currency"])
def test_every_field_is_mandatory(missing):
    data = valid()
    del data[missing]
    with pytest.raises(ValidationError):
        RateIn(**data)


@pytest.mark.parametrize("amount", [0, -1, -0.01, 100001])
def test_rate_must_be_above_zero_and_not_absurd(amount):
    with pytest.raises(ValidationError):
        RateIn(**valid(max_daily_rate=amount))


@pytest.mark.parametrize("currency", ["USD", "eur", "", None])
def test_only_the_agreed_currency_is_accepted(currency):
    with pytest.raises(ValidationError):
        RateIn(**valid(currency=currency))


@pytest.mark.parametrize("seniority", ["INTERN", "junior", ""])
def test_unknown_seniority_is_refused(seniority):
    with pytest.raises(ValidationError):
        RateIn(**valid(seniority=seniority))


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


@pytest.fixture()
def draft(client, contract):
    r = client.post(f"/api/framework-contracts/{contract['id']}/versions", json={}, headers=SOURCING_MANAGER)
    return r.json()


def rate_body(role_id, seniority="SENIOR", amount=900, currency="EUR"):
    return {"role_id": role_id, "seniority": seniority, "max_daily_rate": amount, "currency": currency}


def add_rate(client, version_id, body, headers=SOURCING_MANAGER):
    return client.post(f"/api/contract-versions/{version_id}/rates", json=body, headers=headers)


def rate_ids(client, version_id):
    return {(r["role_id"], r["seniority"]): r for r in client.get(f"/api/contract-versions/{version_id}/rates").json()}


def rate_row_id(draft_id, role_id, seniority):
    with SessionLocal() as db:
        return db.query(ContractRate).filter_by(
            contract_version_id=draft_id, role_id=role_id, seniority_code=seniority
        ).one().id


def move(client, version_id, status):
    r = client.post(f"/api/contract-versions/{version_id}/status", json={"status": status}, headers=SOURCING_MANAGER)
    assert r.status_code == 200, r.text
    return r


def locked_version(client, contract, roles, which):
    """Returns a version that is ACTIVE or SUPERSEDED, with one rate for Backend / SENIOR."""
    first = client.post(f"/api/framework-contracts/{contract['id']}/versions", json={}, headers=SOURCING_MANAGER).json()
    assert add_rate(client, first["id"], rate_body(roles["Backend"])).status_code == 201
    move(client, first["id"], "ACTIVE")
    if which == "ACTIVE":
        return first
    second = client.post(f"/api/framework-contracts/{contract['id']}/versions", json={}, headers=SOURCING_MANAGER).json()
    move(client, second["id"], "ACTIVE")  # supersedes the first one
    return client.get(f"/api/contract-versions/{first['id']}").json()


# ---------- uniqueness: one rate per version + role + level ----------

def test_one_rate_per_role_and_level_in_a_version(client, draft, roles):
    assert add_rate(client, draft["id"], rate_body(roles["Backend"])).status_code == 201
    r = add_rate(client, draft["id"], rate_body(roles["Backend"], amount=950))
    assert r.status_code == 409
    assert "already exists" in r.json()["detail"]
    assert len(client.get(f"/api/contract-versions/{draft['id']}/rates").json()) == 1


def test_same_role_at_another_level_is_allowed(client, draft, roles):
    assert add_rate(client, draft["id"], rate_body(roles["Backend"], "SENIOR")).status_code == 201
    assert add_rate(client, draft["id"], rate_body(roles["Backend"], "EXPERT", 1200)).status_code == 201


def test_same_role_and_level_is_allowed_in_another_version(client, contract, draft, roles):
    assert add_rate(client, draft["id"], rate_body(roles["Backend"])).status_code == 201
    second = client.post(f"/api/framework-contracts/{contract['id']}/versions", json={}, headers=SOURCING_MANAGER).json()
    assert add_rate(client, second["id"], rate_body(roles["Backend"])).status_code == 201


def test_bulk_save_refuses_a_duplicate_role_and_level(client, draft, roles):
    body = {
        "rates": [rate_body(roles["Backend"]), rate_body(roles["Backend"], amount=1000)],
    }
    r = client.put(f"/api/contract-versions/{draft['id']}/rates", json=body, headers=SOURCING_MANAGER)
    assert r.status_code == 422


def test_database_refuses_a_second_rate_for_the_same_role_and_level(client, draft, roles):
    """The database enforces uniqueness too, not only the API."""
    assert add_rate(client, draft["id"], rate_body(roles["Backend"])).status_code == 201
    with SessionLocal() as db:
        db.add(
            ContractRate(
                contract_version_id=draft["id"],
                role_id=roles["Backend"],
                seniority_code="SENIOR",
                max_daily_rate=1000,
                currency="EUR",
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()


# ---------- mandatory fields and value checks (API) ----------

def test_missing_currency_is_refused(client, draft, roles):
    body = rate_body(roles["Backend"])
    del body["currency"]
    assert add_rate(client, draft["id"], body).status_code == 422


def test_missing_rate_is_refused(client, draft, roles):
    body = rate_body(roles["Backend"])
    del body["max_daily_rate"]
    assert add_rate(client, draft["id"], body).status_code == 422


@pytest.mark.parametrize("amount", [0, -50])
def test_rate_zero_or_negative_is_refused(client, draft, roles, amount):
    assert add_rate(client, draft["id"], rate_body(roles["Backend"], amount=amount)).status_code == 422


def test_unknown_currency_is_refused(client, draft, roles):
    assert add_rate(client, draft["id"], rate_body(roles["Backend"], currency="USD")).status_code == 422


def test_unknown_role_is_refused(client, draft):
    assert add_rate(client, draft["id"], rate_body("no-such-role")).status_code == 422


def test_deactivated_role_cannot_get_a_rate(client, draft, roles):
    client.post(f"/api/roles/{roles['Frontend']}/deactivate", headers=SOURCING_MANAGER)
    r = add_rate(client, draft["id"], rate_body(roles["Frontend"]))
    assert r.status_code == 422
    assert "deactivated" in r.json()["detail"]


def test_patch_needs_a_valid_change(client, draft, roles):
    add_rate(client, draft["id"], rate_body(roles["Backend"]))
    rid = rate_row_id(draft["id"], roles["Backend"], "SENIOR")
    assert client.patch(f"/api/contract-rates/{rid}", json={}, headers=SOURCING_MANAGER).status_code == 422
    assert client.patch(f"/api/contract-rates/{rid}", json={"max_daily_rate": 0}, headers=SOURCING_MANAGER).status_code == 422
    assert client.patch(f"/api/contract-rates/{rid}", json={"currency": "USD"}, headers=SOURCING_MANAGER).status_code == 422
    assert client.get(f"/api/contract-rates/{rid}").json()["max_daily_rate"] == 900


# ---------- CRUD ----------

def test_create_read_change_and_delete_a_rate(client, draft, roles):
    assert add_rate(client, draft["id"], rate_body(roles["Backend"])).status_code == 201
    rid = rate_row_id(draft["id"], roles["Backend"], "SENIOR")

    one = client.get(f"/api/contract-rates/{rid}").json()
    assert (one["max_daily_rate"], one["currency"], one["role_name"]) == (900, "EUR", "Backend")

    changed = client.patch(f"/api/contract-rates/{rid}", json={"max_daily_rate": 950}, headers=SOURCING_MANAGER)
    assert changed.status_code == 200 and changed.json()["max_daily_rate"] == 950

    assert client.delete(f"/api/contract-rates/{rid}", headers=SOURCING_MANAGER).status_code == 204
    assert client.get(f"/api/contract-rates/{rid}").status_code == 404


def test_deleting_a_rate_makes_the_combination_not_allowed(client, draft, roles):
    add_rate(client, draft["id"], rate_body(roles["Backend"]))
    rid = rate_row_id(draft["id"], roles["Backend"], "SENIOR")
    client.delete(f"/api/contract-rates/{rid}", headers=SOURCING_MANAGER)
    r = client.get(
        f"/api/contract-versions/{draft['id']}/max-rate",
        params={"role_id": roles["Backend"], "seniority": "SENIOR"},
    )
    assert r.status_code == 404


def test_unknown_rate_id_gives_404(client):
    assert client.get("/api/contract-rates/nope").status_code == 404
    assert client.patch("/api/contract-rates/nope", json={"max_daily_rate": 1}, headers=SOURCING_MANAGER).status_code == 404
    assert client.delete("/api/contract-rates/nope", headers=SOURCING_MANAGER).status_code == 404


# ---------- lookup: max rate for version + role + level ----------

def test_lookup_returns_the_max_rate(client, draft, roles):
    add_rate(client, draft["id"], rate_body(roles["Backend"], "EXPERT", 1200))
    r = client.get(
        f"/api/contract-versions/{draft['id']}/max-rate",
        params={"role_id": roles["Backend"], "seniority": "EXPERT"},
    )
    assert r.status_code == 200
    assert r.json()["max_daily_rate"] == 1200
    assert r.json()["currency"] == "EUR"


def test_lookup_for_a_missing_combination_says_not_allowed(client, draft, roles):
    add_rate(client, draft["id"], rate_body(roles["Backend"]))
    r = client.get(
        f"/api/contract-versions/{draft['id']}/max-rate",
        params={"role_id": roles["Frontend"], "seniority": "JUNIOR"},
    )
    assert r.status_code == 404
    assert "not allowed" in r.json()["detail"].lower()


def test_lookup_rejects_an_unknown_level(client, draft, roles):
    r = client.get(
        f"/api/contract-versions/{draft['id']}/max-rate",
        params={"role_id": roles["Backend"], "seniority": "INTERN"},
    )
    assert r.status_code == 422


def test_lookup_of_an_unknown_version_gives_404(client, roles):
    r = client.get("/api/contract-versions/nope/max-rate", params={"role_id": roles["Backend"], "seniority": "SENIOR"})
    assert r.status_code == 404


# ---------- locking: ACTIVE and SUPERSEDED rates cannot change ----------

@pytest.mark.parametrize("which", ["ACTIVE", "SUPERSEDED"])
def test_rates_of_a_locked_version_cannot_be_added_changed_or_deleted(client, contract, roles, which):
    version = locked_version(client, contract, roles, which)
    rid = rate_row_id(version["id"], roles["Backend"], "SENIOR")

    add = add_rate(client, version["id"], rate_body(roles["Frontend"]))
    assert add.status_code == 409
    assert which in add.json()["detail"]

    patch = client.patch(f"/api/contract-rates/{rid}", json={"max_daily_rate": 1}, headers=SOURCING_MANAGER)
    assert patch.status_code == 409

    delete = client.delete(f"/api/contract-rates/{rid}", headers=SOURCING_MANAGER)
    assert delete.status_code == 409

    bulk = client.put(
        f"/api/contract-versions/{version['id']}/rates",
        json={"rates": [rate_body(roles["Frontend"])]},
        headers=SOURCING_MANAGER,
    )
    assert bulk.status_code == 409


@pytest.mark.parametrize("which", ["ACTIVE", "SUPERSEDED"])
def test_rates_of_a_locked_version_stay_readable(client, contract, roles, which):
    version = locked_version(client, contract, roles, which)
    assert client.get(f"/api/contract-versions/{version['id']}/rates").status_code == 200
    rid = rate_row_id(version["id"], roles["Backend"], "SENIOR")
    assert client.get(f"/api/contract-rates/{rid}").json()["max_daily_rate"] == 900
    lookup = client.get(
        f"/api/contract-versions/{version['id']}/max-rate",
        params={"role_id": roles["Backend"], "seniority": "SENIOR"},
    )
    assert lookup.status_code == 200


def test_rates_can_change_while_draft_or_in_negotiation(client, draft, roles):
    add_rate(client, draft["id"], rate_body(roles["Backend"]))
    rid = rate_row_id(draft["id"], roles["Backend"], "SENIOR")
    assert client.patch(f"/api/contract-rates/{rid}", json={"max_daily_rate": 800}, headers=SOURCING_MANAGER).status_code == 200
    move(client, draft["id"], "IN_NEGOTIATION")
    assert client.patch(f"/api/contract-rates/{rid}", json={"max_daily_rate": 700}, headers=SOURCING_MANAGER).status_code == 200
    assert client.delete(f"/api/contract-rates/{rid}", headers=SOURCING_MANAGER).status_code == 204


# ---------- role permissions ----------

def test_only_the_sourcing_manager_can_change_rates(client, draft, roles):
    add_rate(client, draft["id"], rate_body(roles["Backend"]))
    rid = rate_row_id(draft["id"], roles["Backend"], "SENIOR")

    assert add_rate(client, draft["id"], rate_body(roles["Frontend"]), headers=HIRING_MANAGER).status_code == 403
    assert client.patch(f"/api/contract-rates/{rid}", json={"max_daily_rate": 1}, headers=HIRING_MANAGER).status_code == 403
    assert client.delete(f"/api/contract-rates/{rid}", headers=HIRING_MANAGER).status_code == 403
    bulk = client.put(
        f"/api/contract-versions/{draft['id']}/rates",
        json={"rates": []},
        headers=HIRING_MANAGER,
    )
    assert bulk.status_code == 403


def test_everyone_can_read_rates_and_the_lookup(client, draft, roles):
    add_rate(client, draft["id"], rate_body(roles["Backend"]))
    rid = rate_row_id(draft["id"], roles["Backend"], "SENIOR")
    assert client.get(f"/api/contract-versions/{draft['id']}/rates", headers=HIRING_MANAGER).status_code == 200
    assert client.get(f"/api/contract-rates/{rid}", headers=HIRING_MANAGER).status_code == 200
    r = client.get(
        f"/api/contract-versions/{draft['id']}/max-rate",
        params={"role_id": roles["Backend"], "seniority": "SENIOR"},
        headers=HIRING_MANAGER,
    )
    assert r.status_code == 200


# ---------- audit trail ----------

def rate_audit(client):
    return client.get("/api/audit-log?entity=contract_version", headers=SOURCING_MANAGER).json()


def test_every_rate_change_is_in_the_audit_trail(client, draft, roles):
    add_rate(client, draft["id"], rate_body(roles["Backend"]))
    rid = rate_row_id(draft["id"], roles["Backend"], "SENIOR")
    client.patch(f"/api/contract-rates/{rid}", json={"max_daily_rate": 950}, headers=SOURCING_MANAGER)
    client.delete(f"/api/contract-rates/{rid}", headers=SOURCING_MANAGER)

    entries = [e for e in rate_audit(client) if e["action"].startswith("RATE_")]
    assert [e["action"] for e in entries] == ["RATE_DELETE", "RATE_CHANGE", "RATE_ADD"]
    assert "900 EUR -> " in next(e for e in entries if e["action"] == "RATE_CHANGE")["detail"]
    assert all(e["actor"] == "Anna" for e in entries)
