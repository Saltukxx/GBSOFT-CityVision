#!/usr/bin/env python3
"""Ingest GeoJSON zones into PostGIS."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "geojson",
        nargs="?",
        default=str(ROOT / "configs" / "zones.example.geojson"),
        help="GeoJSON FeatureCollection of zones",
    )
    args = parser.parse_args()

    env_path = ROOT / ".env"
    if env_path.exists() and not os.environ.get("DATABASE_URL"):
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("DATABASE_URL=") and len(line) > 13:
                os.environ["DATABASE_URL"] = line.split("=", 1)[1].strip().strip('"').strip("'")
                break

    from cityvision.db.zones import ingest_zones_geojson

    print(json.dumps(ingest_zones_geojson(args.geojson), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
