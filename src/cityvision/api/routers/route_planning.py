"""Planned drone routes: create/edit on the map, export for the pilot, compare with flights.

The plan requires the same corridor to be flown the same way every time
(plan.md §5), so a route carries the flight parameters, not just a line.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any, Optional
from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field, field_validator

from cityvision.api.deps import (
    Principal,
    get_principal,
    get_store,
    require_admin,
    require_city_row,
    require_operator,
    resolve_city_id,
)

router = APIRouter(prefix="/api/routes", tags=["route-planning"])

MAX_WAYPOINTS = 500


class RoutePlan(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    # [[lon, lat], ...] — GeoJSON order
    coordinates: list[list[float]] = Field(..., min_length=2, max_length=MAX_WAYPOINTS)
    altitude_m: float = Field(60, ge=5, le=500)
    speed_ms: float = Field(5, ge=0.5, le=25)
    gimbal_deg: float = Field(-90, ge=-90, le=0)
    preferred_time: Optional[str] = Field(None, max_length=40)
    notes: Optional[str] = Field(None, max_length=2000)

    @field_validator("coordinates")
    @classmethod
    def _valid_points(cls, pts: list[list[float]]) -> list[list[float]]:
        for p in pts:
            if len(p) < 2 or not (-180 <= p[0] <= 180) or not (-90 <= p[1] <= 90):
                raise ValueError("coordinates must be [lon, lat] pairs")
        return [[round(float(p[0]), 7), round(float(p[1]), 7)] for p in pts]

    def props(self) -> dict[str, Any]:
        return {
            "altitude_m": self.altitude_m,
            "speed_ms": self.speed_ms,
            "gimbal_deg": self.gimbal_deg,
            "preferred_time": self.preferred_time,
            "notes": self.notes,
            "planned": True,
        }


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "route"
    return f"{s}-{uuid.uuid4().hex[:6]}"


def _route_or_404(route_id: str, principal: Principal) -> dict[str, Any]:
    return require_city_row(get_store().get_route(route_id), principal, detail="route not found")


@router.get("/{route_id}")
def get_route(route_id: str, principal: Principal = Depends(get_principal)) -> dict[str, Any]:
    return _route_or_404(route_id, principal)


@router.post("/plan", status_code=201)
def create_route(body: RoutePlan, principal: Principal = Depends(require_operator)) -> dict[str, Any]:
    store = get_store()
    city = principal.city_id or resolve_city_id(principal, None)
    if not city:
        raise HTTPException(status_code=422, detail="city_required")
    rid = _slug(body.name)
    row = store.save_planned_route(
        rid, name=body.name.strip(), city_id=city, coordinates=body.coordinates, props=body.props(), actor=principal.username
    )
    store.add_audit(
        actor=principal.username,
        action="route_create",
        entity_type="route",
        entity_id=rid,
        detail={"name": body.name, "waypoints": len(body.coordinates)},
        city_id=city,
    )
    return row


@router.put("/{route_id}/plan")
def update_route(route_id: str, body: RoutePlan, principal: Principal = Depends(require_operator)) -> dict[str, Any]:
    store = get_store()
    existing = _route_or_404(route_id, principal)
    row = store.save_planned_route(
        route_id,
        name=body.name.strip(),
        city_id=existing.get("city_id") or existing.get("city"),
        coordinates=body.coordinates,
        props=body.props(),
        actor=principal.username,
    )
    store.add_audit(
        actor=principal.username,
        action="route_update",
        entity_type="route",
        entity_id=route_id,
        detail={"name": body.name, "waypoints": len(body.coordinates)},
        city_id=existing.get("city_id"),
    )
    return row


@router.delete("/{route_id}", status_code=204)
def delete_route(route_id: str, principal: Principal = Depends(require_admin)) -> None:
    store = get_store()
    existing = _route_or_404(route_id, principal)
    store.delete_route(route_id)
    store.add_audit(
        actor=principal.username,
        action="route_delete",
        entity_type="route",
        entity_id=route_id,
        detail={"name": existing.get("name")},
        city_id=existing.get("city_id"),
    )


def _coords(route: dict[str, Any]) -> list[list[float]]:
    geom = route.get("geometry") or {}
    if isinstance(geom, str):
        geom = json.loads(geom)
    return geom.get("coordinates") or []


@router.get("/{route_id}/export.kml")
def export_kml(route_id: str, principal: Principal = Depends(get_principal)) -> Response:
    """KML line + numbered waypoints at the planned height above ground.

    Opens in Google Earth and imports into DJI Pilot 2 as a route outline.
    """
    route = _route_or_404(route_id, principal)
    props = route.get("props") or {}
    alt = float(props.get("altitude_m") or 60)
    coords = _coords(route)
    if len(coords) < 2:
        raise HTTPException(status_code=409, detail="route has no line")
    line = " ".join(f"{lon},{lat},{alt:g}" for lon, lat in coords)
    marks = "\n".join(
        f"""    <Placemark><name>WP{i + 1}</name><styleUrl>#wp</styleUrl>
      <Point><altitudeMode>relativeToGround</altitudeMode><coordinates>{lon},{lat},{alt:g}</coordinates></Point></Placemark>"""
        for i, (lon, lat) in enumerate(coords)
    )
    desc = escape(
        f"Altitude {alt:g} m AGL · speed {props.get('speed_ms', 5)} m/s · gimbal {props.get('gimbal_deg', -90)}°"
        + (f" · {props['preferred_time']}" if props.get("preferred_time") else "")
        + (f"\n{props['notes']}" if props.get("notes") else "")
    )
    kml = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>{escape(route["name"])}</name>
    <description>{desc}</description>
    <Style id="route"><LineStyle><color>ffdac34c</color><width>4</width></LineStyle></Style>
    <Style id="wp"><IconStyle><scale>0.7</scale></IconStyle></Style>
    <Placemark>
      <name>{escape(route["name"])}</name>
      <styleUrl>#route</styleUrl>
      <LineString><altitudeMode>relativeToGround</altitudeMode><coordinates>{line}</coordinates></LineString>
    </Placemark>
{marks}
  </Document>
</kml>
"""
    filename = re.sub(r"[^A-Za-z0-9._-]+", "_", route["name"]) or route_id
    return Response(
        kml,
        media_type="application/vnd.google-earth.kml+xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}.kml"'},
    )


@router.get("/{route_id}/export.geojson")
def export_geojson(route_id: str, principal: Principal = Depends(get_principal)) -> Response:
    route = _route_or_404(route_id, principal)
    feature = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"id": route["id"], "name": route["name"], **(route.get("props") or {})},
                "geometry": {"type": "LineString", "coordinates": _coords(route)},
            }
        ],
    }
    filename = re.sub(r"[^A-Za-z0-9._-]+", "_", route["name"]) or route_id
    return Response(
        json.dumps(feature, indent=2),
        media_type="application/geo+json",
        headers={"Content-Disposition": f'attachment; filename="{filename}.geojson"'},
    )
