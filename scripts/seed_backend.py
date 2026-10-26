#!/usr/bin/env python3
"""Seed pilot drone, city pack, users, and assets for City Vision backend."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def _load_database_url() -> None:
    if os.environ.get("DATABASE_URL"):
        return
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("DATABASE_URL=") and len(line) > 13:
            os.environ["DATABASE_URL"] = line.split("=", 1)[1].strip().strip('"').strip("'")
            break


def main() -> int:
    _load_database_url()
    from cityvision.api.security import hash_password
    from cityvision.cities import apply_city_pack, load_city_pack
    from cityvision.db.store import Store
    from cityvision.settings import get_settings

    def _pw(password: str) -> str:
        return hash_password(password)

    get_settings.cache_clear()
    settings = get_settings()
    store = Store()

    city_id = settings.default_city
    pack_result: dict = {}
    try:
        pack = load_city_pack(city_id)
        pack_result = apply_city_pack(pack, store=store)
        route_id = (pack_result.get("routes") or ["R-17"])[0]
    except FileNotFoundError:
        store.upsert_city(city_id, city_id.title())
        from cityvision.db.zones import ingest_zones_geojson

        pack_result = {
            "zones": ingest_zones_geojson(
                ROOT / "configs" / "zones.example.geojson",
                store=store,
                city_id=city_id,
            )
        }
        route_id = store.upsert_route(
            "R-17",
            "Atatürk Cad. hat",
            city=city_id,
            linestring_lonlat=[
                [41.2700, 39.9170],
                [41.2732, 39.9181],
                [41.2720, 39.9218],
                [41.2719, 39.9220],
            ],
            props={"pilot": True},
        )

    drone_ids = ["DJI-DOCK-01"]
    for drone_id in drone_ids:
        # The compatibility schema still stores drone assets in vehicles.id.
        store.upsert_vehicle(drone_id, name=drone_id, route_id=route_id, city_id=city_id)

    store.upsert_camera("AERIAL", vehicle_id="DJI-DOCK-01", label="Drone kamerası", facing="aerial")

    store.upsert_user("operator", "Pilot Operatör", role="operator", password_hash=_pw("operator"), city_id=city_id)
    store.upsert_user("admin", "Sistem Yöneticisi", role="admin", password_hash=_pw("admin123"), city_id=city_id)
    store.upsert_user("viewer", "İzleyici", role="viewer", password_hash=_pw("viewer"), city_id=city_id)

    store.upsert_asset(
        "BIN-12",
        "bin",
        name="Konteyner 12",
        lat=39.92180,
        lon=41.27195,
        zone_id=None,
        city_id=city_id,
    )

    out = {
        "city_id": city_id,
        "city_pack": pack_result,
        "route_id": route_id,
        "drone_ids": drone_ids,
        "users": len(store.list_users()),
        "assets": len(store.list_assets()),
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
