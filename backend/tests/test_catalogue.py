from .conftest import HIRING_MANAGER, SOURCING_MANAGER


def make_category(client, name="Development"):
    r = client.post("/api/role-categories", json={"name": name}, headers=SOURCING_MANAGER)
    assert r.status_code == 201, r.text
    return r.json()


def make_role(client, category_id, name="Java Developer"):
    r = client.post("/api/roles", json={"category_id": category_id, "name": name}, headers=SOURCING_MANAGER)
    assert r.status_code == 201, r.text
    return r.json()


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_seniority_levels_are_fixed_list_in_order(client):
    levels = client.get("/api/seniority-levels").json()
    assert [lvl["code"] for lvl in levels] == ["JUNIOR", "SENIOR", "EXPERT"]


def test_sourcing_manager_can_create_category_and_role(client):
    cat = make_category(client)
    role = make_role(client, cat["id"])
    assert role["category_name"] == "Development"
    assert role["active"] is True


def test_other_roles_cannot_change_catalogue(client):
    r = client.post("/api/role-categories", json={"name": "Development"}, headers=HIRING_MANAGER)
    assert r.status_code == 403
    cat = make_category(client)
    r = client.post("/api/roles", json={"category_id": cat["id"], "name": "QA"}, headers=HIRING_MANAGER)
    assert r.status_code == 403
    r = client.post(f"/api/role-categories/{cat['id']}/deactivate", headers=HIRING_MANAGER)
    assert r.status_code == 403


def test_other_roles_can_read_catalogue(client):
    make_category(client)
    assert client.get("/api/role-categories", headers=HIRING_MANAGER).status_code == 200
    assert client.get("/api/roles", headers=HIRING_MANAGER).status_code == 200


def test_duplicate_category_name_is_rejected_case_insensitive(client):
    make_category(client, "Development")
    r = client.post("/api/role-categories", json={"name": "development"}, headers=SOURCING_MANAGER)
    assert r.status_code == 409


def test_duplicate_role_in_same_category_is_rejected_but_ok_in_other(client):
    dev = make_category(client, "Development")
    other = make_category(client, "Testing")
    make_role(client, dev["id"], "Engineer")
    r = client.post("/api/roles", json={"category_id": dev["id"], "name": "engineer"}, headers=SOURCING_MANAGER)
    assert r.status_code == 409
    make_role(client, other["id"], "Engineer")  # same name in another category is fine


def test_empty_name_is_rejected(client):
    r = client.post("/api/role-categories", json={"name": "   "}, headers=SOURCING_MANAGER)
    assert r.status_code == 422


def test_rename_category_and_role(client):
    cat = make_category(client)
    role = make_role(client, cat["id"])
    r = client.patch(f"/api/role-categories/{cat['id']}", json={"name": "Software"}, headers=SOURCING_MANAGER)
    assert r.json()["name"] == "Software"
    r = client.patch(f"/api/roles/{role['id']}", json={"name": "Backend Developer"}, headers=SOURCING_MANAGER)
    assert r.json()["name"] == "Backend Developer"
    assert r.json()["category_name"] == "Software"


def test_deactivated_role_is_hidden_from_active_list(client):
    cat = make_category(client)
    role = make_role(client, cat["id"])
    r = client.post(f"/api/roles/{role['id']}/deactivate", headers=SOURCING_MANAGER)
    assert r.json()["active"] is False
    assert client.get("/api/roles?active=true").json() == []
    assert len(client.get("/api/roles?active=false").json()) == 1
    assert client.get("/api/catalogue").json()["categories"][0]["roles"] == []


def test_deactivating_category_deactivates_its_roles(client):
    cat = make_category(client)
    make_role(client, cat["id"], "Java Developer")
    make_role(client, cat["id"], "Python Developer")
    r = client.post(f"/api/role-categories/{cat['id']}/deactivate", headers=SOURCING_MANAGER)
    assert r.json()["active"] is False
    assert client.get("/api/roles?active=true").json() == []
    assert client.get("/api/catalogue").json()["categories"] == []


def test_cannot_add_role_to_inactive_category(client):
    cat = make_category(client)
    client.post(f"/api/role-categories/{cat['id']}/deactivate", headers=SOURCING_MANAGER)
    r = client.post("/api/roles", json={"category_id": cat["id"], "name": "Java Developer"}, headers=SOURCING_MANAGER)
    assert r.status_code == 409


def test_role_activation_needs_active_category(client):
    cat = make_category(client)
    role = make_role(client, cat["id"])
    client.post(f"/api/role-categories/{cat['id']}/deactivate", headers=SOURCING_MANAGER)
    r = client.post(f"/api/roles/{role['id']}/activate", headers=SOURCING_MANAGER)
    assert r.status_code == 409
    client.post(f"/api/role-categories/{cat['id']}/activate", headers=SOURCING_MANAGER)
    r = client.post(f"/api/roles/{role['id']}/activate", headers=SOURCING_MANAGER)
    assert r.json()["active"] is True


def test_unknown_ids_return_404(client):
    assert client.post("/api/roles/does-not-exist/deactivate", headers=SOURCING_MANAGER).status_code == 404
    assert client.patch("/api/role-categories/nope", json={"name": "x"}, headers=SOURCING_MANAGER).status_code == 404


def test_audit_trail_records_who_what(client):
    cat = make_category(client)
    role = make_role(client, cat["id"])
    client.post(f"/api/roles/{role['id']}/deactivate", headers=SOURCING_MANAGER)
    entries = client.get("/api/audit-log", headers=SOURCING_MANAGER).json()
    assert [e["action"] for e in entries] == ["DEACTIVATE", "CREATE", "CREATE"]  # newest first
    assert all(e["actor"] == "Anna" for e in entries)
    assert client.get("/api/audit-log", headers=HIRING_MANAGER).status_code == 403


def test_catalogue_for_other_groups_contains_only_active_entries(client):
    cat = make_category(client)
    java = make_role(client, cat["id"], "Java Developer")
    make_role(client, cat["id"], "Python Developer")
    client.post(f"/api/roles/{java['id']}/deactivate", headers=SOURCING_MANAGER)
    data = client.get("/api/catalogue").json()
    assert [r["name"] for r in data["categories"][0]["roles"]] == ["Python Developer"]
    assert [lvl["code"] for lvl in data["seniority_levels"]] == ["JUNIOR", "SENIOR", "EXPERT"]
