"""Pull a finished FlightHub flight into the existing analyze_video path.

Nothing here re-implements detection. A completed task's video lands in the object
store, its trajectory becomes a GPS sidecar, and the normal `analyze_video` job takes
over: run_pipeline → events → PostGIS → operator review → work order.

Idempotency comes from the `edge_video_uploads(device_id, checksum)` unique index, so
re-polling the same task is harmless — a second pull of unchanged media is a no-op.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from cityvision.db.store import Store
from cityvision.flighthub.client import FlightHubClient, FlightHubError, video_media
from cityvision.flighthub.trajectory import parse_trajectory, write_gps_sidecar
from cityvision.settings import get_settings
from cityvision.storage import get_object_store
from cityvision.workers.jobs import enqueue_job

log = logging.getLogger(__name__)

TASK_STATUS_DONE = "success"
_HASH_CHUNK = 1 << 20


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(_HASH_CHUNK)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _ensure_dock_device(store: Store, task: Dict[str, Any], city_id: Optional[str]) -> str:
    """
    Represent the dock as an edge device so uploads satisfy the existing FK.

    The token hash is random and thrown away: pulls are server-initiated, so the dock
    never authenticates inbound, and a derivable hash would be a guessable credential.
    """
    dock_sn = str(task.get("dock_sn") or "unknown").strip() or "unknown"
    device_id = f"dock-{dock_sn}"
    if store.get_edge_device(device_id):
        return device_id
    store.upsert_edge_device(
        device_id,
        f"DJI Dock {dock_sn}",
        secrets.token_hex(32),
        city_id=city_id,
        props={
            "source": "flighthub2",
            "dock_sn": dock_sn,
            "aircraft_sn": task.get("aircraft_sn"),
            "inbound_auth": "disabled",
        },
    )
    return device_id


def pull_flight_task(
    task_uuid: str,
    *,
    client: Optional[FlightHubClient] = None,
    store: Optional[Store] = None,
    city_id: Optional[str] = None,
    vehicle_id: Optional[str] = None,
    camera_id: str = "AERIAL",
    work_dir: Optional[Path] = None,
    require_success: bool = True,
) -> Dict[str, Any]:
    """
    Fetch one task's video + trajectory and queue analysis.

    `vehicle_id` must already exist in the fleet (`vehicles.id`) — runs carry a foreign
    key, so the dock's aircraft serial is recorded as metadata instead of guessed here.
    """
    client = client or FlightHubClient()
    store = store or Store()
    settings = get_settings()
    city = city_id or settings.default_city
    work_root = Path(work_dir) if work_dir else settings.edge_upload_dir / "flighthub"

    task = client.get_flight_task(task_uuid)
    status = str(task.get("status") or "").lower()
    if require_success and status != TASK_STATUS_DONE:
        return {
            "task_uuid": task_uuid,
            "status": status,
            "skipped": "task not finished",
            "videos": [],
        }

    media = video_media(client.get_task_media(task_uuid))
    if not media:
        return {"task_uuid": task_uuid, "status": status, "skipped": "no video media", "videos": []}

    fixes = []
    trajectory_warning: Optional[str] = None
    try:
        fixes = parse_trajectory(
            client.get_task_trajectory(task_uuid), start_ms=task.get("begin_time")
        )
    except FlightHubError as exc:
        # A wrong provisional endpoint must not cost us the footage; the pipeline can
        # still fuse on pixels, it just cannot place events on the map.
        trajectory_warning = str(exc)
        log.warning("trajectory unavailable for task %s: %s", task_uuid, exc)
    if not fixes and trajectory_warning is None:
        trajectory_warning = "trajectory returned no usable points"

    device_id = _ensure_dock_device(store, task, city)
    obj = get_object_store()
    results: List[Dict[str, Any]] = []

    for item in media:
        url = str(item.get("original_url") or item.get("preview_url") or "").strip()
        if not url:
            results.append({"name": item.get("name"), "skipped": "no download url"})
            continue
        suffix = str(item.get("suffix") or ".mp4")
        filename = f"{item.get('name') or 'flight'}{suffix}"
        staging = work_root / task_uuid / filename
        client.download_to(url, staging)
        checksum = _sha256_file(staging)

        existing = store.find_video_by_checksum(device_id, checksum)
        if existing:
            staging.unlink(missing_ok=True)
            results.append(
                {
                    "name": filename,
                    "upload_id": existing.get("upload_id"),
                    "status": existing.get("status"),
                    "deduped": True,
                }
            )
            continue

        upload_id = uuid.uuid4().hex
        key_prefix = f"flighthub/{device_id}/{upload_id}"
        video_key = f"{key_prefix}/{filename}"
        obj.put_file(video_key, staging)

        gps_key = None
        if fixes:
            sidecar = write_gps_sidecar(fixes, staging.with_name("gps.jsonl"))
            gps_key = f"{key_prefix}/gps.jsonl"
            obj.put_file(gps_key, sidecar)
            sidecar.unlink(missing_ok=True)

        nbytes = staging.stat().st_size
        run_name = f"fh2-{task_uuid[:8]}-{upload_id[:6]}"
        store.create_edge_video_upload(
            upload_id,
            device_id,
            video_key,
            checksum,
            city_id=city,
            vehicle_id=vehicle_id,
            gps_object_key=gps_key,
            nbytes=nbytes,
            payload={
                "source": "flighthub2",
                "task_uuid": task_uuid,
                "task_name": task.get("name"),
                "media_uuid": item.get("uuid"),
                "filename": filename,
                "run_name": run_name,
                "camera_id": camera_id,
                "dock_sn": task.get("dock_sn"),
                "aircraft_sn": task.get("aircraft_sn"),
                "gps_fixes": len(fixes),
                "trajectory_warning": trajectory_warning,
            },
        )
        job_id, deduped = enqueue_job(
            store,
            "analyze_video",
            {
                "upload_id": upload_id,
                "object_key": video_key,
                "gps_object_key": gps_key,
                "city_id": city,
                "vehicle_id": vehicle_id,
                "camera_id": camera_id,
                "run_name": run_name,
            },
        )
        store.update_edge_video_upload(upload_id, status="queued", job_id=job_id)
        staging.unlink(missing_ok=True)
        results.append(
            {
                "name": filename,
                "upload_id": upload_id,
                "object_key": video_key,
                "gps_object_key": gps_key,
                "bytes": nbytes,
                "job_id": job_id,
                "job_deduped": deduped,
            }
        )

    return {
        "task_uuid": task_uuid,
        "status": status,
        "device_id": device_id,
        "gps_fixes": len(fixes),
        "trajectory_warning": trajectory_warning,
        "videos": results,
    }


def pull_completed_tasks(
    *,
    client: Optional[FlightHubClient] = None,
    store: Optional[Store] = None,
    city_id: Optional[str] = None,
    vehicle_id: Optional[str] = None,
    page_size: int = 20,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Walk the task list and pull every finished flight that is not already stored."""
    client = client or FlightHubClient()
    store = store or Store()
    tasks = client.list_flight_tasks(page=1, page_size=page_size)
    out: List[Dict[str, Any]] = []
    for task in tasks:
        if limit is not None and len(out) >= limit:
            break
        task_uuid = str(task.get("task_uuid") or task.get("uuid") or "").strip()
        if not task_uuid:
            continue
        if str(task.get("status") or "").lower() != TASK_STATUS_DONE:
            continue
        try:
            out.append(
                pull_flight_task(
                    task_uuid,
                    client=client,
                    store=store,
                    city_id=city_id,
                    vehicle_id=vehicle_id,
                )
            )
        except FlightHubError as exc:
            log.warning("pull failed for task %s: %s", task_uuid, exc)
            out.append({"task_uuid": task_uuid, "error": str(exc)})
    return out
