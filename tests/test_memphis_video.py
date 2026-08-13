"""Memphis central video upload API tests."""

from __future__ import annotations

import time
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

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


def _register(client: TestClient, device_id: str | None = None) -> str:
    store = Store()
    store.upsert_city("erzurum", "Erzurum")
    device_id = device_id or f"memphis-{uuid.uuid4().hex[:10]}"
    reg = client.post(
        "/api/edge/devices",
        json={
            "id": device_id,
            "name": "Memphis Lab",
            "city_id": "erzurum",
            "vehicle_id": "BUS-MEM",
        },
    )
    assert reg.status_code == 200, reg.text
    return reg.json()["token"]


def test_memphis_heartbeat_and_video_dedupe(store: Store, tmp_path: Path, monkeypatch):
    monkeypatch.setenv("CITYVISION_RBAC", "0")
    monkeypatch.setenv("CITYVISION_JOB_INLINE", "1")
    monkeypatch.setenv("CITYVISION_OBJECT_STORE", str(tmp_path / "obj"))
    monkeypatch.setenv("CITYVISION_EDGE_UPLOAD_DIR", str(tmp_path / "edge"))
    get_settings.cache_clear()
    from cityvision.storage import get_object_store

    get_object_store.cache_clear()

    def fake_analyze(st: Store, payload: dict):
        uid = str(payload["upload_id"])
        st.update_edge_video_upload(uid, status="succeeded", run_dir=str(tmp_path / "run"))
        return {"upload_id": uid, "ingest": {"events_created": 0}}

    monkeypatch.setattr("cityvision.workers.jobs._run_analyze_video", fake_analyze)

    from cityvision.api.app import app

    client = TestClient(app)
    token = _register(client)

    hb = client.post(
        "/api/edge/heartbeat",
        headers={"X-Edge-Token": token},
        json={"props": {"disk_free_gb": 12.5, "uplink_ok": True}},
    )
    assert hb.status_code == 200, hb.text
    assert hb.json()["ok"] is True
    assert hb.json()["props"].get("disk_free_gb") == 12.5

    video = b"\x00\x00\x00\x18ftypmp42" + uuid.uuid4().bytes + b"\x00" * 180
    gps = b'{"timestamp_ms": 0, "lat": 39.9, "lon": 41.27}\n'

    up = client.post(
        "/api/edge/video",
        headers={"X-Edge-Token": token},
        files={
            "file": ("seg.mp4", video, "video/mp4"),
            "gps": ("gps.jsonl", gps, "application/x-ndjson"),
        },
        data={"route_id": "R-1", "run_name": "lab-1"},
    )
    assert up.status_code == 200, up.text
    body = up.json()
    assert body["deduped"] is False
    assert body["job_id"]
    upload_id = body["upload_id"]

    for _ in range(40):
        job = store.get_job(int(body["job_id"]))
        if job and job.get("status") in {"succeeded", "failed"}:
            break
        time.sleep(0.05)
    job = store.get_job(int(body["job_id"]))
    assert job is not None
    assert job["status"] == "succeeded", job

    status = client.get(
        f"/api/edge/video/{upload_id}",
        headers={"X-Edge-Token": token},
    )
    assert status.status_code == 200
    assert status.json()["status"] == "succeeded"

    again = client.post(
        "/api/edge/video",
        headers={"X-Edge-Token": token},
        files={"file": ("seg.mp4", video, "video/mp4")},
        data={"run_name": "lab-1-retry"},
    )
    assert again.status_code == 200, again.text
    assert again.json()["deduped"] is True
    assert again.json()["upload_id"] == upload_id


def test_memphis_video_rejects_bad_token(store: Store, monkeypatch):
    monkeypatch.setenv("CITYVISION_RBAC", "0")
    get_settings.cache_clear()
    from cityvision.api.app import app

    client = TestClient(app)
    bad = client.post(
        "/api/edge/video",
        headers={"X-Edge-Token": "nope"},
        files={"file": ("x.mp4", b"abc", "video/mp4")},
    )
    assert bad.status_code == 401
