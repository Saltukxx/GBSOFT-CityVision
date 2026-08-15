"""Edge upload API + package safety tests."""

from __future__ import annotations

import io
import json
import time
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cityvision.api.security import create_access_token, hash_password
from cityvision.db.store import Store
from cityvision.edge.package import safe_extract_zip
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


def _zip_bytes(events: list) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "events.json",
            json.dumps(events, ensure_ascii=False),
        )
        zf.writestr(
            "summary.json",
            json.dumps({"note": "edge-test"}, ensure_ascii=False),
        )
    return buf.getvalue()


def test_zip_slip_blocked(tmp_path: Path):
    evil = tmp_path / "evil.zip"
    with zipfile.ZipFile(evil, "w") as zf:
        zf.writestr("../outside.json", '{"x":1}')
        zf.writestr("events.json", "[]")
    with pytest.raises(ValueError, match="traversal"):
        safe_extract_zip(evil, tmp_path / "out")


def test_edge_register_upload_ingest(store: Store, tmp_path: Path, monkeypatch):
    monkeypatch.setenv("CITYVISION_RBAC", "0")
    monkeypatch.setenv("CITYVISION_EDGE_UPLOAD_DIR", str(tmp_path / "edge_uploads"))
    get_settings.cache_clear()

    # Ensure schema present
    store.upsert_city("erzurum", "Erzurum")

    from cityvision.api.app import app

    client = TestClient(app)

    reg = client.post(
        "/api/edge/devices",
        json={
            "id": "edge-test-1",
            "name": "Test Edge",
            "city_id": "erzurum",
            "vehicle_id": "BUS-EDGE",
        },
    )
    assert reg.status_code == 200, reg.text
    token = reg.json()["token"]
    assert token
    assert "token" not in (store.get_edge_device("edge-test-1") or {})

    # Bad token rejected
    bad = client.post(
        "/api/edge/upload",
        headers={"X-Edge-Token": "not-a-real-token"},
        files={"file": ("run.zip", _zip_bytes([]), "application/zip")},
    )
    assert bad.status_code == 401

    events = [
        {
            "event_id": "POT-EDGE-001",
            "type": "pothole",
            "lat": 39.94001,
            "lon": 41.30001,
            "confidence": 0.91,
            "status": "under_review",
            "observations": 1,
            "vehicle_id": "BUS-EDGE",
        }
    ]
    ok = client.post(
        "/api/edge/upload",
        headers={"X-Edge-Token": token},
        files={"file": ("run.zip", _zip_bytes(events), "application/zip")},
        data={"run_name": "edge-run-1"},
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert body["events"] == 1
    assert body["job_id"]
    upload_id = body["upload_id"]
    run_dir = Path(body["run_dir"])
    assert (run_dir / "events.json").exists()
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary.get("city_id") == "erzurum"
    assert summary.get("edge_device_id") == "edge-test-1"

    # Wait briefly for in-process job thread
    for _ in range(40):
        job = store.get_job(int(body["job_id"]))
        if job and job.get("status") in {"succeeded", "failed"}:
            break
        time.sleep(0.1)
    job = store.get_job(int(body["job_id"]))
    assert job is not None
    assert job["status"] == "succeeded", job

    ev = store.get_event("POT-EDGE-001")
    assert ev is not None
    assert ev.get("city_id") == "erzurum"

    status = client.get(
        f"/api/edge/uploads/{upload_id}",
        headers={"X-Edge-Token": token},
    )
    assert status.status_code == 200
    up = status.json()
    assert up["upload_id"] == upload_id
    assert up["status"] == "succeeded"
    assert up.get("job", {}).get("status") == "succeeded"


def test_edge_device_admin_gate(store: Store, monkeypatch):
    monkeypatch.setenv("CITYVISION_RBAC", "1")
    monkeypatch.setenv("CITYVISION_JWT_SECRET", "edge-admin-secret-key-32bytes!!!!")
    get_settings.cache_clear()
    store.upsert_user(
        "edge_admin",
        display_name="Admin",
        role="admin",
        password_hash=hash_password("adminpass"),
    )
    store.upsert_user(
        "edge_op",
        display_name="Op",
        role="operator",
        password_hash=hash_password("oppass12"),
    )

    from cityvision.api.app import app

    client = TestClient(app)
    op_tok = create_access_token("edge_op", "operator", expires_minutes=30)
    ad_tok = create_access_token("edge_admin", "admin", expires_minutes=30)

    denied = client.post(
        "/api/edge/devices",
        json={"id": "edge-denied", "name": "Nope"},
        headers={"Authorization": f"Bearer {op_tok}"},
    )
    assert denied.status_code == 403

    allowed = client.post(
        "/api/edge/devices",
        json={"id": "edge-allowed", "name": "Yes", "city_id": "erzurum"},
        headers={"Authorization": f"Bearer {ad_tok}"},
    )
    assert allowed.status_code == 200
    assert allowed.json().get("token")
