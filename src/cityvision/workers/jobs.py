from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from cityvision.db.ingest import ingest_run_dir
from cityvision.db.store import Store
from cityvision.db.zones import ingest_zones_geojson
from cityvision.settings import get_settings

log = logging.getLogger(__name__)


def enqueue_job(store: Store, job_type: str, payload: Dict[str, Any]) -> Tuple[int, bool]:
    """
    Enqueue a job. Returns (job_id, deduped).

    If an identical ingest is already queued/running, returns that job without creating another.
    """
    existing = None
    if job_type == "ingest_run" and payload.get("run_dir"):
        existing = store.find_active_job("ingest_run", run_dir=str(payload["run_dir"]))
    elif job_type == "ingest_zones" and payload.get("path"):
        existing = store.find_active_job("ingest_zones", path=str(payload["path"]))
    elif job_type == "analyze_video" and payload.get("upload_id"):
        existing = store.find_active_job(
            "analyze_video", upload_id=str(payload["upload_id"])
        )
    elif job_type == "analyze_video" and payload.get("object_key"):
        existing = store.find_active_job(
            "analyze_video", object_key=str(payload["object_key"])
        )
    if existing and existing.get("id") is not None:
        return int(existing["id"]), True

    job_id = store.create_job(job_type, payload)
    settings = get_settings()
    if settings.job_inline or not _redis_push(job_id):
        # Fallback: in-process thread (local pilot / tests)
        thread = threading.Thread(
            target=run_job,
            args=(job_id,),
            daemon=True,
            name=f"cv-job-{job_id}",
        )
        thread.start()
    return job_id, False


def run_job(job_id: int) -> None:
    store = Store()
    store.reclaim_stale_jobs(older_than_minutes=30)
    row = store.get_job(job_id)
    if not row:
        return
    if row.get("status") != "queued":
        return
    if not store.claim_job(job_id):
        # Another worker won the race
        return
    job_type = row["job_type"]
    payload = row.get("payload") or {}
    try:
        if job_type == "ingest_run":
            result = ingest_run_dir(payload["run_dir"], store=store)
        elif job_type == "ingest_zones":
            result = ingest_zones_geojson(payload["path"], store=store)
        elif job_type == "analyze_video":
            result = _run_analyze_video(store, payload)
        else:
            raise ValueError(f"unknown job_type: {job_type}")
        store.mark_job_done(job_id, ok=True, result=result)
        _sync_edge_upload(store, payload, status="succeeded", error=None)
        _sync_edge_video_upload(store, payload, status="succeeded", error=None)
    except Exception as exc:  # noqa: BLE001
        log.exception("job %s failed", job_id)
        store.mark_job_done(job_id, ok=False, error=str(exc))
        _sync_edge_upload(store, payload, status="failed", error=str(exc))
        _sync_edge_video_upload(store, payload, status="failed", error=str(exc))


