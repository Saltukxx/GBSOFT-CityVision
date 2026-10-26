"""Ingest end-to-end contracts: TX, merge, city_id, status preservation."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from cityvision.db.ingest import ingest_run_dir
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
    store = Store()
    store.upsert_city("erzurum", "Erzurum")
    return store


def _write_run(
    path: Path,
    *,
    event_id: str,
    lat: float,
    lon: float,
    vehicle: str,
    city_id: str = "erzurum",
    status: str = "under_review",
    observations: int = 1,
) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "events.json").write_text(
        json.dumps(
            [
                {
                    "event_id": event_id,
                    "type": "pothole",
                    "lat": lat,
                    "lon": lon,
                    "confidence": 0.87,
                    "confidence_band": "probable",
                    "observations": observations,
                    "severity": "medium",
                    "status": status,
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
        json.dumps(
            {
                "vehicle_id": vehicle,
                "camera_id": "FRONT",
                "city_id": city_id,
            }
        ),
        encoding="utf-8",
    )


def test_ingest_contract_city_merge_status_tx(store: Store, tmp_path: Path):
    suffix = uuid.uuid4().hex[:8]
    city_id = f"e2e-city-{suffix}"
    store.upsert_city(city_id, f"E2E {suffix}")
    lat = 39.95011 + int(suffix[:2], 16) * 1e-5
    lon = 41.31011 + int(suffix[2:4], 16) * 1e-5
    id_a = f"POT-E2E-A-{suffix}"
    id_b = f"POT-E2E-B-{suffix}"

    run_a = tmp_path / "a"
    run_b = tmp_path / "b"
    _write_run(run_a, event_id=id_a, lat=lat, lon=lon, vehicle="DJI-E2E-A", city_id=city_id)
    _write_run(
        run_b,
        event_id=id_b,
        lat=lat + 0.00001,
        lon=lon + 0.00001,
        vehicle="DJI-E2E-B",
        city_id=city_id,
    )

    r1 = ingest_run_dir(run_a, store=store)
    assert r1["events_created"] == 1
    assert r1["city_id"] == city_id
    row = store.get_event(id_a)
    assert row is not None
    assert row["city_id"] == city_id

    # Operator confirms
    assert store.update_event_status(id_a, "confirmed", actor="e2e")

    # Cross-run merge from bus B
    r2 = ingest_run_dir(run_b, store=store)
    assert r2["events_merged"] == 1
    assert r2["merges"][0]["into"] == id_a
    merged = store.get_event(id_a)
    assert merged is not None
    assert merged["status"] == "confirmed"  # protected
    assert store.get_event(id_b) is None
    payload = merged.get("payload") or {}
    assert id_b in (payload.get("merged_from") or [])
    assert "DJI-E2E-A" in (payload.get("vehicle_ids") or [])
    assert "DJI-E2E-B" in (payload.get("vehicle_ids") or [])

    # Re-ingest B is idempotent
    r3 = ingest_run_dir(run_b, store=store)
    assert r3["events_already_merged"] == 1
    assert r3["events_merged"] == 0
    again = store.get_event(id_a)
    assert again is not None
    assert int(again["observations"]) == int(merged["observations"])

    # Same event_id re-ingest does not wipe confirmed
    _write_run(
        run_a,
        event_id=id_a,
        lat=lat,
        lon=lon,
        vehicle="DJI-E2E-A",
        city_id=city_id,
        status="under_review",
        observations=1,
    )
    r4 = ingest_run_dir(run_a, store=store)
    assert r4["events_updated"] == 1
    final = store.get_event(id_a)
    assert final is not None
    assert final["status"] == "confirmed"
