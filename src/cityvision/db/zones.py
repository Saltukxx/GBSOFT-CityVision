from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from cityvision.db.store import Store


def ingest_zones_geojson(
    path: str | Path,
    store: Store | None = None,
    city_id: str | None = None,
) -> Dict[str, Any]:
    """Load a GeoJSON FeatureCollection of zones into PostGIS."""
    path = Path(path).resolve()
    store = store or Store()
    from cityvision.settings import get_settings

    cid = city_id or get_settings().default_city
    data = json.loads(path.read_text(encoding="utf-8"))
    features = data.get("features") or []
    upserted: List[str] = []
    skipped = 0

    for i, feat in enumerate(features):
        if not isinstance(feat, dict):
            skipped += 1
            continue
        props = feat.get("properties") or {}
        geom = feat.get("geometry")
        if not geom or geom.get("type") not in {"Polygon", "MultiPolygon"}:
            skipped += 1
            continue
        zone_id = str(props.get("zone_id") or props.get("id") or f"zone-{i}")
        name = str(props.get("name") or zone_id)
        zone_type = str(props.get("type") or props.get("zone_type") or "bus_stop")
        # keep other props without duplicating identity keys
        extra = {
            k: v
            for k, v in props.items()
            if k not in {"zone_id", "id", "name", "type", "zone_type", "city_id"}
        }
        z_city = str(props.get("city_id") or cid)
        store.upsert_zone(zone_id, name, zone_type, geom, extra, city_id=z_city)
        upserted.append(zone_id)

    return {
        "path": str(path),
        "city_id": cid,
        "zones_upserted": len(upserted),
        "zone_ids": upserted,
        "skipped": skipped,
    }
