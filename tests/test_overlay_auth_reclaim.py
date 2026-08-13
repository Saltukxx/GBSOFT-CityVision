"""Auth role matrix + pipeline city overlay + job reclaim."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from cityvision.api.security import create_access_token, hash_password
from cityvision.config import deep_merge, load_pipeline_config
from cityvision.db.store import Store
from cityvision.settings import get_settings


def _db_ok() -> bool:
    try:
        get_settings.cache_clear()
        return Store().ping()
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_ok(), reason="PostGIS not reachable")


@pytest.fixture()
def store() -> Store:
    get_settings.cache_clear()
    return Store()


def test_deep_merge_and_city_overlay():
    base = {"run": {"vehicle_id": "BUS-DEMO", "camera_id": "FRONT"}, "events": {"fusion_radius_m": 20}}
    overlay = {"run": {"vehicle_id": "BUS-17"}, "events": {"min_observations": 2}}
    merged = deep_merge(base, overlay)
    assert merged["run"]["vehicle_id"] == "BUS-17"
    assert merged["run"]["camera_id"] == "FRONT"
    assert merged["events"]["fusion_radius_m"] == 20
    assert merged["events"]["min_observations"] == 2

    cfg = load_pipeline_config(city_id="erzurum")
    assert cfg["run"]["city_id"] == "erzurum"
    assert cfg["run"]["vehicle_id"] == "BUS-17"  # from overlay
    assert "geofence" in cfg
    assert cfg["geofence"].get("path")


def test_auth_role_matrix(store: Store, monkeypatch):
    monkeypatch.setenv("CITYVISION_RBAC", "1")
    monkeypatch.setenv("CITYVISION_JWT_SECRET", "matrix-secret-key-32bytes-min!!")
    get_settings.cache_clear()

    events = store.list_events(limit=1)
    if not events:
        pytest.skip("no events")
    eid = events[0]["event_id"]

    for user, role, pw in (
        ("m_viewer", "viewer", "vpass12"),
        ("m_operator", "operator", "opass12"),
        ("m_admin", "admin", "apass12"),
    ):
        store.upsert_user(user, display_name=user, role=role, password_hash=hash_password(pw))

    from cityvision.api.app import app

    client = TestClient(app)
    tokens = {
        role: create_access_token(f"m_{role}", role, expires_minutes=30)
        for role in ("viewer", "operator", "admin")
    }

    def hdr(role: str) -> dict:
        return {"Authorization": f"Bearer {tokens[role]}"}

    # GET events: open (middleware/RBAC not gating reads)
    assert client.get("/api/events").status_code == 200

    # Status patch: viewer forbidden, operator+ ok
    assert (
        client.patch(
            f"/api/events/{eid}/status",
            json={"status": "under_review"},
            headers=hdr("viewer"),
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"/api/events/{eid}/status",
            json={"status": "under_review"},
            headers=hdr("operator"),
        ).status_code
        == 200
    )

    # Users list: admin only
    assert client.get("/api/users", headers=hdr("viewer")).status_code == 403
    assert client.get("/api/users", headers=hdr("operator")).status_code == 403
    assert client.get("/api/users", headers=hdr("admin")).status_code == 200

    # Ingest: admin only
    assert (
        client.post(
            "/api/ingest",
            json={"run_dir": "outputs/does-not-exist"},
            headers=hdr("operator"),
        ).status_code
        == 403
    )
    # admin reaches handler (404 for missing path is fine)
    admin_ingest = client.post(
        "/api/ingest",
        json={"run_dir": "outputs/does-not-exist"},
        headers=hdr("admin"),
    )
    assert admin_ingest.status_code in {404, 422, 500}


def test_reclaim_stale_jobs_returns_ids(store: Store):
    job_id = store.create_job("ingest_run", {"run_dir": "/tmp/reclaim-test"})
    assert store.claim_job(job_id)
    # Backdate started_at so reclaim sees it as stale
    with store.connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE jobs SET started_at = %s WHERE id = %s",
                (datetime.now(timezone.utc) - timedelta(minutes=60), job_id),
            )
        store._commit(conn)

    ids = store.reclaim_stale_jobs(older_than_minutes=30)
    assert job_id in ids
    row = store.get_job(job_id)
    assert row is not None
    assert row["status"] == "queued"
    store.mark_job_done(job_id, ok=True, result={"cleanup": True})
