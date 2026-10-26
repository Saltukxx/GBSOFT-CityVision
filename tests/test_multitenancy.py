"""Cross-tenant isolation: app-layer checks and Postgres RLS."""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from cityvision.api.deps import Principal, resolve_city_id
from cityvision.api.security import create_access_token, hash_password
from cityvision.db.store import Store
from cityvision.settings import get_settings
from cityvision.tenant import reset_tenant_city, set_tenant_city


def _db_ok() -> bool:
    try:
        get_settings.cache_clear()
        return Store().ping()
    except Exception:
        return False


def test_resolve_city_id_trusts_query_when_strict_off(monkeypatch):
    monkeypatch.setenv("CITYVISION_STRICT_TENANCY", "0")
    monkeypatch.setenv("CITYVISION_DEFAULT_CITY", "erzurum")
    get_settings.cache_clear()
    anon = Principal(username="anonymous", role="anonymous")
    assert resolve_city_id(anon, "ankara") == "ankara"
    assert resolve_city_id(anon, None) == "erzurum"


def test_resolve_city_id_rejects_override_when_strict_on(monkeypatch):
    monkeypatch.setenv("CITYVISION_STRICT_TENANCY", "1")
    get_settings.cache_clear()
    user = Principal(username="op", role="operator", city_id="erzurum")
    with pytest.raises(HTTPException) as exc:
        resolve_city_id(user, "ankara")
    assert exc.value.status_code == 403

    assert resolve_city_id(user, None) == "erzurum"
    assert resolve_city_id(user, "erzurum") == "erzurum"

    staff = Principal(username="root", role="superadmin", city_id=None)
    assert resolve_city_id(staff, "ankara") == "ankara"
    assert resolve_city_id(staff, None) is None

    key = Principal(username="api_key", role="admin", city_id=None, via="api_key")
    assert key.is_cross_city
    assert resolve_city_id(key, "ankara") == "ankara"

    impostor = Principal(username="api_key", role="operator", city_id="erzurum", via="jwt")
    assert not impostor.is_cross_city
    with pytest.raises(HTTPException) as stolen:
        resolve_city_id(impostor, "ankara")
    assert stolen.value.status_code == 403

    with pytest.raises(HTTPException) as exc2:
        resolve_city_id(Principal(username="anonymous", role="anonymous"), None)
    assert exc2.value.status_code == 401


def test_require_city_row_honours_signed_city(monkeypatch):
    monkeypatch.setenv("CITYVISION_STRICT_TENANCY", "1")
    get_settings.cache_clear()
    from cityvision.api.deps import require_city_row

    anon = Principal(username="anonymous", role="anonymous", via="anonymous")
    with pytest.raises(HTTPException) as exc:
        require_city_row(
            {"id": 1, "city_id": "erzurum"}, anon, signed_city_id="ankara"
        )
    assert exc.value.status_code == 404
    own = require_city_row(
        {"id": 1, "city_id": "erzurum"}, anon, signed_city_id="erzurum"
    )
    assert own["id"] == 1


pytestmark_db = pytest.mark.skipif(not _db_ok(), reason="PostGIS not reachable")


@pytest.fixture()
def store() -> Store:
    get_settings.cache_clear()
    return Store()


def _strict(monkeypatch) -> None:
    monkeypatch.setenv("CITYVISION_STRICT_TENANCY", "1")
    monkeypatch.setenv("CITYVISION_RBAC", "1")
    monkeypatch.setenv("CITYVISION_JWT_SECRET", "mt-secret-key-32-bytes-minimum!!")
    monkeypatch.setenv("CITYVISION_API_KEY", "")
    get_settings.cache_clear()


