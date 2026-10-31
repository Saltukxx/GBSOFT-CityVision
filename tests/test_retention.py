"""GDPR retention and right to erasure."""

from __future__ import annotations

import uuid

import pytest
from test_admin_api import _auth, _client, _db_ok, _event, city  # noqa: F401

pytestmark = pytest.mark.skipif(not _db_ok(), reason="PostGIS not reachable")


def _sql(store, sql, args=()):
    with store.connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            rows = cur.fetchall() if cur.description else []
        store._commit(conn)
    return rows


def _flight(store, city_id, *, run_dir=None, status="succeeded", days_old=0):
    from cityvision.flights.uploads import web_device_id
    from cityvision.storage import get_object_store

    fid = uuid.uuid4().hex
    key = f"flights/{city_id}/{fid}/video.mp4"
    get_object_store().put_bytes(key, b"raw video with people in it")
    store.create_edge_video_upload(
        fid, web_device_id(store, city_id), key, f"sha-{fid}", city_id=city_id, nbytes=10,
        payload={"source": "web", "name": "ret"}, status=status,
    )
    if run_dir:
        store.update_edge_video_upload(fid, run_dir=run_dir)
    _sql(store, "UPDATE edge_video_uploads SET created_at = NOW() - make_interval(days => %s) WHERE upload_id = %s", (days_old, fid))
    return fid, key


def _latest_run_dir(store, city_id):
    return _sql(store, "SELECT run_dir FROM runs WHERE city_id = %s ORDER BY id DESC LIMIT 1", (city_id,))[0]["run_dir"]


def test_raw_video_purged_after_retention_once(city):  # noqa: F811
    from cityvision.privacy.retention import run_retention
    from cityvision.storage import get_object_store

    store = city["store"]
    old, old_key = _flight(store, city["id"], days_old=40)
    new, new_key = _flight(store, city["id"], days_old=5)
    busy, busy_key = _flight(store, city["id"], days_old=40, status="analyzing")

    report = run_retention(store, city["id"])[city["id"]]
    assert report["raw_videos_deleted"] == 1 and report["raw_video_days"] == 30
    obj = get_object_store()
    assert not obj.exists(old_key) and obj.exists(new_key) and obj.exists(busy_key)
    assert "raw_deleted_at" in store.get_edge_video_upload(old)["payload"]
    assert store.get_edge_video_upload(old)["status"] == "succeeded"  # flight stays, footage goes

    assert run_retention(store, city["id"])[city["id"]]["raw_videos_deleted"] == 0  # idempotent

    # 0 = keep forever.
    store.update_city(city["id"], props_merge={"raw_video_days": 0})
    store.update_edge_video_upload(new, payload_merge={})
    _sql(store, "UPDATE edge_video_uploads SET created_at = NOW() - interval '400 days' WHERE upload_id = %s", (new,))
    assert run_retention(store, city["id"])[city["id"]]["raw_videos_deleted"] == 0
    assert obj.exists(new_key)


def test_rejected_evidence_purged_but_training_frames_kept(city, tmp_path):  # noqa: F811
    from cityvision.privacy.retention import run_retention
    from cityvision.storage import get_object_store

    store = city["store"]
    obj = get_object_store()
    e_rej, e_keep, e_ok = (_event(city, tmp_path) for _ in range(3))
    keys = {}
    for eid in (e_rej, e_keep, e_ok):
        keys[eid] = f"evidence/{eid}/t/event.jpg"
        obj.put_bytes(keys[eid], b"img")
        store.upsert_event_media(eid, "image", keys[eid], "image/jpeg", 3, keys[eid])
    _sql(store, "UPDATE events SET status = 'false_positive' WHERE event_id = ANY(%s)", ([e_rej, e_keep],))
    for eid in (e_rej, e_keep):  # rejected 100 days ago
        _sql(store, "INSERT INTO review_feedback (event_id, label, reviewer, created_at) VALUES (%s, 'wrong', 't', NOW() - interval '100 days')", (eid,))
    _sql(store, "UPDATE events SET updated_at = NOW() - interval '100 days' WHERE event_id = %s", (e_ok,))
    media_keep = store.list_event_media(e_keep)[0]["id"]
    store.upsert_training_label(e_keep, kind="negative", boxes=[], labeller="t", media_id=media_keep, city_id=city["id"])

    report = run_retention(store, city["id"])[city["id"]]
    assert report["rejected_media_deleted"] == 1
    assert store.list_event_media(e_rej) == [] and not obj.exists(keys[e_rej])
    assert len(store.list_event_media(e_keep)) == 1 and obj.exists(keys[e_keep])
    assert len(store.list_event_media(e_ok)) == 1  # not rejected: kept
    assert store.get_event(e_rej) is not None  # the record stays for statistics


def test_erase_flight_and_api(city, tmp_path):  # noqa: F811
    from cityvision.storage import get_object_store

    store = city["store"]
    client = _client()
    op = _auth(client, city["op"], "op-pass-123")
    admin = _auth(client, city["admin"], "admin-pass-1")

    only_here = _event(city, tmp_path)
    run_dir = _latest_run_dir(store, city["id"])
    fid, key = _flight(store, city["id"], run_dir=run_dir)

    assert client.delete(f"/api/flights/{fid}", headers=op).status_code == 403
    assert client.delete(f"/api/flights/{fid}", headers=admin).status_code == 204
    assert store.get_edge_video_upload(fid) is None
    assert store.get_event(only_here) is None
    assert not get_object_store().exists(key)
    assert _sql(store, "SELECT 1 FROM runs WHERE run_dir = %s", (run_dir,)) == []
    audit = client.get("/api/audit/search", params={"action": "flight_delete"}, headers=admin).json()
    assert audit and audit[0]["entity_id"] == fid

    busy, _ = _flight(store, city["id"], status="analyzing")
    assert client.delete(f"/api/flights/{busy}", headers=admin).json()["detail"] == "stop_processing_first"


def test_retention_settings_and_run_now(city, monkeypatch):  # noqa: F811
    import cityvision.workers.jobs as jobs

    client = _client()
    admin = _auth(client, city["admin"], "admin-pass-1")
    s = client.get("/api/city-settings", headers=admin).json()
    assert s["raw_video_days"] == 30 and s["rejected_evidence_days"] == 90
    r = client.patch("/api/city-settings", json={"raw_video_days": 14, "rejected_evidence_days": 0}, headers=admin)
    assert r.json()["raw_video_days"] == 14 and r.json()["rejected_evidence_days"] == 0
    assert client.patch("/api/city-settings", json={"raw_video_days": -1}, headers=admin).status_code == 422

    queued = []
    monkeypatch.setattr(jobs, "enqueue_job", lambda st, t, p: (queued.append((t, p)), (1, False))[1])
    assert client.post("/api/city-settings/retention/run", headers=admin).json()["job_id"] == 1
    assert queued == [("retention", {"only_city": city["id"], "city_id": city["id"]})]
