from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import yaml

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CLASSES = ROOT / "configs" / "classes.yaml"
DEFAULT_PIPELINE = ROOT / "configs" / "pipeline.yaml"


def load_yaml(path: Path | str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {path}")
    return data


def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge overlay into a copy of base (dicts only; lists replaced)."""
    out: dict[str, Any] = dict(base)
    for key, value in overlay.items():
        if (
            key in out
            and isinstance(out[key], dict)
            and isinstance(value, dict)
        ):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def load_class_config(path: Path | str | None = None) -> dict[str, Any]:
    return load_yaml(path or DEFAULT_CLASSES)


DEFAULT_PROFILE = "oblique"
PROFILE_DIR = ROOT / "configs" / "profiles"


def load_profile_overlay(profile: str) -> dict[str, Any]:
    """Load configs/profiles/<profile>.yaml (nadir | oblique)."""
    name = str(profile).strip()
    if not name:
        raise ValueError("pipeline profile name is empty")
    overlay_path = PROFILE_DIR / f"{name}.yaml"
    if not overlay_path.is_file():
        known = sorted(p.stem for p in PROFILE_DIR.glob("*.yaml"))
        raise FileNotFoundError(
            f"Unknown pipeline profile {name!r} ({overlay_path}). Known: {known}"
        )
    return load_yaml(overlay_path)


def load_pipeline_config(
    path: Path | str | None = None,
    *,
    city_id: Optional[str] = None,
    profile: Optional[str] = None,
) -> dict[str, Any]:
    """
    Load pipeline.yaml, optionally merged with a flight profile then
    configs/cities/<city_id>/pipeline.overlay.yaml.

    Merge order: base → profile → city overlay.
    """
    cfg = load_yaml(path or DEFAULT_PIPELINE)
    if profile:
        cfg = deep_merge(cfg, load_profile_overlay(profile))
        run_stamp = dict(cfg.get("run") or {})
        run_stamp["profile"] = str(profile).strip()
        cfg["run"] = run_stamp
    if not city_id:
        return cfg
    try:
        from cityvision.cities.pack import load_city_pack

        pack = load_city_pack(city_id)
    except FileNotFoundError:
        return cfg
    if pack.pipeline_overlay:
        cfg = deep_merge(cfg, pack.pipeline_overlay)
    # Stamp city metadata for downstream consumers (ingest summary, etc.)
    run = dict(cfg.get("run") or {})
    run.setdefault("city_id", pack.city_id)
    cfg["run"] = run
    geo = dict(cfg.get("geofence") or {})
    if pack.zones_path and not geo.get("path"):
        geo["path"] = str(pack.zones_path)
    cfg["geofence"] = geo
    return cfg


def coco_to_city_name(class_cfg: dict[str, Any]) -> dict[str, str]:
    """Map COCO class name → City Vision class name."""
    mapping: dict[str, str] = {}
    for item in class_cfg.get("classes", []):
        coco = item.get("coco_name")
        name = item.get("name")
        if coco and name:
            mapping[str(coco)] = str(name)
    return mapping


def normalize_label_key(name: str) -> str:
    """Normalize detector label for alias lookup (case/space/underscore-insensitive)."""
    cleaned = (
        str(name)
        .strip()
        .casefold()
        .replace("-", " ")
        .replace("_", " ")
    )
    return " ".join(cleaned.split())


def label_alias_map(class_cfg: dict[str, Any]) -> dict[str, str | None]:
    """
    External model label → City Vision name (or None to drop).

    Keys are stored normalized via normalize_label_key.
    """
    raw = class_cfg.get("label_aliases") or {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str | None] = {}
    for key, value in raw.items():
        norm = normalize_label_key(str(key))
        if not norm:
            continue
        if value is None:
            out[norm] = None
        else:
            out[norm] = str(value)
    return out


def taxonomy_names(class_cfg: dict[str, Any], model: str | None = None) -> set[str]:
    names: set[str] = set()
    for item in class_cfg.get("classes", []):
        name = item.get("name")
        if not name:
            continue
        if model is None or str(item.get("model")) == model:
            names.add(str(name))
    return names


def resolve_class_name(
    raw_name: str,
    class_cfg: dict[str, Any],
    *,
    bootstrap_coco_only: bool,
) -> str | None:
    """Resolve detector label to City Vision class, or None to drop."""
    known = taxonomy_names(class_cfg)
    if raw_name in known:
        return raw_name

    coco_map = coco_to_city_name(class_cfg)
    mapped = coco_map.get(raw_name)
    if mapped is not None:
        return mapped

    aliases = label_alias_map(class_cfg)
    alias_key = normalize_label_key(raw_name)
    if alias_key in aliases:
        return aliases[alias_key]

    if bootstrap_coco_only:
        return None
    return raw_name