def _seed_two_cities(store: Store) -> dict:
    suffix = uuid.uuid4().hex[:8]
    city_a = f"mt-a-{suffix}"
    city_b = f"mt-b-{suffix}"
    store.upsert_city(city_a, f"City A {suffix}")
    store.upsert_city(city_b, f"City B {suffix}")
    run_a = store.upsert_run(
        f"/tmp/mt-a-{suffix}",
        {"city_id": city_a, "vehicle_id": "DJI-A"},
        {},
    )
    run_b = store.upsert_run(
        f"/tmp/mt-b-{suffix}",
        {"city_id": city_b, "vehicle_id": "DJI-B"},
        {},
    )
    eid_a = f"POT-A-{suffix}"
    eid_b = f"POT-B-{suffix}"
    store.upsert_event(
        run_a,
        {
            "event_id": eid_a,
            "type": "pothole",
            "lat": 39.91,
            "lon": 41.27,
            "confidence": 0.9,
            "status": "under_review",
            "city_id": city_a,
        },
    )
    store.upsert_event(
        run_b,
        {
            "event_id": eid_b,
            "type": "pothole",
            "lat": 39.92,
            "lon": 32.85,
            "confidence": 0.9,
            "status": "under_review",
            "city_id": city_b,
        },
    )
    store.upsert_user(
        f"op-a-{suffix}",
        display_name="Op A",
        role="operator",
        password_hash=hash_password("opass12"),
        city_id=city_a,
    )
    store.upsert_user(
        f"op-b-{suffix}",
        display_name="Op B",
        role="operator",
        password_hash=hash_password("opass12"),
        city_id=city_b,
    )
    store.upsert_user(
        f"sa-{suffix}",
        display_name="Super",
        role="superadmin",
        password_hash=hash_password("sapass1"),
        city_id=None,
    )
    store.upsert_user(
        f"ad-a-{suffix}",
        display_name="Admin A",
        role="admin",
        password_hash=hash_password("adpass12"),
        city_id=city_a,
    )
    return {
        "city_a": city_a,
        "city_b": city_b,
        "eid_a": eid_a,
        "eid_b": eid_b,
        "run_a": run_a,
        "run_b": run_b,
        "user_a": f"op-a-{suffix}",
        "user_b": f"op-b-{suffix}",
        "admin_a": f"ad-a-{suffix}",
        "super": f"sa-{suffix}",
    }


@pytestmark_db
def test_strict_tenancy_closes_anonymous_reads(store: Store, monkeypatch):
    _strict(monkeypatch)
    from cityvision.api.app import app

    client = TestClient(app)
    assert client.get("/health").status_code == 200
    denied = client.get("/api/events")
    assert denied.status_code == 401
    assert client.get("/api/kpis").status_code == 401


@pytestmark_db
def test_city_user_cannot_read_or_override_other_city(store: Store, monkeypatch):
    _strict(monkeypatch)
    ids = _seed_two_cities(store)
    from cityvision.api.app import app

    client = TestClient(app)
    tok_a = create_access_token(
        ids["user_a"], "operator", city_id=ids["city_a"], expires_minutes=30
    )
    hdr = {"Authorization": f"Bearer {tok_a}"}

    listed = client.get("/api/events", headers=hdr)
    assert listed.status_code == 200
    eids = {r["event_id"] for r in listed.json()}
    assert ids["eid_a"] in eids
    assert ids["eid_b"] not in eids

    override = client.get("/api/events", params={"city_id": ids["city_b"]}, headers=hdr)
    assert override.status_code == 403

    other = client.get(f"/api/events/{ids['eid_b']}", headers=hdr)
    assert other.status_code == 404

    own = client.get(f"/api/events/{ids['eid_a']}", headers=hdr)
    assert own.status_code == 200

    other_run = client.get(f"/api/runs/{ids['run_b']}/detections", headers=hdr)
    assert other_run.status_code == 404

    patched = client.patch(
        f"/api/events/{ids['eid_b']}/status",
        json={"status": "confirmed"},
        headers=hdr,
    )
    assert patched.status_code == 404
    still = store.get_event(ids["eid_b"])
    assert still is not None
    assert still["status"] == "under_review"


@pytestmark_db
def test_superadmin_can_select_a_city(store: Store, monkeypatch):
    _strict(monkeypatch)
    ids = _seed_two_cities(store)
    from cityvision.api.app import app

    client = TestClient(app)
    tok = create_access_token(
        ids["super"], "superadmin", city_id=None, expires_minutes=30
    )
    hdr = {"Authorization": f"Bearer {tok}"}
    b_only = client.get("/api/events", params={"city_id": ids["city_b"]}, headers=hdr)
    assert b_only.status_code == 200
    eids = {r["event_id"] for r in b_only.json()}
    assert ids["eid_b"] in eids
    assert ids["eid_a"] not in eids


