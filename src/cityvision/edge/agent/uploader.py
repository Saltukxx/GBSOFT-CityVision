from __future__ import annotations

import json
import shutil
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def upload_video_file(
    *,
    api_base: str,
    token: str,
    video_path: Path,
    gps_path: Optional[Path] = None,
    vehicle_id: Optional[str] = None,
    city_id: Optional[str] = None,
    route_id: Optional[str] = None,
    run_name: Optional[str] = None,
    camera_id: Optional[str] = None,
    timeout_s: float = 120.0,
) -> Dict[str, Any]:
    """POST multipart to /api/edge/video. Returns JSON body."""
    import mimetypes

    # stdlib has no multipart helper — build manually
    boundary = f"----cvboundary{uuid.uuid4().hex}"
    body = bytearray()

    def _add_field(name: str, value: str) -> None:
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        body.extend(value.encode("utf-8"))
        body.extend(b"\r\n")

    def _add_file(name: str, path: Path, content_type: str) -> None:
        data = path.read_bytes()
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(
            (
                f'Content-Disposition: form-data; name="{name}"; '
                f'filename="{path.name}"\r\n'
            ).encode()
        )
        body.extend(f"Content-Type: {content_type}\r\n\r\n".encode())
        body.extend(data)
        body.extend(b"\r\n")

    if vehicle_id:
        _add_field("vehicle_id", vehicle_id)
    if city_id:
        _add_field("city_id", city_id)
    if route_id:
        _add_field("route_id", route_id)
    if run_name:
        _add_field("run_name", run_name)
    if camera_id:
        _add_field("camera_id", camera_id)

    ctype = mimetypes.guess_type(str(video_path))[0] or "video/mp4"
    _add_file("file", video_path, ctype)
    if gps_path and gps_path.is_file():
        gtype = "application/x-ndjson"
        if gps_path.suffix.lower() == ".csv":
            gtype = "text/csv"
        elif gps_path.suffix.lower() == ".json":
            gtype = "application/json"
        _add_file("gps", gps_path, gtype)

    body.extend(f"--{boundary}--\r\n".encode())

    url = api_base.rstrip("/") + "/api/edge/video"
    req = Request(
        url,
        data=bytes(body),
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "X-Edge-Token": token,
        },
        method="POST",
    )
    with urlopen(req, timeout=timeout_s) as resp:
        return json.loads(resp.read().decode("utf-8"))


def heartbeat(
    *,
    api_base: str,
    token: str,
    props: Optional[Dict[str, Any]] = None,
    timeout_s: float = 15.0,
) -> Dict[str, Any]:
    url = api_base.rstrip("/") + "/api/edge/heartbeat"
    payload = json.dumps({"props": props or {}}).encode("utf-8")
    req = Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-Edge-Token": token,
        },
        method="POST",
    )
    with urlopen(req, timeout=timeout_s) as resp:
        return json.loads(resp.read().decode("utf-8"))


def upload_with_outbox(
    *,
    api_base: str,
    token: str,
    video_path: Path,
    outbox_dir: Path,
    gps_path: Optional[Path] = None,
    max_retries: int = 5,
    backoff_s: float = 2.0,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Try upload; on network/HTTP failure copy into outbox and retry with backoff.
    """
    outbox_dir = Path(outbox_dir)
    outbox_dir.mkdir(parents=True, exist_ok=True)
    last_err: Optional[Exception] = None
    for attempt in range(max_retries):
        try:
            return upload_video_file(
                api_base=api_base,
                token=token,
                video_path=video_path,
                gps_path=gps_path,
                **kwargs,
            )
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            last_err = exc
            time.sleep(backoff_s * (2**attempt))

    # Persist to outbox for later drain
    stamp = uuid.uuid4().hex[:10]
    dest = outbox_dir / stamp
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(video_path, dest / video_path.name)
    meta = {
        "video": video_path.name,
        "gps": gps_path.name if gps_path else None,
        "kwargs": {k: v for k, v in kwargs.items() if v is not None},
        "error": str(last_err),
    }
    if gps_path and gps_path.is_file():
        shutil.copy2(gps_path, dest / gps_path.name)
    (dest / "meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    raise RuntimeError(
        f"upload failed after {max_retries} attempts; queued in {dest}: {last_err}"
    ) from last_err


def drain_outbox(
    *,
    api_base: str,
    token: str,
    outbox_dir: Path,
) -> list[Dict[str, Any]]:
    """Retry pending outbox packages; remove on success."""
    outbox_dir = Path(outbox_dir)
    results: list[Dict[str, Any]] = []
    if not outbox_dir.is_dir():
        return results
    for dest in sorted(outbox_dir.iterdir()):
        if not dest.is_dir():
            continue
        meta_path = dest / "meta.json"
        if not meta_path.is_file():
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        video = dest / meta["video"]
        gps = dest / meta["gps"] if meta.get("gps") else None
        if not video.is_file():
            continue
        try:
            body = upload_video_file(
                api_base=api_base,
                token=token,
                video_path=video,
                gps_path=gps if gps and gps.is_file() else None,
                **(meta.get("kwargs") or {}),
            )
            results.append({"outbox": str(dest), "ok": True, "response": body})
            shutil.rmtree(dest, ignore_errors=True)
        except Exception as exc:  # noqa: BLE001
            results.append({"outbox": str(dest), "ok": False, "error": str(exc)})
    return results
