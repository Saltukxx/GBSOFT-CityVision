"""Edge device token hashing and run-package extraction."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import zipfile
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from cityvision.settings import get_settings


def generate_edge_token() -> str:
    return secrets.token_urlsafe(32)


def hash_edge_token(token: str) -> str:
    """Deterministic token hash (pepper from JWT secret when set)."""
    settings = get_settings()
    pepper = settings.jwt_secret or settings.api_key or "cityvision-edge"
    return hashlib.sha256(f"{pepper}:{token}".encode("utf-8")).hexdigest()


def verify_edge_token(token: str, token_hash: str) -> bool:
    return hmac.compare_digest(hash_edge_token(token), token_hash)


def safe_extract_zip(zip_path: Path, dest: Path) -> Path:
    """
    Extract zip under dest with zip-slip protection.
    Returns the directory that contains events.json.
    """
    dest = dest.resolve()
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        for info in zf.infolist():
            name = info.filename
            if name.endswith("/"):
                continue
            target = (dest / name).resolve()
            try:
                target.relative_to(dest)
            except ValueError as exc:
                raise ValueError(f"zip path traversal blocked: {name}") from exc
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info, "r") as src, open(target, "wb") as out:
                out.write(src.read())

    events = _find_events_json(dest)
    if events is None:
        raise ValueError("uploaded package missing events.json")
    return events.parent


def _find_events_json(root: Path) -> Optional[Path]:
    direct = root / "events.json"
    if direct.is_file():
        return direct
    matches = list(root.rglob("events.json"))
    if not matches:
        return None
    matches.sort(key=lambda p: len(p.relative_to(root).parts))
    return matches[0]


def ensure_run_summary(
    run_dir: Path,
    *,
    city_id: Optional[str],
    vehicle_id: Optional[str],
    device_id: str,
    upload_id: str,
) -> Dict[str, Any]:
    """Merge edge metadata into summary.json (create if absent)."""
    summary_path = run_dir / "summary.json"
    summary: Dict[str, Any] = {}
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if not isinstance(summary, dict):
            summary = {}
    if city_id and not summary.get("city_id"):
        summary["city_id"] = city_id
    if vehicle_id and not summary.get("vehicle_id"):
        summary["vehicle_id"] = vehicle_id
    summary["edge_device_id"] = device_id
    summary["edge_upload_id"] = upload_id
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return summary


def validate_events_json(run_dir: Path) -> Tuple[int, list]:
    path = run_dir / "events.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("events.json must be a JSON array")
    return len(data), data
