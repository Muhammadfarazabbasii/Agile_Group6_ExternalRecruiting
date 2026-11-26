"""Change feed on the audit log (for Group 5 and other groups that poll for changes).

Each audit entry has a unique integer id that grows with every change. A client keeps the
last id it processed and asks for entries with a larger id (`after_id`). Oldest come first.
"""
from .conftest import HIRING_MANAGER, SOURCING_MANAGER


def make_category(client, name):
    r = client.post("/api/role-categories", json={"name": name}, headers=SOURCING_MANAGER)
    assert r.status_code == 201, r.text
    return r.json()


def feed(client, **params):
    return client.get("/api/audit-log", params=params, headers=SOURCING_MANAGER)


def test_default_list_is_still_newest_first(client):
    make_category(client, "Development")
    make_category(client, "Testing")
    ids = [e["id"] for e in feed(client).json()]
    assert ids == sorted(ids, reverse=True)


def test_after_id_returns_only_newer_entries_oldest_first(client):
    make_category(client, "Development")
    first_id = feed(client).json()[0]["id"]
    make_category(client, "Testing")
    make_category(client, "Design")

    everything = sorted(e["id"] for e in feed(client, limit=500).json())
    expected = [i for i in everything if i > first_id]

    ids = [e["id"] for e in feed(client, after_id=first_id).json()]
    assert ids == expected          # exactly the newer entries
    assert ids == sorted(ids)       # oldest first
    assert len(ids) == 2


def test_cursor_at_the_last_id_returns_nothing(client):
    make_category(client, "Development")
    last_id = feed(client).json()[0]["id"]
    assert feed(client, after_id=last_id).json() == []


def test_polling_with_a_cursor_sees_every_change_once(client):
    for name in ["Development", "Testing", "Design", "Data", "Security"]:
        make_category(client, name)

    seen = []
    cursor = 0
    while True:
        batch = feed(client, after_id=cursor, limit=2).json()
        if not batch:
            break
        seen.extend(e["id"] for e in batch)
        cursor = batch[-1]["id"]

    all_ids = sorted(e["id"] for e in feed(client, limit=500).json())
    assert seen == all_ids          # nothing missed, nothing twice, in order
    assert len(seen) == len(set(seen)) == 5


def test_feed_respects_the_entity_filter(client):
    cat = make_category(client, "Development")
    client.post(
        "/api/roles", json={"category_id": cat["id"], "name": "Backend"}, headers=SOURCING_MANAGER
    )
    entries = feed(client, after_id=0, entity="role").json()
    assert entries and all(e["entity"] == "role" for e in entries)


def test_feed_is_only_for_the_sourcing_manager(client):
    make_category(client, "Development")
    r = client.get("/api/audit-log", params={"after_id": 0}, headers=HIRING_MANAGER)
    assert r.status_code == 403
