"""Worker job control: heartbeat-based reclaim, bounded retries, cancel, stop/retry API."""

from __future__ import annotations

import uuid

import pytest
from test_admin_api import _auth, _client, _db_ok, city  # noqa: F401

pytestmark = pytest.mark.skipif(not _db_ok(), reason="PostGIS not reachable")


def _job(store, city_id, job_type="ingest_run", payload=None):
    from cityvision.tenant import TENANT_ALL, reset_tenant_city, set_tenant_city

    token = set_tenant_city(TENANT_ALL)
    try:
        return store.create_job(job_type, {"city_id": city_id, **(payload or {})})
    finally:
        reset_tenant_city(token)


def _sql(store, sql, args=()):
    with store.connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, args)
        store._commit(conn)


def test_reclaim_uses_heartbeat_and_gives_up(city):  # noqa: F811
    store = city["store"]
    jid = _job(store, city["id"])
    assert store.claim_job(jid)
    job = store.get_job(jid)
    assert job["attempts"] == 1 and job["heartbeat_at"] is not None

    # Running for hours but still beating: left alone.
    _sql(store, "UPDATE jobs SET started_at = NOW() - interval '3 hours', heartbeat_at = NOW() WHERE id = %s", (jid,))
    assert jid not in store.reclaim_stale_jobs(older_than_minutes=5)

    # Silent for 10 minutes: re-queued.
    _sql(store, "UPDATE jobs SET heartbeat_at = NOW() - interval '10 minutes' WHERE id = %s", (jid,))
    assert jid in store.reclaim_stale_jobs(older_than_minutes=5)
    assert store.get_job(jid)["status"] == "queued"

    # Third silent death: failed, not looped.
    _sql(store, "UPDATE jobs SET status = 'running', attempts = 3, heartbeat_at = NOW() - interval '10 minutes' WHERE id = %s", (jid,))
    assert jid not in store.reclaim_stale_jobs(older_than_minutes=5, max_attempts=3)
    job = store.get_job(jid)
    assert job["status"] == "failed" and "giving up" in job["error"]
    _sql(store, "DELETE FROM jobs WHERE id = %s", (jid,))


def test_cancel_queued_and_running(city, monkeypatch):  # noqa: F811
    import cityvision.workers.jobs as jobs
    from cityvision.flights.uploads import web_device_id

    store = city["store"]
    queued = _job(store, city["id"])
    assert store.request_job_cancel(queued) == "cancelled"
    assert not store.claim_job(queued)

    # A running analysis that is told to stop ends as cancelled; its flight as stopped.
    fid = uuid.uuid4().hex
    store.create_edge_video_upload(
        fid, web_device_id(store, city["id"]), f"flights/{fid}/v.mp4", f"sha-{fid}",
        city_id=city["id"], nbytes=1, payload={"source": "web", "name": "Stop me"}, status="queued",
    )
    jid = _job(store, city["id"], "analyze_video", {"upload_id": fid, "object_key": f"flights/{fid}/v.mp4"})

    def fake_analyze(store_, payload, job_id, hb):
        store_.request_job_cancel(job_id)
        hb.cancelled.set()  # what the heartbeat thread does on its next beat
        hb.check()

    monkeypatch.setattr(jobs, "_run_analyze_video", fake_analyze)
    jobs.run_job(jid)
    assert store.get_job(jid)["status"] == "cancelled"
    assert store.get_edge_video_upload(fid)["status"] == "stopped"
    _sql(store, "DELETE FROM jobs WHERE id = ANY(%s)", ([queued, jid],))


def test_stop_and_retry_api(city, monkeypatch):  # noqa: F811
    import cityvision.api.routers.flights as flights_router
    from cityvision.flights.uploads import web_device_id

    store = city["store"]
    client = _client()
    op = _auth(client, city["op"], "op-pass-123")
    enqueued: list = []
    monkeypatch.setattr(flights_router, "enqueue_job", lambda st, t, p: (enqueued.append((t, p)) or _job(st, city["id"], t, p), False))

    fid = uuid.uuid4().hex
    store.create_edge_video_upload(
        fid, web_device_id(store, city["id"]), f"flights/{fid}/v.mp4", f"sha-{fid}",
        city_id=city["id"], nbytes=1, payload={"source": "web", "name": "Retry me"}, status="queued",
    )
    store.update_edge_video_upload(fid, job_id=_job(store, city["id"]))

    assert client.post(f"/api/flights/{fid}/retry", headers=op).status_code == 409  # still running
    stopped = client.post(f"/api/flights/{fid}/stop", headers=op)
    assert stopped.status_code == 200 and stopped.json()["status"] == "stopped"
    assert client.post(f"/api/flights/{fid}/stop", headers=op).status_code == 409

    retried = client.post(f"/api/flights/{fid}/retry", headers=op)
    assert retried.status_code == 200 and retried.json()["status"] == "queued"
    assert enqueued[-1][0] == "analyze_video" and enqueued[-1][1]["object_key"] == f"flights/{fid}/v.mp4"

    # Never reached storage and its chunks are gone: ask for a new upload.
    gid = uuid.uuid4().hex
    store.create_edge_video_upload(
        gid, web_device_id(store, city["id"]), f"flights/{gid}/v.mp4", f"pending:{gid}",
        city_id=city["id"], nbytes=10, payload={"source": "web"}, status="failed",
    )
    r = client.post(f"/api/flights/{gid}/retry", headers=op)
    assert r.status_code == 409 and r.json()["detail"] == "upload_incomplete"
    _sql(store, "DELETE FROM jobs WHERE city_id = %s", (city["id"],))
