"""Backend hardening: idempotent merge, status preservation, jobs, contracts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cityvision.db.ingest import ingest_run_dir
from cityvision.db.store import Store
from cityvision.settings import get_settings
from cityvision.workers.jobs import enqueue_job


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


def _write_run(path: Path, event_id: str, lat: float, lon: float, vehicle: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "events.json").write_text(
        json.dumps(
            [
                {
                    "event_id": event_id,
                    "type": "pothole",
                    "lat": lat,
                    "lon": lon,
                    "confidence": 0.86,
                    "confidence_band": "probable",
                    "observations": 1,
                    "severity": "medium",
                    "status": "under_review",
                    "vehicle_ids": [vehicle],
                    "vehicle_id": vehicle,
                    "first_seen_ms": 1000,
                    "last_seen_ms": 1500,
                }
            ]
        ),
        encoding="utf-8",
    )
    (path / "summary.json").write_text(
        json.dumps({"vehicle_id": vehicle, "camera_id": "FRONT"}),
        encoding="utf-8",
    )


def test_merge_reingest_is_idempotent(store: Store, tmp_path: Path):
    lat, lon = 39.91101, 41.31101
    run_a = tmp_path / "ida"
    run_b = tmp_path / "idb"
    _write_run(run_a, "POT-IDEM-A", lat, lon, "BUS-X")
    _write_run(run_b, "POT-IDEM-B", lat + 0.00001, lon + 0.00001, "BUS-Y")

    ingest_run_dir(run_a, store=store)
    r2 = ingest_run_dir(run_b, store=store)
    assert r2["events_merged"] == 1
    before = store.get_event("POT-IDEM-A")
    assert before is not None
    obs_before = int(before["observations"])

    r3 = ingest_run_dir(run_b, store=store)
    assert r3["events_merged"] == 0
    assert r3["events_already_merged"] == 1
    after = store.get_event("POT-IDEM-A")
    assert after is not None
    assert int(after["observations"]) == obs_before


def test_operator_status_preserved_on_reingest(store: Store, tmp_path: Path):
    lat, lon = 39.91202, 41.31202
    run = tmp_path / "status_run"
    _write_run(run, "POT-STATUS-1", lat, lon, "BUS-S")
    ingest_run_dir(run, store=store)
    assert store.update_event_status("POT-STATUS-1", "confirmed", actor="pytest")

    # Pipeline still says under_review — must not wipe confirmed
    events = json.loads((run / "events.json").read_text(encoding="utf-8"))
    events[0]["status"] = "under_review"
    events[0]["observations"] = 1
    (run / "events.json").write_text(json.dumps(events), encoding="utf-8")

    r = ingest_run_dir(run, store=store)
    assert r["events_updated"] == 1
    row = store.get_event("POT-STATUS-1")
    assert row is not None
    assert row["status"] == "confirmed"


def test_status_enum_rejects_invalid(store: Store):
    from fastapi.testclient import TestClient

    from cityvision.api.app import app

    events = store.list_events(limit=1)
    if not events:
        pytest.skip("no events")
    eid = events[0]["event_id"]
    client = TestClient(app)
    bad = client.patch(f"/api/events/{eid}/status", json={"status": "not_a_real_status"})
    assert bad.status_code == 422


def test_job_claim_is_single_winner(store: Store, tmp_path: Path):
    run = tmp_path / "job_run"
    _write_run(run, "POT-JOB-1", 39.91303, 41.31303, "BUS-J")
    job_id = store.create_job("ingest_run", {"run_dir": str(run)})
    assert store.claim_job(job_id) is True
    assert store.claim_job(job_id) is False
    # Finish so we don't leave junk running
    store.mark_job_done(job_id, ok=True, result={"ok": True})


def test_enqueue_dedupes_active_ingest(store: Store, tmp_path: Path):
    run = tmp_path / "dedupe_run"
    _write_run(run, "POT-DEDUP-1", 39.91404, 41.31404, "BUS-D")
    # Create a queued job without starting a worker thread
    j1 = store.create_job("ingest_run", {"run_dir": str(run)})
    active = store.find_active_job("ingest_run", run_dir=str(run))
    assert active is not None
    assert int(active["id"]) == j1

    j2, deduped = enqueue_job(store, "ingest_run", {"run_dir": str(run)})
    assert deduped is True
    assert j2 == j1

    store.mark_job_done(j1, ok=True, result={"cleanup": True})
