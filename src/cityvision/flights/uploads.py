"""Resumable browser uploads of flight video.

The browser sends the video in fixed-size chunks (any order, retried freely).
Chunks land in a per-upload staging folder; which chunks exist on disk *is* the
resume state, so an interrupted upload continues after a reload or a server
restart. Once every chunk is present a background job joins them, checks for a
duplicate, moves the file to object storage and starts video analysis.
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
import secrets
import shutil
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from cityvision.db.store import Store
from cityvision.settings import get_settings

log = logging.getLogger(__name__)

CHUNK_SIZE = 8 * 1024 * 1024
VIDEO_SUFFIXES = (".mp4", ".mov", ".mkv", ".avi")
TELEMETRY_SUFFIXES = (".srt", ".jsonl", ".json", ".csv")
TELEMETRY_MAX_BYTES = 50 * 1024 * 1024
PENDING_CHECKSUM_PREFIX = "pending:"

_UPLOAD_ID_RE = re.compile(r"^[0-9a-f]{32}$")


def valid_upload_id(upload_id: str) -> bool:
    return bool(_UPLOAD_ID_RE.match(upload_id))


def staging_dir(upload_id: str) -> Path:
    if not valid_upload_id(upload_id):
        raise ValueError("invalid upload id")
    return get_settings().edge_upload_dir / "flights" / upload_id


def chunk_count(size: int, chunk_size: Optional[int] = None) -> int:
    return max(1, math.ceil(size / (chunk_size or CHUNK_SIZE)))


def expected_chunk_bytes(index: int, size: int, chunk_size: Optional[int] = None) -> int:
    chunk_size = chunk_size or CHUNK_SIZE
    last = chunk_count(size, chunk_size) - 1
    if index < 0 or index > last:
        raise ValueError("chunk index out of range")
    return size - chunk_size * last if index == last else chunk_size


def chunk_path(upload_id: str, index: int) -> Path:
    return staging_dir(upload_id) / "chunks" / f"{index:06d}.part"


def received_chunks(upload_id: str) -> List[int]:
    folder = staging_dir(upload_id) / "chunks"
    if not folder.is_dir():
        return []
    out = []
    for p in folder.glob("*.part"):
        try:
            out.append(int(p.stem))
        except ValueError:
            continue
    return sorted(out)


def missing_chunks(upload_id: str, size: int) -> List[int]:
    have = set(received_chunks(upload_id))
    return [i for i in range(chunk_count(size)) if i not in have]


def telemetry_path(upload_id: str) -> Optional[Path]:
    folder = staging_dir(upload_id)
    for p in folder.glob("telemetry.*"):
        return p
    return None


def web_device_id(store: Store, city_id: Optional[str]) -> str:
    """Browser uploads hang off one synthetic device per city (FK on device_id).

    Its token hash is random and discarded, so it can never authenticate inbound.
    """
    device_id = f"web-{city_id or 'global'}"
    if not store.get_edge_device(device_id):
        store.upsert_edge_device(
            device_id,
            "Web upload",
            secrets.token_hex(32),
            city_id=city_id,
            props={"source": "web", "inbound_auth": "disabled"},
        )
    return device_id


def assemble(upload_id: str, size: int, dest: Path) -> str:
    """Join chunks into `dest`; returns the SHA-256 of the result."""
    missing = missing_chunks(upload_id, size)
    if missing:
        raise ValueError(f"{len(missing)} chunk(s) missing")
    digest = hashlib.sha256()
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as out:
        for i in range(chunk_count(size)):
            with chunk_path(upload_id, i).open("rb") as part:
                while True:
                    block = part.read(1024 * 1024)
                    if not block:
                        break
                    digest.update(block)
                    out.write(block)
    if dest.stat().st_size != size:
        raise ValueError("assembled file size does not match the declared size")
    return digest.hexdigest()


def finalize_and_analyze(
    store: Store,
    payload: Dict[str, Any],
    job_id: Optional[int],
    analyze: Callable[[Store, Dict[str, Any], Optional[int]], Dict[str, Any]],
) -> Dict[str, Any]:
    """Job body for `flight_upload`: assemble → dedupe → store → analyze."""
    from cityvision.storage import get_object_store

    upload_id = str(payload["upload_id"])
    row = store.get_edge_video_upload(upload_id)
    if not row:
        raise ValueError("flight upload not found")
    size = int(row.get("bytes") or 0)
    folder = staging_dir(upload_id)

    def report(p: float) -> None:
        if job_id is not None:
            store.set_job_progress(job_id, p)

    try:
        video = folder / f"video{Path(str(row['object_key'])).suffix or '.mp4'}"
        checksum = assemble(upload_id, size, video)
        report(0.03)

        existing = store.find_video_by_checksum(str(row["device_id"]), checksum)
        if existing and existing.get("upload_id") != upload_id:
            store.update_edge_video_upload(
                upload_id,
                status="duplicate",
                error="This video was already uploaded.",
                payload_merge={"duplicate_of": existing.get("upload_id")},
            )
            shutil.rmtree(folder, ignore_errors=True)
            return {"upload_id": upload_id, "duplicate_of": existing.get("upload_id")}

        obj = get_object_store()
        obj.put_file(str(row["object_key"]), video)
        gps_key = None
        tele = telemetry_path(upload_id)
        if tele is not None:
            gps_key = f"{Path(str(row['object_key'])).parent}/{tele.name.replace('telemetry', 'gps')}"
            obj.put_file(gps_key, tele)
        store.update_edge_video_upload(
            upload_id, status="queued", checksum=checksum, gps_object_key=gps_key
        )
        shutil.rmtree(folder, ignore_errors=True)
        report(0.08)

        analyze_payload = {
            "upload_id": upload_id,
            "object_key": row["object_key"],
            "gps_object_key": gps_key,
            "city_id": row.get("city_id"),
            "vehicle_id": row.get("vehicle_id"),
            "route_id": row.get("route_id"),
            "camera_id": "AERIAL",
            "run_name": (row.get("payload") or {}).get("name") or upload_id[:12],
            "progress_offset": 0.08,
        }
        return analyze(store, analyze_payload, job_id)
    except Exception as exc:
        store.update_edge_video_upload(upload_id, status="failed", error=str(exc))
        raise