@pytestmark_db
def test_rls_hides_other_city_even_without_sql_filter(store: Store, monkeypatch):
    """RLS boundary: unfiltered list_events must not return the other city."""
    _strict(monkeypatch)
    ids = _seed_two_cities(store)
    token = set_tenant_city(ids["city_a"])
    try:
        rows = store.list_events(limit=500)
        eids = {r["event_id"] for r in rows}
        assert ids["eid_a"] in eids
        assert ids["eid_b"] not in eids
        assert store.get_event(ids["eid_b"]) is None
    finally:
        reset_tenant_city(token)

    token = set_tenant_city("*")
    try:
        assert store.get_event(ids["eid_b"]) is not None
    finally:
        reset_tenant_city(token)


def test_create_job_rejects_tenant_mismatch():
    token = set_tenant_city("erzurum")
    try:
        with pytest.raises(ValueError, match="does not match"):
            Store().create_job(
                "ingest_run", {"run_dir": "/tmp/x", "city_id": "ankara"}
            )
        with pytest.raises(ValueError, match="does not match"):
            Store().upsert_user("x", role="operator", city_id="ankara")
    finally:
        reset_tenant_city(token)


@pytestmark_db
def test_create_job_stamps_tenant_city(store: Store, monkeypatch):
    _strict(monkeypatch)
    ids = _seed_two_cities(store)
    token = set_tenant_city(ids["city_a"])
    try:
        job_id = store.create_job("ingest_run", {"run_dir": "/tmp/mt-job"})
        row = store.get_job(job_id)
        assert row is not None
        assert row["city_id"] == ids["city_a"]
        assert row["payload"]["city_id"] == ids["city_a"]
    finally:
        reset_tenant_city(token)

    token = set_tenant_city(ids["city_b"])
    try:
        assert store.get_job(job_id) is None
    finally:
        reset_tenant_city(token)


@pytestmark_db
def test_stale_jwt_reloads_city_from_db(store: Store, monkeypatch):
    _strict(monkeypatch)
    ids = _seed_two_cities(store)
    tok = create_access_token(
        ids["user_a"], "operator", city_id=ids["city_a"], expires_minutes=30
    )
    store.upsert_user(
        ids["user_a"],
        display_name="Op A moved",
        role="operator",
        password_hash=hash_password("opass12"),
        city_id=ids["city_b"],
    )
    from cityvision.api.app import app

    client = TestClient(app)
    listed = client.get("/api/events", headers={"Authorization": f"Bearer {tok}"})
    assert listed.status_code == 200
    eids = {r["event_id"] for r in listed.json()}
    assert ids["eid_b"] in eids
    assert ids["eid_a"] not in eids


@pytestmark_db
def test_storage_and_audit_are_city_scoped(store: Store, monkeypatch):
    _strict(monkeypatch)
    ids = _seed_two_cities(store)
    key_b = f"events/{ids['eid_b']}/frame.jpg"
    store.upsert_event_media(
        ids["eid_b"], "image", "/tmp/frame.jpg", object_key=key_b
    )
    store.add_audit(
        actor="op-b",
        action="login",
        entity_type="user",
        entity_id="1",
        city_id=ids["city_b"],
    )
    from cityvision.api.app import app

    client = TestClient(app)
    tok_a = create_access_token(
        ids["admin_a"], "admin", city_id=ids["city_a"], expires_minutes=30
    )
    hdr = {"Authorization": f"Bearer {tok_a}"}
    denied = client.get(f"/api/storage/{key_b}", headers=hdr)
    assert denied.status_code == 404

    audit = client.get("/api/audit", headers=hdr)
    assert audit.status_code == 200
    cities = {row.get("city_id") for row in audit.json()}
    assert ids["city_b"] not in cities


@pytestmark_db
def test_username_reserved_and_collision(store: Store, monkeypatch):
    _strict(monkeypatch)
    ids = _seed_two_cities(store)
    from cityvision.api.app import app

    client = TestClient(app)
    tok_a = create_access_token(
        ids["admin_a"], "admin", city_id=ids["city_a"], expires_minutes=30
    )
    hdr = {"Authorization": f"Bearer {tok_a}"}
    reserved = client.post(
        "/api/auth/users",
        json={
            "username": "api_key",
            "password": "secret12",
            "role": "operator",
        },
        headers=hdr,
    )
    assert reserved.status_code == 422

    collision = client.post(
        "/api/auth/users",
        json={
            "username": ids["user_b"],
            "password": "secret12",
            "role": "operator",
        },
        headers=hdr,
    )
    assert collision.status_code == 409
