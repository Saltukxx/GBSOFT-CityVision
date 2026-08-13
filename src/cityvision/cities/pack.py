"""City configuration packs — per-municipality zones/routes overlays."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from cityvision.config import ROOT


@dataclass
class CityPack:
    city_id: str
    name: str
    timezone: str = "Europe/Istanbul"
    root: Path = field(default_factory=lambda: ROOT / "configs" / "cities")
    zones_path: Optional[Path] = None
    routes: List[Dict[str, Any]] = field(default_factory=list)
    props: Dict[str, Any] = field(default_factory=dict)
    pipeline_overlay: Dict[str, Any] = field(default_factory=dict)

    @property
    def pack_dir(self) -> Path:
        return self.root / self.city_id


def cities_root(repo: Optional[Path] = None) -> Path:
    return (repo or ROOT) / "configs" / "cities"


def list_city_packs(repo: Optional[Path] = None) -> List[str]:
    root = cities_root(repo)
    if not root.is_dir():
        return []
    out = []
    for p in sorted(root.iterdir()):
        if p.is_dir() and (p / "city.yaml").exists():
            out.append(p.name)
    return out


def load_city_pack(city_id: str, repo: Optional[Path] = None) -> CityPack:
    root = cities_root(repo)
    pack_dir = root / city_id
    city_yaml = pack_dir / "city.yaml"
    if not city_yaml.exists():
        raise FileNotFoundError(f"city pack missing: {city_yaml}")

    data = yaml.safe_load(city_yaml.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"invalid city.yaml in {pack_dir}")

    zones_rel = data.get("zones") or "zones.geojson"
    zones_path = pack_dir / zones_rel
    if not zones_path.exists():
        zones_path = None

    overlay: Dict[str, Any] = {}
    overlay_path = pack_dir / "pipeline.overlay.yaml"
    if overlay_path.exists():
        loaded = yaml.safe_load(overlay_path.read_text(encoding="utf-8")) or {}
        if isinstance(loaded, dict):
            overlay = loaded

    return CityPack(
        city_id=str(data.get("id") or city_id),
        name=str(data.get("name") or city_id),
        timezone=str(data.get("timezone") or "Europe/Istanbul"),
        root=root,
        zones_path=zones_path,
        routes=list(data.get("routes") or []),
        props=dict(data.get("props") or {}),
        pipeline_overlay=overlay,
    )


def apply_city_pack(pack: CityPack, store=None) -> Dict[str, Any]:
    """Upsert city row, zones, and optional routes into the database."""
    from cityvision.db.store import Store
    from cityvision.db.zones import ingest_zones_geojson

    store = store or Store()
    store.upsert_city(pack.city_id, pack.name, timezone=pack.timezone)

    zones_result: Dict[str, Any] = {"zones_upserted": 0, "zone_ids": []}
    if pack.zones_path and pack.zones_path.exists():
        zones_result = ingest_zones_geojson(
            pack.zones_path, store=store, city_id=pack.city_id
        )

    route_ids = []
    for route in pack.routes:
        if not isinstance(route, dict) or not route.get("id"):
            continue
        rid = store.upsert_route(
            str(route["id"]),
            str(route.get("name") or route["id"]),
            city=pack.city_id,
            linestring_lonlat=route.get("coordinates"),
            props=route.get("props"),
        )
        route_ids.append(rid)

    return {
        "city_id": pack.city_id,
        "name": pack.name,
        "zones": zones_result,
        "routes": route_ids,
    }
