"""API key gate + evidence media access control (no DB needed)."""

from __future__ import annotations

import time
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from cityvision.settings import get_settings


@contextmanager
def _client(monkeypatch, **env):
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    from cityvision.api.app import app

    try:
        yield TestClient(app)
    finally:
        get_settings.cache_clear()


def test_login_reachable_when_api_key_is_set(monkeypatch):
    """Regression: the API key gate used to 401 the login endpoint itself,
    making the documented 'API key and/or JWT' combination unusable."""

    class _NoUsers:
        def get_user(self, username):
            return None

    with _client(
        monkeypatch, CITYVISION_API_KEY="secret123", CITYVISION_JWT_SECRET="jwt-secret"
    ) as client:
        import cityvision.api.routers.auth_export as auth_export

        monkeypatch.setattr(auth_export, "get_store", lambda: _NoUsers())
        r = client.post("/api/auth/login", json={"username": "x", "password": "y"})

    # The request must reach the route: "invalid credentials" comes from the
    # login handler, "unauthorized" would mean the middleware blocked it.
    assert r.status_code == 401
    assert r.json()["detail"] == "invalid credentials"


def test_docs_and_health_stay_open_with_api_key(monkeypatch):
    with _client(monkeypatch, CITYVISION_API_KEY="secret123") as client:
        assert client.get("/openapi.json").status_code == 200
        assert client.get("/docs").status_code == 200


def test_mutating_endpoint_still_requires_key(monkeypatch):
    with _client(monkeypatch, CITYVISION_API_KEY="secret123") as client:
        r = client.post("/api/jobs/ingest", json={"run_dir": "outputs/nope"})
    assert r.status_code == 401
    assert r.json()["detail"] == "unauthorized"


def test_media_requires_auth_when_configured(monkeypatch):
    with _client(monkeypatch, CITYVISION_API_KEY="secret123") as client:
        assert client.get("/api/storage/evidence/POT-1/event.jpg").status_code == 401
        assert client.get("/api/media/1").status_code == 401
        assert client.get("/api/runs/1/annotated").status_code == 401


def test_media_accepts_api_key_header(monkeypatch):
    with _client(monkeypatch, CITYVISION_API_KEY="secret123") as client:
        r = client.get(
            "/api/storage/evidence/POT-1/missing.jpg", headers={"X-API-Key": "secret123"}
        )
    # Authorized; 404 because the object does not exist.
    assert r.status_code == 404


def test_media_accepts_signed_url(monkeypatch):
    with _client(monkeypatch, CITYVISION_API_KEY="secret123") as client:
        from cityvision.api.media_tokens import storage_url

        key = "evidence/POT-1/missing.jpg"
        url = storage_url(key)
        assert "sig=" in url and "exp=" in url
        assert client.get(url).status_code == 404


def test_signed_url_rejects_tampering_and_expiry(monkeypatch):
    with _client(monkeypatch, CITYVISION_API_KEY="secret123") as client:
        from cityvision.api.media_tokens import (
            sign_media_params,
            storage_resource,
            storage_url,
        )

        url = storage_url("evidence/POT-1/missing.jpg")
        sig = url.split("sig=")[1]

        # Signature is bound to the resource: it must not unlock another key.
        assert client.get(f"/api/storage/evidence/POT-2/other.jpg?{url.split('?')[1]}").status_code == 401
        # Flipped signature.
        assert client.get(url.replace(sig, "0" * len(sig))).status_code == 401
        # Already expired.
        expired = sign_media_params(storage_resource("evidence/POT-1/missing.jpg"), ttl_sec=-10)
        assert client.get(f"/api/storage/evidence/POT-1/missing.jpg?{expired}").status_code == 401


def test_media_open_when_no_credentials_configured(monkeypatch):
    """Bare local pilot keeps working without any auth setup."""
    with _client(monkeypatch, CITYVISION_API_KEY="", CITYVISION_JWT_SECRET="") as client:
        r = client.get("/api/storage/evidence/POT-1/missing.jpg")
    assert r.status_code == 404  # reached the store, just no such object


def test_signed_url_unsigned_when_no_secret(monkeypatch):
    with _client(monkeypatch, CITYVISION_API_KEY="", CITYVISION_JWT_SECRET=""):
        from cityvision.api.media_tokens import storage_url

        assert storage_url("evidence/a.jpg") == "/api/storage/evidence/a.jpg"


def test_media_token_ttl_is_honoured(monkeypatch):
    with _client(monkeypatch, CITYVISION_JWT_SECRET="jwt-secret"):
        from cityvision.api.media_tokens import sign_media_params, verify_media_token

        params = dict(p.split("=", 1) for p in sign_media_params("storage:a", ttl_sec=60).split("&"))
        assert int(params["exp"]) > int(time.time())
        assert verify_media_token("storage:a", params["exp"], params["sig"])
        assert not verify_media_token("storage:b", params["exp"], params["sig"])


def test_signed_url_is_bound_to_city(monkeypatch):
    with _client(monkeypatch, CITYVISION_JWT_SECRET="jwt-secret"):
        from cityvision.api.media_tokens import (
            storage_resource,
            storage_url,
            verify_media_token,
        )

        url = storage_url("evidence/a.jpg", city_id="erzurum")
        assert "cid=erzurum" in url
        params = dict(p.split("=", 1) for p in url.split("?", 1)[1].split("&"))
        assert verify_media_token(
            storage_resource("evidence/a.jpg"),
            params["exp"],
            params["sig"],
            city_id="erzurum",
        )
        assert not verify_media_token(
            storage_resource("evidence/a.jpg"),
            params["exp"],
            params["sig"],
            city_id="ankara",
        )


def test_strict_tenancy_rejects_garbage_bearer_on_edge_admin(monkeypatch):
    """A junk Authorization header must not skip tenancy on /api/edge/devices."""
    with _client(
        monkeypatch,
        CITYVISION_STRICT_TENANCY="1",
        CITYVISION_JWT_SECRET="mt-secret-key-32-bytes-minimum!!",
        CITYVISION_API_KEY="",
        CITYVISION_RBAC="1",
    ) as client:
        hdr = {"Authorization": "Bearer not-a-jwt"}
        assert client.get("/api/edge/devices", headers=hdr).status_code == 401
        assert client.get("/api/events", headers=hdr).status_code == 401


@pytest.mark.parametrize("path", ["/api/events", "/api/kpis"])
def test_dashboard_reads_stay_open(monkeypatch, path):
    """These are the reads the operator UI polls; they intentionally stay open.
    Media is not among them."""
    from cityvision.api.auth import ALWAYS_OPEN_PATHS, OPEN_READ_PREFIXES

    assert any(path.startswith(p) for p in OPEN_READ_PREFIXES) or path in ALWAYS_OPEN_PATHS
    assert not any(p.startswith("/api/storage") or p.startswith("/api/media") for p in OPEN_READ_PREFIXES)
