import os

# Use a separate test database file, never the real one.
os.environ["DATABASE_URL"] = "sqlite:///./test_group6.db"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import seed  # noqa: E402

SOURCING_MANAGER = {"X-User-Role": "SOURCING_MANAGER", "X-User-Name": "Anna"}
HIRING_MANAGER = {"X-User-Role": "HIRING_MANAGER", "X-User-Name": "Ben"}


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    seed()
    with TestClient(app) as c:
        yield c
