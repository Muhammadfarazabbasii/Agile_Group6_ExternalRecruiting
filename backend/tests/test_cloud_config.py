"""Cloud settings: database URL and allowed origins."""
import pytest

from app.database import normalize_database_url


@pytest.mark.parametrize(
    "given,expected",
    [
        ("postgres://u:p@host:5432/db", "postgresql+psycopg://u:p@host:5432/db"),
        ("postgresql://u:p@host/db?sslmode=require", "postgresql+psycopg://u:p@host/db?sslmode=require"),
        ("postgresql+psycopg://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
        ("sqlite:///./group6.db", "sqlite:///./group6.db"),
    ],
)
def test_database_url_is_normalised(given, expected):
    assert normalize_database_url(given) == expected


def test_cors_allows_the_configured_origin_only(client):
    ok = client.options("/health", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    bad = client.options("/health", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in bad.headers