def _run_analyze_video(store: Store, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Memphis: download video (+ GPS), run_pipeline, ingest events."""
    from cityvision.pipeline.runner import run_pipeline
    from cityvision.storage import get_object_store

    upload_id = str(payload["upload_id"])
    object_key = str(payload["object_key"])
    gps_key = payload.get("gps_object_key")
    city_id = payload.get("city_id")
    vehicle_id = payload.get("vehicle_id")
    camera_id = payload.get("camera_id") or "FRONT"
    run_name = payload.get("run_name") or upload_id[:12]

    store.update_edge_video_upload(upload_id, status="analyzing")

    settings = get_settings()
    work = settings.edge_upload_dir / "analyze" / upload_id
    work.mkdir(parents=True, exist_ok=True)
    video_path = work / "video.mp4"
    obj = get_object_store()
    obj.download_to(object_key, video_path)

    gps_path = None
    if gps_key:
        suffix = Path(str(gps_key)).suffix or ".jsonl"
        gps_path = work / f"gps{suffix}"
        obj.download_to(str(gps_key), gps_path)

    out_dir = work / "run"
    if out_dir.exists():
        import shutil

        shutil.rmtree(out_dir)
    run_pipeline(
        source=video_path,
        output_dir=out_dir,
        gps_path=str(gps_path) if gps_path else None,
        vehicle_id=str(vehicle_id) if vehicle_id else None,
        camera_id=str(camera_id) if camera_id else None,
        city_id=str(city_id) if city_id else None,
    )
    # Ensure city/route land in summary for ingest
    summary_path = out_dir / "summary.json"
    if summary_path.exists() or city_id or vehicle_id:
        import json

        summary: Dict[str, Any] = {}
        if summary_path.exists():
            try:
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
                if not isinstance(summary, dict):
                    summary = {}
            except json.JSONDecodeError:
                summary = {}
        if city_id and not summary.get("city_id"):
            summary["city_id"] = city_id
        if vehicle_id and not summary.get("vehicle_id"):
            summary["vehicle_id"] = vehicle_id
        if payload.get("route_id") and not summary.get("route_id"):
            summary["route_id"] = payload["route_id"]
        summary["memphis_upload_id"] = upload_id
        summary["run_name"] = run_name
        summary_path.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    ingest_result = ingest_run_dir(out_dir, store=store)
    store.update_edge_video_upload(
        upload_id, status="succeeded", run_dir=str(out_dir.resolve())
    )
    return {
        "upload_id": upload_id,
        "run_dir": str(out_dir.resolve()),
        "ingest": ingest_result,
    }


def _sync_edge_upload(
    store: Store,
    payload: Dict[str, Any],
    *,
    status: str,
    error: Optional[str],
) -> None:
    upload_id = payload.get("edge_upload_id")
    if not upload_id:
        return
    try:
        store.update_edge_upload(str(upload_id), status=status, error=error)
    except Exception:  # noqa: BLE001
        log.warning("failed to sync edge_upload %s -> %s", upload_id, status, exc_info=True)


def _sync_edge_video_upload(
    store: Store,
    payload: Dict[str, Any],
    *,
    status: str,
    error: Optional[str],
) -> None:
    upload_id = payload.get("upload_id")
    if not upload_id or "object_key" not in payload:
        return
    try:
        store.update_edge_video_upload(str(upload_id), status=status, error=error)
    except Exception:  # noqa: BLE001
        log.warning(
            "failed to sync edge_video_upload %s -> %s", upload_id, status, exc_info=True
        )


def startup_reclaim(older_than_minutes: int = 30) -> List[int]:
    """Reclaim stuck running jobs and re-queue them on Redis when available."""
    store = Store()
    ids = store.reclaim_stale_jobs(older_than_minutes=older_than_minutes)
    if not ids:
        return []
    log.info("Reclaimed %s stale job(s): %s", len(ids), ids)
    for job_id in ids:
        if not _redis_push(job_id):
            # No Redis — run inline so they are not orphaned
            threading.Thread(
                target=run_job,
                args=(job_id,),
                daemon=True,
                name=f"cv-reclaim-{job_id}",
            ).start()
    return ids


def redis_available() -> bool:
    return _redis_client() is not None


def _redis_client():
    try:
        import redis
    except ImportError:
        return None
    settings = get_settings()
    try:
        client = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=0.5)
        client.ping()
        return client
    except Exception:
        return None


def _redis_push(job_id: int) -> bool:
    client = _redis_client()
    if not client:
        return False
    settings = get_settings()
    try:
        client.rpush(settings.redis_queue_key, str(job_id))
        return True
    except Exception as exc:
        log.warning("redis push failed, falling back to thread: %s", exc)
        return False


def redis_worker_loop(stop_event: Optional[threading.Event] = None) -> None:
    """Blocking BLPOP loop — used by scripts/job_worker.py."""
    settings = get_settings()
    client = _redis_client()
    if not client:
        raise RuntimeError(f"Redis unavailable at {settings.redis_url}")
    startup_reclaim(older_than_minutes=30)
    log.info("Redis worker listening on %s", settings.redis_queue_key)
    while stop_event is None or not stop_event.is_set():
        item = client.blpop(settings.redis_queue_key, timeout=2)
        if not item:
            continue
        _, raw = item
        job_id = int(raw.decode() if isinstance(raw, bytes) else raw)
        run_job(job_id)
