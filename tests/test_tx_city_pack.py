"""Transactional ingest + city pack tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cityvision.cities import apply_city_pack, list_city_packs, load_city_pack
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
    return Store()


def test_load_erzurum_city_pack():
    assert "erzurum" in list_city_packs()
    pack = load_city_pack("erzurum")
    assert pack.city_id == "erzurum"
    assert pack.zones_path is not None and pack.zones_path.exists()
    assert pack.routes


def test_apply_city_pack(store: Store):
    pack = load_city_pack("erzurum")
    result = apply_city_pack(pack, store=store)
    assert result["city_id"] == "erzurum"
    assert result["zones"]["zones_upserted"] >= 1
    cities = {c["id"] for c in store.list_cities()}
    assert "erzurum" in cities


def test_transactional_ingest_commits(store: Store, tmp_path: Path):
    run = tmp_path / "tx_ok"
    run.mkdir()
    eid = "POT-TX-OK"
    (run / "events.json").write_text(
        json.dumps(
            [
                {
                    "event_id": eid,
                    "type": "pothole",
                    "lat": 39.93011,
                    "lon": 41.29011,
                    "confidence": 0.9,
                    "status": "under_review",
                    "observations": 1,
                    "vehicle_id": "DJI-TX",
                }
            ]
        ),
        encoding="utf-8",
    )
    (run / "summary.json").write_text(
        json.dumps({"vehicle_id": "DJI-TX", "city_id": "erzurum"}),
        encoding="utf-8",
    )
    r = ingest_run_dir(run, store=store)
    assert r["events_created"] == 1 or r["events_updated"] == 1
    assert store.get_event(eid) is not None


def test_transaction_rolls_back_on_error(store: Store, tmp_path: Path, monkeypatch):
    run = tmp_path / "tx_fail"
    run.mkdir()
    eid = "POT-TX-FAIL"
    (run / "events.json").write_text(
        json.dumps(
            [
                {
                    "event_id": eid,
                    "type": "pothole",
                    "lat": 39.93111,
                    "lon": 41.29111,
                    "confidence": 0.9,
                    "status": "under_review",
                    "observations": 1,
                    "vehicle_id": "DJI-TXF",
                }
            ]
        ),
        encoding="utf-8",
    )
    (run / "summary.json").write_text(
        json.dumps({"vehicle_id": "DJI-TXF", "city_id": "erzurum"}),
        encoding="utf-8",
    )

    original = store.sync_observation_count

    def boom(event_id: str) -> int:
        raise RuntimeError("forced failure mid-ingest")

    monkeypatch.setattr(store, "sync_observation_count", boom)
    with pytest.raises(RuntimeError, match="forced failure"):
        ingest_run_dir(run, store=store)

    # Event must not exist after rollback
    assert store.get_event(eid) is None
    monkeypatch.setattr(store, "sync_observation_count", original)
