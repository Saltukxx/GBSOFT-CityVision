from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any, Dict, Generator, List, Optional

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from cityvision.settings import get_settings


def database_url() -> str:
    return get_settings().database_url


class Store:
    """PostgreSQL + PostGIS event store."""

    def __init__(self, dsn: str | None = None):
        self.dsn = dsn or database_url()
        self._tx_conn: Optional[psycopg.Connection] = None

    def _commit(self, conn: psycopg.Connection) -> None:
        """Commit unless an outer transaction() owns the connection."""
        if self._tx_conn is not None:
            return
        conn.commit()

    @contextmanager
    def transaction(self) -> Generator["Store", None, None]:
        """Run nested Store writes in a single DB transaction."""
        if self._tx_conn is not None:
            yield self
            return
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            self._tx_conn = conn
            try:
                yield self
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                self._tx_conn = None

    @contextmanager
    def connect(self) -> Generator[psycopg.Connection, None, None]:
        if self._tx_conn is not None:
            yield self._tx_conn
            return
        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            yield conn

    def ping(self) -> bool:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 AS ok, PostGIS_Version() AS postgis")
                row = cur.fetchone()
                return bool(row and row.get("ok") == 1)

    def upsert_city(self, city_id: str, name: str, timezone: str = "Europe/Istanbul") -> str:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO cities (id, name, timezone)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                      name = EXCLUDED.name,
                      timezone = EXCLUDED.timezone
                    RETURNING id
                    """,
                    (city_id, name, timezone),
                )
                row = cur.fetchone()
            self._commit(conn)
            return str(row["id"])

    def list_cities(self) -> List[Dict[str, Any]]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, name, timezone, props, created_at FROM cities ORDER BY id"
                )
                return [_serialize_row(r) for r in cur.fetchall()]

    def upsert_run(self, run_dir: str, meta: Dict[str, Any], summary: Dict[str, Any]) -> int:
        from cityvision.settings import get_settings

        city_id = meta.get("city_id") or get_settings().default_city
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO runs (run_dir, source, vehicle_id, camera_id, model_a, model_b, summary, city_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (run_dir) DO UPDATE SET
                      source = EXCLUDED.source,
                      vehicle_id = EXCLUDED.vehicle_id,
                      camera_id = EXCLUDED.camera_id,
                      model_a = EXCLUDED.model_a,
                      model_b = EXCLUDED.model_b,
                      summary = EXCLUDED.summary,
                      city_id = COALESCE(EXCLUDED.city_id, runs.city_id)
                    RETURNING id
                    """,
                    (
                        run_dir,
                        meta.get("source"),
                        meta.get("vehicle_id"),
                        meta.get("camera_id"),
                        meta.get("model_a"),
                        Jsonb(meta["model_b"]) if meta.get("model_b") is not None else None,
                        Jsonb(summary),
                        city_id,
                    ),
                )
                row = cur.fetchone()
            self._commit(conn)
            return int(row["id"])

    def upsert_event(self, run_id: int, event: Dict[str, Any]) -> None:
        vehicle_ids = event.get("vehicle_ids") or []
        camera_ids = event.get("camera_ids") or []
        vehicle_id = event.get("vehicle_id") or (vehicle_ids[0] if vehicle_ids else None)
        camera_id = event.get("camera_id") or (camera_ids[0] if camera_ids else None)
        zone_id = event.get("zone_id")
        lat, lon = event.get("lat"), event.get("lon")
        from cityvision.settings import get_settings

        city_id = event.get("city_id") or get_settings().default_city

        with self.connect() as conn:
            with conn.cursor() as cur:
                if not zone_id and lat is not None and lon is not None:
                    cur.execute(
                        """
                        SELECT zone_id FROM zones
                        WHERE geom IS NOT NULL
                          AND (city_id IS NULL OR city_id = %s)
                          AND ST_Covers(
                                geom,
                                ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography
                              )
                        ORDER BY zone_id
                        LIMIT 1
                        """,
                        (city_id, lon, lat),
                    )
                    zrow = cur.fetchone()
                    if zrow:
                        zone_id = zrow["zone_id"]
                        event = {**event, "zone_id": zone_id}

                cur.execute(
                    """
                    INSERT INTO events (
                      event_id, run_id, type, lat, lon, severity, confidence, confidence_band,
                      observations, status, model_version, zone_id, evidence_dir, payload,
                      first_seen_ms, last_seen_ms, vehicle_id, camera_id, route_id, city_id
                    ) VALUES (
                      %s, %s, %s, %s, %s, %s, %s, %s,
                      %s, %s, %s, %s, %s, %s,
                      %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (event_id) DO UPDATE SET
                      run_id = EXCLUDED.run_id,
                      type = EXCLUDED.type,
                      lat = COALESCE(EXCLUDED.lat, events.lat),
                      lon = COALESCE(EXCLUDED.lon, events.lon),
                      severity = EXCLUDED.severity,
                      confidence = GREATEST(
                        COALESCE(events.confidence, 0),
                        COALESCE(EXCLUDED.confidence, 0)
                      ),
                      confidence_band = EXCLUDED.confidence_band,
                      observations = GREATEST(
                        COALESCE(events.observations, 0),
                        COALESCE(EXCLUDED.observations, 0)
                      ),
                      -- Never reset operator-owned municipal status from pipeline re-ingest
                      status = CASE
                        WHEN events.status IN (
                          'confirmed', 'false_positive', 'work_order_created',
                          'resolved', 'archived'
                        ) THEN events.status
                        ELSE EXCLUDED.status
                      END,
                      model_version = COALESCE(EXCLUDED.model_version, events.model_version),
                      zone_id = COALESCE(events.zone_id, EXCLUDED.zone_id),
                      evidence_dir = COALESCE(EXCLUDED.evidence_dir, events.evidence_dir),
                      payload = EXCLUDED.payload,
                      first_seen_ms = COALESCE(
                        LEAST(events.first_seen_ms, EXCLUDED.first_seen_ms),
                        events.first_seen_ms,
                        EXCLUDED.first_seen_ms
                      ),
                      last_seen_ms = COALESCE(
                        GREATEST(events.last_seen_ms, EXCLUDED.last_seen_ms),
                        events.last_seen_ms,
                        EXCLUDED.last_seen_ms
                      ),
                      vehicle_id = COALESCE(events.vehicle_id, EXCLUDED.vehicle_id),
                      camera_id = COALESCE(events.camera_id, EXCLUDED.camera_id),
                      route_id = COALESCE(events.route_id, EXCLUDED.route_id),
                      city_id = COALESCE(events.city_id, EXCLUDED.city_id)
                    """,
                    (
                        event.get("event_id"),
                        run_id,
                        event.get("type"),
                        lat,
                        lon,
                        event.get("severity"),
                        event.get("confidence"),
                        event.get("confidence_band"),
                        event.get("observations") or 1,
                        event.get("status") or "under_review",
                        event.get("model_version"),
                        zone_id,
                        event.get("evidence_dir"),
                        Jsonb(event),
                        event.get("first_seen_ms") or event.get("first_seen"),
                        event.get("last_seen_ms") or event.get("last_seen"),
                        vehicle_id,
                        camera_id,
                        event.get("route_id"),
                        city_id,
                    ),
                )
            self._commit(conn)

    def find_canonical_for_source_id(self, source_event_id: str) -> Optional[str]:
        """If source_event_id was previously merged into another event, return canonical id."""
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT event_id
                    FROM events
                    WHERE payload->'merged_from' ? %s
                    ORDER BY updated_at DESC
                    LIMIT 1
                    """,
                    (source_event_id,),
                )
                row = cur.fetchone()
        return str(row["event_id"]) if row else None

    def find_merge_candidate(
        self,
        event_type: str,
        lat: float,
        lon: float,
        radius_m: float = 15.0,
        exclude_event_id: Optional[str] = None,
        city_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Nearest same-type event within radius (PostGIS), for cross-run fusion."""
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT event_id, type, lat, lon, severity, confidence, confidence_band,
                           observations, status, model_version, zone_id, evidence_dir, payload,
                           first_seen_ms, last_seen_ms, vehicle_id, camera_id, route_id, run_id,
                           city_id,
                           ST_Distance(
                             geom,
                             ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography
                           ) AS distance_m
                    FROM events
                    WHERE type = %s
                      AND geom IS NOT NULL
                      AND COALESCE(status, '') <> 'archived'
                      AND (%s::text IS NULL OR event_id <> %s)
                      AND (%s::text IS NULL OR city_id = %s)
                      AND ST_DWithin(
                            geom,
                            ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                            %s
                          )
                    ORDER BY distance_m ASC, updated_at DESC
                    LIMIT 1
                    """,
                    (
                        lon,
                        lat,
                        event_type,
                        exclude_event_id,
                        exclude_event_id,
                        city_id,
                        city_id,
                        lon,
                        lat,
                        radius_m,
                    ),
                )
                row = cur.fetchone()
        return _serialize_row(row) if row else None

    def sync_observation_count(self, event_id: str) -> int:
        """Set events.observations from COUNT(observations) for this event."""
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE events e
                    SET observations = sub.c
                    FROM (
                      SELECT COUNT(*)::int AS c FROM observations WHERE event_id = %s
                    ) sub
                    WHERE e.event_id = %s
                    RETURNING e.observations
                    """,
                    (event_id, event_id),
                )
                row = cur.fetchone()
            self._commit(conn)
        return int(row["observations"]) if row else 0

    def merge_into_event(
        self,
        canonical_event_id: str,
        run_id: int,
        incoming: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Fold a new sighting into an existing event (cross-bus / cross-run).

        Updates observation count, confidence, time span, and payload.merged_from.
        """
        from cityvision.events.confidence import (
            composite_confidence,
            confidence_band,
            severity_from_class,
        )

        existing = self.get_event(canonical_event_id)
        if not existing:
            raise KeyError(f"canonical event not found: {canonical_event_id}")

        payload = dict(existing.get("payload") or {})
        if not isinstance(payload, dict):
            payload = {}

        incoming_vids = [str(v) for v in (incoming.get("vehicle_ids") or [])]
        if incoming.get("vehicle_id"):
            incoming_vids.append(str(incoming["vehicle_id"]))
        existing_vids = [str(v) for v in (payload.get("vehicle_ids") or [])]
        if existing.get("vehicle_id"):
            existing_vids.append(str(existing["vehicle_id"]))
        vehicle_ids = sorted({*existing_vids, *incoming_vids})

        camera_ids = sorted(
            {
                *[str(c) for c in (payload.get("camera_ids") or [])],
                *[str(c) for c in (incoming.get("camera_ids") or [])],
                *([str(existing["camera_id"])] if existing.get("camera_id") else []),
                *([str(incoming["camera_id"])] if incoming.get("camera_id") else []),
            }
        )

        add_obs = int(incoming.get("observations") or 1)
        new_obs = int(existing.get("observations") or 1) + add_obs
        ai_conf = max(
            float(existing.get("confidence") or 0.0),
            float(incoming.get("confidence") or 0.0),
        )
        # Strip prior composite bonuses roughly: use max raw-ish conf from payloads if present
        for src in (payload, incoming):
            if isinstance(src, dict) and src.get("ai_confidence") is not None:
                ai_conf = max(ai_conf, float(src["ai_confidence"]))

        score = composite_confidence(
            ai_conf=min(ai_conf, 1.0),
            observations=new_obs,
            has_gps=existing.get("lat") is not None or incoming.get("lat") is not None,
            multi_vehicle=len(vehicle_ids) > 1,
        )
        bands = {"discard": 0.70, "review": 0.85, "probable": 0.95}
        band = confidence_band(score, bands)
        event_type = str(existing.get("type") or incoming.get("type") or "unknown")
        severity = severity_from_class(event_type, score)

        merged_from = list(payload.get("merged_from") or [])
        incoming_id = str(incoming.get("event_id") or "")
        if incoming_id and incoming_id not in merged_from and incoming_id != canonical_event_id:
            merged_from.append(incoming_id)

        first_seen = existing.get("first_seen_ms")
        last_seen = existing.get("last_seen_ms")
        inc_first = incoming.get("first_seen_ms") or incoming.get("first_seen")
        inc_last = incoming.get("last_seen_ms") or incoming.get("last_seen")
        if inc_first is not None:
            first_seen = min(float(first_seen), float(inc_first)) if first_seen is not None else float(inc_first)
        if inc_last is not None:
            last_seen = max(float(last_seen), float(inc_last)) if last_seen is not None else float(inc_last)

        payload.update(
            {
                "vehicle_ids": vehicle_ids,
                "camera_ids": camera_ids,
                "merged_from": merged_from,
                "observations": new_obs,
                "confidence": round(score, 4),
                "confidence_band": band,
                "severity": severity,
                "last_merge_run_id": run_id,
            }
        )

        status = existing.get("status") or "under_review"
        if status == "archived" and band != "discard":
            status = "under_review"

        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE events SET
                      observations = %s,
                      confidence = %s,
                      confidence_band = %s,
                      severity = %s,
                      status = %s,
                      first_seen_ms = %s,
                      last_seen_ms = %s,
                      vehicle_id = COALESCE(vehicle_id, %s),
                      camera_id = COALESCE(camera_id, %s),
                      route_id = COALESCE(route_id, %s),
                      zone_id = COALESCE(zone_id, %s),
                      evidence_dir = COALESCE(evidence_dir, %s),
                      payload = %s,
                      run_id = COALESCE(run_id, %s)
                    WHERE event_id = %s
                    """,
                    (
                        new_obs,
                        round(score, 4),
                        band,
                        severity,
                        status,
                        first_seen,
                        last_seen,
                        incoming.get("vehicle_id") or (incoming_vids[0] if incoming_vids else None),
                        incoming.get("camera_id"),
                        incoming.get("route_id"),
                        incoming.get("zone_id"),
                        incoming.get("evidence_dir"),
                        Jsonb(payload),
                        run_id,
                        canonical_event_id,
                    ),
                )
            self._commit(conn)

        return self.get_event(canonical_event_id) or {"event_id": canonical_event_id}

    def list_events(
        self,
        status: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 200,
        city_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        clauses = ["1=1"]
        args: List[Any] = []
        if status:
            clauses.append("status = %s")
            args.append(status)
        if event_type:
            clauses.append("type = %s")
            args.append(event_type)
        if city_id:
            clauses.append("city_id = %s")
            args.append(city_id)
        args.append(limit)
        sql = f"""
            SELECT id, event_id, run_id, type, lat, lon, severity, confidence,
                   confidence_band, observations, status, model_version, zone_id,
                   evidence_dir, payload, first_seen_ms, last_seen_ms,
                   vehicle_id, camera_id, route_id, city_id,
                   created_at, updated_at
            FROM events
            WHERE {' AND '.join(clauses)}
            ORDER BY updated_at DESC
            LIMIT %s
        """
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, args)
                rows = cur.fetchall()
        return [_serialize_row(r) for r in rows]

    def get_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, event_id, run_id, type, lat, lon, severity, confidence,
                           confidence_band, observations, status, model_version, zone_id,
                           evidence_dir, payload, first_seen_ms, last_seen_ms,
                           vehicle_id, camera_id, route_id, city_id,
                           created_at, updated_at
                    FROM events WHERE event_id = %s
                    """,
                    (event_id,),
                )
                row = cur.fetchone()
        return _serialize_row(row) if row else None

    def update_event_status(
        self,
        event_id: str,
        status: str,
        *,
        actor: str = "system",
    ) -> bool:
        from cityvision.domain.statuses import EVENT_STATUSES

        if status not in EVENT_STATUSES:
            raise ValueError(f"unsupported event status: {status}")
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE events SET status = %s WHERE event_id = %s",
                    (status, event_id),
                )
                ok = cur.rowcount > 0
            self._commit(conn)
        if ok:
            self.add_audit(
                actor=actor,
                action="event_status",
                entity_type="event",
                entity_id=event_id,
                detail={"status": status},
            )
        return ok

    def create_work_order(
        self, event_id: str, unit: str, note: str = "", *, actor: str = "system"
    ) -> int:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO work_orders (event_id, unit, note)
                    VALUES (%s, %s, %s)
                    RETURNING id
                    """,
                    (event_id, unit, note),
                )
                row = cur.fetchone()
                cur.execute(
                    "UPDATE events SET status = %s WHERE event_id = %s",
                    ("work_order_created", event_id),
                )
            self._commit(conn)
            wid = int(row["id"])
        self.add_audit(
            actor=actor,
            action="work_order_create",
            entity_type="work_order",
            entity_id=str(wid),
            detail={"event_id": event_id, "unit": unit, "note": note},
        )
        _notify_webhook(
            {
                "type": "work_order_created",
                "work_order_id": wid,
                "event_id": event_id,
                "unit": unit,
            }
        )
        return wid

    def update_work_order(
        self,
        work_order_id: int,
        status: Optional[str] = None,
        note: Optional[str] = None,
        assignee: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        from cityvision.domain.statuses import WORK_ORDER_STATUSES

        if status is not None and status not in WORK_ORDER_STATUSES:
            raise ValueError(f"unsupported work order status: {status}")
        sets = ["updated_at = NOW()"]
        args: List[Any] = []
        if status is not None:
            sets.append("status = %s")
            args.append(status)
        if note is not None:
            sets.append("note = %s")
            args.append(note)
        if assignee is not None:
            sets.append("assignee = %s")
            args.append(assignee)
        args.append(work_order_id)
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE work_orders SET {', '.join(sets)}
                    WHERE id = %s
                    RETURNING id, event_id, unit, note, status, assignee, created_at, updated_at
                    """,
                    args,
                )
                row = cur.fetchone()
                if row and status == "resolved":
                    cur.execute(
                        "UPDATE events SET status = %s WHERE event_id = %s",
                        ("resolved", row["event_id"]),
                    )
            self._commit(conn)
        if row:
            self.add_audit(
                actor=assignee or "system",
                action="work_order_update",
                entity_type="work_order",
                entity_id=str(work_order_id),
                detail={"status": status, "note": note, "assignee": assignee},
            )
        return _serialize_row(row) if row else None

        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, event_id, unit, note, status, assignee, created_at, updated_at
                    FROM work_orders WHERE id = %s
                    """,
                    (work_order_id,),
                )
                row = cur.fetchone()
        return _serialize_row(row) if row else None

    def get_work_order(self, work_order_id: int) -> Optional[Dict[str, Any]]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, event_id, unit, note, status, assignee, created_at, updated_at
                    FROM work_orders WHERE id = %s
                    """,
                    (work_order_id,),
                )
                row = cur.fetchone()
        return _serialize_row(row) if row else None

    def kpis(self, city_id: Optional[str] = None) -> Dict[str, Any]:
        city_clause = " AND city_id = %s" if city_id else ""
        city_args: List[Any] = [city_id] if city_id else []
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) AS c FROM events WHERE 1=1{city_clause}", city_args)
                total = cur.fetchone()["c"]
                cur.execute(
                    f"SELECT type, COUNT(*) AS c FROM events WHERE 1=1{city_clause} GROUP BY type ORDER BY c DESC",
                    city_args,
                )
                by_type = cur.fetchall()
                cur.execute(
                    f"SELECT status, COUNT(*) AS c FROM events WHERE 1=1{city_clause} GROUP BY status ORDER BY c DESC",
                    city_args,
                )
                by_status = cur.fetchall()
                cur.execute(
                    f"""
                    SELECT COUNT(*) AS c FROM events
                    WHERE (status = 'under_review' OR confidence_band = 'manual_review')
                    {city_clause}
                    """,
                    city_args,
                )
                review = cur.fetchone()["c"]
                cur.execute(
                    f"""
                    SELECT type, COUNT(*) AS c FROM events
                    WHERE created_at >= date_trunc('day', NOW())
                    {city_clause}
                    GROUP BY type ORDER BY c DESC
                    """,
                    city_args,
                )
                today_by_type = cur.fetchall()
                cur.execute(
                    f"""
                    SELECT COUNT(*) AS c FROM events
                    WHERE created_at >= date_trunc('day', NOW())
                    {city_clause}
                    """,
                    city_args,
                )
                today_total = cur.fetchone()["c"]
                cur.execute(
                    """
                    SELECT COUNT(*) AS c FROM work_orders
                    WHERE status NOT IN ('resolved', 'cancelled')
                    """
                )
                open_wo = cur.fetchone()["c"]
        out = {
            "events_total": total,
            "review_queue": review,
            "by_type": {r["type"]: r["c"] for r in by_type if r["type"]},
            "by_status": {r["status"]: r["c"] for r in by_status if r["status"]},
            "today_total": today_total,
            "today_by_type": {r["type"]: r["c"] for r in today_by_type if r["type"]},
            "open_work_orders": open_wo,
        }
        if city_id:
            out["city_id"] = city_id
        return out

    def list_runs(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, run_dir, source, vehicle_id, camera_id, model_a, model_b, created_at
                    FROM runs ORDER BY id DESC LIMIT %s
                    """,
                    (limit,),
                )
                rows = cur.fetchall()
        return [_serialize_row(r) for r in rows]

    def get_run(self, run_id: int) -> Optional[Dict[str, Any]]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, run_dir, source, vehicle_id, camera_id, model_a, model_b, summary, city_id, created_at
                    FROM runs WHERE id = %s
                    """,
                    (run_id,),
                )
                row = cur.fetchone()
        return _serialize_row(row) if row else None

    def events_near(
        self, lat: float, lon: float, radius_m: float = 50.0, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """PostGIS spatial lookup around a point."""
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT event_id, type, lat, lon, status, confidence,
                           ST_Distance(
                             geom,
                             ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography
                           ) AS distance_m
                    FROM events
                    WHERE geom IS NOT NULL
                      AND ST_DWithin(
                            geom,
                            ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                            %s
                          )
                    ORDER BY distance_m
                    LIMIT %s
                    """,
                    (lon, lat, lon, lat, radius_m, limit),
                )
                rows = cur.fetchall()
        return [_serialize_row(r) for r in rows]

    def upsert_zone(
        self,
        zone_id: str,
        name: str,
        zone_type: str,
        geometry: Dict[str, Any],
        props: Optional[Dict[str, Any]] = None,
        city_id: Optional[str] = None,
    ) -> str:
        """Upsert a zone from a GeoJSON geometry dict (Polygon / MultiPolygon)."""
        from cityvision.settings import get_settings

        geom_json = json.dumps(geometry)
        cid = city_id or get_settings().default_city
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO zones (zone_id, name, zone_type, geom, props, city_id)
                    VALUES (
                      %s, %s, %s,
                      ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)::geography,
                      %s, %s
                    )
                    ON CONFLICT (zone_id) DO UPDATE SET
                      name = EXCLUDED.name,
                      zone_type = EXCLUDED.zone_type,
                      geom = EXCLUDED.geom,
                      props = EXCLUDED.props,
                      city_id = COALESCE(EXCLUDED.city_id, zones.city_id)
                    RETURNING zone_id
                    """,
                    (
                        zone_id,
                        name,
                        zone_type,
                        geom_json,
                        Jsonb(props or {}),
                        cid,
                    ),
                )
                row = cur.fetchone()
            self._commit(conn)
            return str(row["zone_id"])

    def list_zones(
        self, zone_type: Optional[str] = None, city_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        clauses = ["1=1"]
        args: List[Any] = []
        if zone_type:
            clauses.append("zone_type = %s")
            args.append(zone_type)
        if city_id:
            clauses.append("city_id = %s")
            args.append(city_id)
        sql = f"""
            SELECT zone_id, name, zone_type, city_id, props, created_at,
                   ST_AsGeoJSON(geom::geometry)::json AS geometry
            FROM zones
            WHERE {' AND '.join(clauses)}
            ORDER BY zone_id
        """
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, args)
                rows = cur.fetchall()
        return [_serialize_row(r) for r in rows]

    def zones_geojson(
        self, zone_type: Optional[str] = None, city_id: Optional[str] = None
    ) -> Dict[str, Any]:
        features = []
        for z in self.list_zones(zone_type=zone_type, city_id=city_id):
            features.append(
                {
                    "type": "Feature",
                    "properties": {
                        "zone_id": z.get("zone_id"),
                        "name": z.get("name"),
                        "type": z.get("zone_type"),
                        "city_id": z.get("city_id"),
                        **(z.get("props") or {}),
                    },
                    "geometry": z.get("geometry"),
                }
            )
        return {"type": "FeatureCollection", "features": features}

    def events_in_zone(self, zone_id: str, limit: int = 200) -> List[Dict[str, Any]]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT e.event_id, e.type, e.lat, e.lon, e.status, e.confidence, e.zone_id
                    FROM events e
                    JOIN zones z ON z.zone_id = %s
                    WHERE e.geom IS NOT NULL
                      AND ST_Within(e.geom::geometry, z.geom::geometry)
                    ORDER BY e.updated_at DESC
                    LIMIT %s
                    """,
                    (zone_id, limit),
                )
                rows = cur.fetchall()
        return [_serialize_row(r) for r in rows]

    def add_review(
        self,
        event_id: str,
        label: str,
        note: str = "",
        reviewer: str = "operator",
        source: str = "api",
        unit: str = "ops",
    ) -> Dict[str, Any]:
        """Record review feedback and update event status (+ optional work order)."""
        status_map = {
            "correct": "confirmed",
            "wrong": "false_positive",
            "work_order": "work_order_created",
            "resolved": "resolved",
            "confirmed": "confirmed",
            "false_positive": "false_positive",
            "under_review": "under_review",
        }
        if label not in status_map and label not in status_map.values():
            raise ValueError(f"unsupported review label: {label}")
        new_status = status_map.get(label, label)

        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT event_id FROM events WHERE event_id = %s", (event_id,))
                if not cur.fetchone():
                    raise KeyError(event_id)
                cur.execute(
                    """
                    INSERT INTO review_feedback (event_id, label, note, reviewer, source)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id, created_at
                    """,
                    (event_id, label, note, reviewer, source),
                )
                fb = cur.fetchone()
                work_order_id = None
                if label == "work_order" or new_status == "work_order_created":
                    cur.execute(
                        """
                        INSERT INTO work_orders (event_id, unit, note)
                        VALUES (%s, %s, %s)
                        RETURNING id
                        """,
                        (event_id, unit, note),
                    )
                    work_order_id = int(cur.fetchone()["id"])
                cur.execute(
                    "UPDATE events SET status = %s WHERE event_id = %s",
                    (new_status, event_id),
                )
            self._commit(conn)
        out = {
            "feedback_id": int(fb["id"]),
            "event_id": event_id,
            "label": label,
            "status": new_status,
            "work_order_id": work_order_id,
            "created_at": fb["created_at"].isoformat()
            if hasattr(fb["created_at"], "isoformat")
            else fb["created_at"],
        }
        self.add_audit(
            actor=reviewer,
            action="review",
            entity_type="event",
            entity_id=event_id,
            detail={"label": label, "status": new_status, "work_order_id": work_order_id, "source": source},
        )
        return out

    def list_reviews(self, event_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        clauses = ["1=1"]
        args: List[Any] = []
        if event_id:
            clauses.append("event_id = %s")
            args.append(event_id)
        args.append(limit)
        sql = f"""
            SELECT id, event_id, label, note, reviewer, source, created_at
            FROM review_feedback
            WHERE {' AND '.join(clauses)}
            ORDER BY created_at DESC
            LIMIT %s
        """
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, args)
                rows = cur.fetchall()
        return [_serialize_row(r) for r in rows]

    def upsert_vehicle(
        self,
        vehicle_id: str,
        name: str | None = None,
        plate: str | None = None,
        route_id: str | None = None,
        city_id: Optional[str] = None,
    ) -> str:
        from cityvision.settings import get_settings

        cid = city_id or get_settings().default_city
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO vehicles (id, name, plate, route_id, city_id)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                      name = COALESCE(EXCLUDED.name, vehicles.name),
                      plate = COALESCE(EXCLUDED.plate, vehicles.plate),
                      route_id = COALESCE(EXCLUDED.route_id, vehicles.route_id),
                      city_id = COALESCE(EXCLUDED.city_id, vehicles.city_id)
                    RETURNING id
                    """,
                    (vehicle_id, name or vehicle_id, plate, route_id, cid),
                )
                row = cur.fetchone()
            self._commit(conn)
            return str(row["id"])

    def upsert_camera(
        self,
        camera_id: str,
        vehicle_id: str | None = None,
        label: str | None = None,
        facing: str | None = None,
    ) -> str:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO cameras (id, vehicle_id, label, facing)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                      vehicle_id = COALESCE(EXCLUDED.vehicle_id, cameras.vehicle_id),
                      label = COALESCE(EXCLUDED.label, cameras.label),
                      facing = COALESCE(EXCLUDED.facing, cameras.facing)
                    RETURNING id
                    """,
                    (camera_id, vehicle_id, label or camera_id, facing),
                )
                row = cur.fetchone()
            self._commit(conn)
            return str(row["id"])

    def upsert_route(
        self,
        route_id: str,
        name: str,
        city: str = "erzurum",
        linestring_lonlat: Optional[List[List[float]]] = None,
        props: Optional[Dict[str, Any]] = None,
    ) -> str:
        ewkt = None
        if linestring_lonlat and len(linestring_lonlat) >= 2:
            pts = ", ".join(f"{p[0]} {p[1]}" for p in linestring_lonlat)
            ewkt = f"SRID=4326;LINESTRING({pts})"
        with self.connect() as conn:
            with conn.cursor() as cur:
                if ewkt:
                    cur.execute(
                        """
                        INSERT INTO routes (id, name, city, city_id, geom, props)
                        VALUES (%s, %s, %s, %s, ST_GeogFromText(%s), %s)
                        ON CONFLICT (id) DO UPDATE SET
                          name = EXCLUDED.name,
                          city = EXCLUDED.city,
                          city_id = COALESCE(EXCLUDED.city_id, routes.city_id),
                          geom = COALESCE(EXCLUDED.geom, routes.geom),
                          props = EXCLUDED.props
                        RETURNING id
                        """,
                        (route_id, name, city, city, ewkt, Jsonb(props or {})),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO routes (id, name, city, city_id, geom, props)
                        VALUES (%s, %s, %s, %s, NULL, %s)
                        ON CONFLICT (id) DO UPDATE SET
                          name = EXCLUDED.name,
                          city = EXCLUDED.city,
                          city_id = COALESCE(EXCLUDED.city_id, routes.city_id),
                          props = EXCLUDED.props
                        RETURNING id
                        """,
                        (route_id, name, city, city, Jsonb(props or {})),
                    )
                row = cur.fetchone()
            self._commit(conn)
            return str(row["id"])

    def list_vehicles(self) -> List[Dict[str, Any]]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, name, plate, route_id, city_id, active, props, created_at
                    FROM vehicles ORDER BY id
                    """
                )
                return [_serialize_row(r) for r in cur.fetchall()]

    def list_cameras(self, vehicle_id: Optional[str] = None) -> List[Dict[str, Any]]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                if vehicle_id:
                    cur.execute(
                        """
                        SELECT id, vehicle_id, label, facing, active, props, created_at
                        FROM cameras WHERE vehicle_id = %s ORDER BY id
                        """,
                        (vehicle_id,),
                    )
                else:
                    cur.execute(
                        """
                        SELECT id, vehicle_id, label, facing, active, props, created_at
                        FROM cameras ORDER BY id
                        """
                    )
                return [_serialize_row(r) for r in cur.fetchall()]

    def list_routes(self) -> List[Dict[str, Any]]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, name, city, city_id, props, created_at,
                           ST_AsGeoJSON(geom::geometry)::json AS geometry
                    FROM routes ORDER BY id
                    """
                )
                return [_serialize_row(r) for r in cur.fetchall()]

    def list_work_orders(self, status: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        clauses = ["1=1"]
        args: List[Any] = []
        if status:
            clauses.append("status = %s")
            args.append(status)
        args.append(limit)
        sql = f"""
            SELECT id, event_id, unit, note, status, assignee, created_at, updated_at
            FROM work_orders
            WHERE {' AND '.join(clauses)}
            ORDER BY created_at DESC
            LIMIT %s
        """
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, args)
                return [_serialize_row(r) for r in cur.fetchall()]

    def replace_observations(self, event_id: str, run_id: int, rows: List[Dict[str, Any]]) -> int:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM observations WHERE event_id = %s AND run_id = %s",
                    (event_id, run_id),
                )
                n = 0
                for row in rows:
                    cur.execute(
                        """
                        INSERT INTO observations (
                          event_id, run_id, vehicle_id, camera_id, track_id,
                          lat, lon, confidence, frame_idx, seen_ms, payload
                        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        """,
                        (
                            event_id,
                            run_id,
                            row.get("vehicle_id"),
                            row.get("camera_id"),
                            row.get("track_id"),
                            row.get("lat"),
                            row.get("lon"),
                            row.get("confidence"),
                            row.get("frame_idx"),
                            row.get("seen_ms"),
                            Jsonb(row.get("payload") or {}),
                        ),
                    )
                    n += 1
            self._commit(conn)
            return n

    def upsert_detection_stat(
        self,
        run_id: int,
        class_name: str,
        count: int,
        avg_confidence: Optional[float] = None,
        model_role: str = "A",
    ) -> None:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO detections (run_id, class_name, model_role, count, avg_confidence)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (run_id, class_name, model_role) DO UPDATE SET
                      count = EXCLUDED.count,
                      avg_confidence = EXCLUDED.avg_confidence
                    """,
                    (run_id, class_name, model_role, count, avg_confidence),
                )
            self._commit(conn)

    def list_detection_stats(self, run_id: int) -> List[Dict[str, Any]]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT run_id, class_name, model_role, count, avg_confidence
                    FROM detections WHERE run_id = %s ORDER BY count DESC
                    """,
                    (run_id,),
                )
                return [_serialize_row(r) for r in cur.fetchall()]

    def upsert_event_media(
        self,
        event_id: str,
        media_type: str,
        path: str,
        content_type: Optional[str] = None,
        nbytes: Optional[int] = None,
        object_key: Optional[str] = None,
    ) -> None:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO event_media (event_id, media_type, path, content_type, bytes, object_key)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (event_id, path) DO UPDATE SET
                      media_type = EXCLUDED.media_type,
                      content_type = EXCLUDED.content_type,
                      bytes = EXCLUDED.bytes,
                      object_key = COALESCE(EXCLUDED.object_key, event_media.object_key)
                    """,
                    (event_id, media_type, path, content_type, nbytes, object_key),
                )
            self._commit(conn)

    def list_event_media(self, event_id: str) -> List[Dict[str, Any]]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, event_id, media_type, path, content_type, bytes, object_key, created_at
                    FROM event_media WHERE event_id = %s ORDER BY id
                    """,
                    (event_id,),
                )
                return [_serialize_row(r) for r in cur.fetchall()]

    def get_event_media(self, media_id: int) -> Optional[Dict[str, Any]]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, event_id, media_type, path, content_type, bytes, object_key, created_at
                    FROM event_media WHERE id = %s
                    """,
                    (media_id,),
                )
                row = cur.fetchone()
        return _serialize_row(row) if row else None

    def create_job(self, job_type: str, payload: Dict[str, Any]) -> int:
        from cityvision.settings import get_settings

        city_id = payload.get("city_id") or get_settings().default_city
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO jobs (job_type, payload, city_id)
                    VALUES (%s, %s, %s)
                    RETURNING id
                    """,
                    (job_type, Jsonb(payload), city_id),
                )
                row = cur.fetchone()
            self._commit(conn)
            return int(row["id"])

    def find_active_job(
        self,
        job_type: str,
        *,
        run_dir: Optional[str] = None,
        path: Optional[str] = None,
        upload_id: Optional[str] = None,
        object_key: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Return queued/running job with same payload key, if any."""
        if upload_id is not None:
            key, value = "upload_id", upload_id
        elif object_key is not None:
            key, value = "object_key", object_key
        elif run_dir is not None:
            key, value = "run_dir", run_dir
        elif path is not None:
            key, value = "path", path
        else:
            return None
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, job_type, status, payload, result, error,
                           created_at, started_at, finished_at
                    FROM jobs
                    WHERE job_type = %s
                      AND status IN ('queued', 'running')
                      AND payload->>%s = %s
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (job_type, key, value),
                )
                row = cur.fetchone()
        return _serialize_row(row) if row else None

    def get_job(self, job_id: int) -> Optional[Dict[str, Any]]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, job_type, status, payload, result, error,
                           created_at, started_at, finished_at
                    FROM jobs WHERE id = %s
                    """,
                    (job_id,),
                )
                row = cur.fetchone()
        return _serialize_row(row) if row else None

    def list_jobs(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, job_type, status, payload, result, error,
                           created_at, started_at, finished_at
                    FROM jobs ORDER BY id DESC LIMIT %s
                    """,
                    (limit,),
                )
                return [_serialize_row(r) for r in cur.fetchall()]

    def claim_job(self, job_id: int) -> bool:
        """Atomically move queued → running. Returns False if already claimed."""
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE jobs
                    SET status = 'running', started_at = NOW(), error = NULL
                    WHERE id = %s AND status = 'queued'
                    RETURNING id
                    """,
                    (job_id,),
                )
                row = cur.fetchone()
            self._commit(conn)
        return row is not None

    def mark_job_running(self, job_id: int) -> bool:
        """Backward-compatible alias for claim_job."""
        return self.claim_job(job_id)

    def reclaim_stale_jobs(self, older_than_minutes: int = 30) -> List[int]:
        """Reset stuck running jobs back to queued. Returns reclaimed job ids."""
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE jobs
                    SET status = 'queued', started_at = NULL, error = 'reclaimed: stale running'
                    WHERE status = 'running'
                      AND started_at IS NOT NULL
                      AND started_at < NOW() - (%s || ' minutes')::interval
                    RETURNING id
                    """,
                    (str(int(older_than_minutes)),),
                )
                rows = cur.fetchall()
            self._commit(conn)
        return [int(r["id"]) for r in rows]

    def mark_job_done(
        self,
        job_id: int,
        *,
        ok: bool,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE jobs SET
                      status = %s,
                      result = %s,
                      error = %s,
                      finished_at = NOW()
                    WHERE id = %s
                    """,
                    (
                        "succeeded" if ok else "failed",
                        Jsonb(result) if result is not None else None,
                        error,
                        job_id,
                    ),
                )
            self._commit(conn)

    def upsert_user(
        self,
        username: str,
        display_name: str = "",
        role: str = "operator",
        password_hash: Optional[str] = None,
    ) -> int:
        with self.connect() as conn:
            with conn.cursor() as cur:
                if password_hash is not None:
                    cur.execute(
                        """
                        INSERT INTO users (username, display_name, role, password_hash)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (username) DO UPDATE SET
                          display_name = EXCLUDED.display_name,
                          role = EXCLUDED.role,
                          password_hash = EXCLUDED.password_hash
                        RETURNING id
                        """,
                        (username, display_name or username, role, password_hash),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO users (username, display_name, role)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (username) DO UPDATE SET
                          display_name = EXCLUDED.display_name,
                          role = EXCLUDED.role
                        RETURNING id
                        """,
                        (username, display_name or username, role),
                    )
                row = cur.fetchone()
            self._commit(conn)
            return int(row["id"])

    def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, username, display_name, role, active, password_hash, created_at
                    FROM users WHERE username = %s
                    """,
                    (username,),
                )
                row = cur.fetchone()
        return _serialize_row(row) if row else None

    def add_audit(
        self,
        actor: str,
        action: str,
        entity_type: str,
        entity_id: Optional[str] = None,
        detail: Optional[Dict[str, Any]] = None,
    ) -> int:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO audit_log (actor, action, entity_type, entity_id, detail)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (actor, action, entity_type, entity_id, Jsonb(detail or {})),
                )
                row = cur.fetchone()
            self._commit(conn)
            return int(row["id"])

    def list_audit(self, limit: int = 100, entity_type: Optional[str] = None) -> List[Dict[str, Any]]:
        clauses = ["1=1"]
        args: List[Any] = []
        if entity_type:
            clauses.append("entity_type = %s")
            args.append(entity_type)
        args.append(limit)
        sql = f"""
            SELECT id, actor, action, entity_type, entity_id, detail, created_at
            FROM audit_log
            WHERE {' AND '.join(clauses)}
            ORDER BY id DESC
            LIMIT %s
        """
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, args)
                return [_serialize_row(r) for r in cur.fetchall()]

    def list_users(self) -> List[Dict[str, Any]]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, username, display_name, role, active, created_at FROM users ORDER BY id"
                )
                return [_serialize_row(r) for r in cur.fetchall()]

    def upsert_asset(
        self,
        asset_id: str,
        asset_type: str,
        name: str = "",
        lat: float | None = None,
        lon: float | None = None,
        zone_id: str | None = None,
        props: Optional[Dict[str, Any]] = None,
        city_id: Optional[str] = None,
    ) -> str:
        from cityvision.settings import get_settings

        cid = city_id or get_settings().default_city
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO assets (id, asset_type, name, lat, lon, zone_id, props, city_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                      asset_type = EXCLUDED.asset_type,
                      name = EXCLUDED.name,
                      lat = EXCLUDED.lat,
                      lon = EXCLUDED.lon,
                      zone_id = EXCLUDED.zone_id,
                      props = EXCLUDED.props,
                      city_id = COALESCE(EXCLUDED.city_id, assets.city_id)
                    RETURNING id
                    """,
                    (asset_id, asset_type, name, lat, lon, zone_id, Jsonb(props or {}), cid),
                )
                row = cur.fetchone()
            self._commit(conn)
            return str(row["id"])

    def list_assets(self, asset_type: Optional[str] = None) -> List[Dict[str, Any]]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                if asset_type:
                    cur.execute(
                        """
                        SELECT id, asset_type, name, lat, lon, zone_id, props, created_at
                        FROM assets WHERE asset_type = %s ORDER BY id
                        """,
                        (asset_type,),
                    )
                else:
                    cur.execute(
                        """
                        SELECT id, asset_type, name, lat, lon, zone_id, props, created_at
                        FROM assets ORDER BY id
                        """
                    )
                return [_serialize_row(r) for r in cur.fetchall()]

    def list_observations(self, event_id: str) -> List[Dict[str, Any]]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, event_id, run_id, vehicle_id, camera_id, track_id,
                           lat, lon, confidence, frame_idx, seen_ms, payload, created_at
                    FROM observations WHERE event_id = %s ORDER BY id
                    """,
                    (event_id,),
                )
                return [_serialize_row(r) for r in cur.fetchall()]

    # --- Edge devices / uploads ---

    def upsert_edge_device(
        self,
        device_id: str,
        name: str,
        token_hash: str,
        *,
        city_id: Optional[str] = None,
        vehicle_id: Optional[str] = None,
        active: bool = True,
        props: Optional[Dict[str, Any]] = None,
    ) -> str:
        from cityvision.settings import get_settings

        cid = city_id or get_settings().default_city
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO edge_devices (
                      id, name, city_id, vehicle_id, token_hash, active, props
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                      name = EXCLUDED.name,
                      city_id = COALESCE(EXCLUDED.city_id, edge_devices.city_id),
                      vehicle_id = COALESCE(EXCLUDED.vehicle_id, edge_devices.vehicle_id),
                      token_hash = EXCLUDED.token_hash,
                      active = EXCLUDED.active,
                      props = EXCLUDED.props
                    RETURNING id
                    """,
                    (
                        device_id,
                        name,
                        cid,
                        vehicle_id,
                        token_hash,
                        active,
                        Jsonb(props or {}),
                    ),
                )
                row = cur.fetchone()
            self._commit(conn)
            return str(row["id"])

    def get_edge_device(self, device_id: str) -> Optional[Dict[str, Any]]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, name, city_id, vehicle_id, token_hash, active,
                           last_seen_at, props, created_at
                    FROM edge_devices WHERE id = %s
                    """,
                    (device_id,),
                )
                row = cur.fetchone()
        return _serialize_row(row) if row else None

    def get_edge_device_by_token_hash(self, token_hash: str) -> Optional[Dict[str, Any]]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, name, city_id, vehicle_id, token_hash, active,
                           last_seen_at, props, created_at
                    FROM edge_devices
                    WHERE token_hash = %s AND active = TRUE
                    LIMIT 1
                    """,
                    (token_hash,),
                )
                row = cur.fetchone()
        return _serialize_row(row) if row else None

    def touch_edge_device(
        self,
        device_id: str,
        *,
        props: Optional[Dict[str, Any]] = None,
    ) -> None:
        with self.connect() as conn:
            with conn.cursor() as cur:
                if props is not None:
                    cur.execute(
                        """
                        UPDATE edge_devices
                        SET last_seen_at = NOW(),
                            props = COALESCE(props, '{}'::jsonb) || %s::jsonb
                        WHERE id = %s
                        """,
                        (Jsonb(props), device_id),
                    )
                else:
                    cur.execute(
                        "UPDATE edge_devices SET last_seen_at = NOW() WHERE id = %s",
                        (device_id,),
                    )
            self._commit(conn)

    def list_edge_devices(self, city_id: Optional[str] = None) -> List[Dict[str, Any]]:
        clauses = ["1=1"]
        args: List[Any] = []
        if city_id:
            clauses.append("city_id = %s")
            args.append(city_id)
        sql = f"""
            SELECT id, name, city_id, vehicle_id, active, last_seen_at, props, created_at
            FROM edge_devices
            WHERE {' AND '.join(clauses)}
            ORDER BY id
        """
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, args)
                return [_serialize_row(r) for r in cur.fetchall()]

    def create_edge_upload(
        self,
        upload_id: str,
        device_id: str,
        run_dir: str,
        *,
        city_id: Optional[str] = None,
        vehicle_id: Optional[str] = None,
        nbytes: Optional[int] = None,
        checksum: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO edge_uploads (
                      upload_id, device_id, city_id, vehicle_id, run_dir,
                      status, bytes, checksum, payload
                    ) VALUES (%s, %s, %s, %s, %s, 'received', %s, %s, %s)
                    RETURNING id, upload_id, device_id, city_id, vehicle_id, run_dir,
                              status, bytes, checksum, job_id, error, payload,
                              created_at, updated_at
                    """,
                    (
                        upload_id,
                        device_id,
                        city_id,
                        vehicle_id,
                        run_dir,
                        nbytes,
                        checksum,
                        Jsonb(payload or {}),
                    ),
                )
                row = cur.fetchone()
            self._commit(conn)
        return _serialize_row(row)

    def update_edge_upload(
        self,
        upload_id: str,
        *,
        status: Optional[str] = None,
        job_id: Optional[int] = None,
        error: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        sets = ["updated_at = NOW()"]
        args: List[Any] = []
        if status is not None:
            sets.append("status = %s")
            args.append(status)
        if job_id is not None:
            sets.append("job_id = %s")
            args.append(job_id)
        if error is not None:
            sets.append("error = %s")
            args.append(error)
        args.append(upload_id)
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE edge_uploads SET {', '.join(sets)}
                    WHERE upload_id = %s
                    RETURNING id, upload_id, device_id, city_id, vehicle_id, run_dir,
                              status, bytes, checksum, job_id, error, payload,
                              created_at, updated_at
                    """,
                    args,
                )
                row = cur.fetchone()
            self._commit(conn)
        return _serialize_row(row) if row else None

    def get_edge_upload(self, upload_id: str) -> Optional[Dict[str, Any]]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, upload_id, device_id, city_id, vehicle_id, run_dir,
                           status, bytes, checksum, job_id, error, payload,
                           created_at, updated_at
                    FROM edge_uploads WHERE upload_id = %s
                    """,
                    (upload_id,),
                )
                row = cur.fetchone()
        return _serialize_row(row) if row else None

    # --- Memphis video uploads ---

    def find_video_by_checksum(
        self, device_id: str, checksum: str
    ) -> Optional[Dict[str, Any]]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, upload_id, device_id, city_id, vehicle_id, route_id,
                           object_key, gps_object_key, bytes, checksum, status,
                           job_id, run_dir, error, payload, created_at, updated_at
                    FROM edge_video_uploads
                    WHERE device_id = %s AND checksum = %s
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (device_id, checksum),
                )
                row = cur.fetchone()
        return _serialize_row(row) if row else None

    def create_edge_video_upload(
        self,
        upload_id: str,
        device_id: str,
        object_key: str,
        checksum: str,
        *,
        city_id: Optional[str] = None,
        vehicle_id: Optional[str] = None,
        route_id: Optional[str] = None,
        gps_object_key: Optional[str] = None,
        nbytes: Optional[int] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO edge_video_uploads (
                      upload_id, device_id, city_id, vehicle_id, route_id,
                      object_key, gps_object_key, bytes, checksum, status, payload
                    ) VALUES (
                      %s, %s, %s, %s, %s, %s, %s, %s, %s, 'received', %s
                    )
                    RETURNING id, upload_id, device_id, city_id, vehicle_id, route_id,
                              object_key, gps_object_key, bytes, checksum, status,
                              job_id, run_dir, error, payload, created_at, updated_at
                    """,
                    (
                        upload_id,
                        device_id,
                        city_id,
                        vehicle_id,
                        route_id,
                        object_key,
                        gps_object_key,
                        nbytes,
                        checksum,
                        Jsonb(payload or {}),
                    ),
                )
                row = cur.fetchone()
            self._commit(conn)
        return _serialize_row(row)

    def update_edge_video_upload(
        self,
        upload_id: str,
        *,
        status: Optional[str] = None,
        job_id: Optional[int] = None,
        run_dir: Optional[str] = None,
        error: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        sets = ["updated_at = NOW()"]
        args: List[Any] = []
        if status is not None:
            sets.append("status = %s")
            args.append(status)
        if job_id is not None:
            sets.append("job_id = %s")
            args.append(job_id)
        if run_dir is not None:
            sets.append("run_dir = %s")
            args.append(run_dir)
        if error is not None:
            sets.append("error = %s")
            args.append(error)
        args.append(upload_id)
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE edge_video_uploads SET {', '.join(sets)}
                    WHERE upload_id = %s
                    RETURNING id, upload_id, device_id, city_id, vehicle_id, route_id,
                              object_key, gps_object_key, bytes, checksum, status,
                              job_id, run_dir, error, payload, created_at, updated_at
                    """,
                    args,
                )
                row = cur.fetchone()
            self._commit(conn)
        return _serialize_row(row) if row else None

    def get_edge_video_upload(self, upload_id: str) -> Optional[Dict[str, Any]]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, upload_id, device_id, city_id, vehicle_id, route_id,
                           object_key, gps_object_key, bytes, checksum, status,
                           job_id, run_dir, error, payload, created_at, updated_at
                    FROM edge_video_uploads WHERE upload_id = %s
                    """,
                    (upload_id,),
                )
                row = cur.fetchone()
        return _serialize_row(row) if row else None


def _notify_webhook(payload: Dict[str, Any]) -> None:
    from cityvision.settings import get_settings

    url = get_settings().webhook_url
    if not url:
        return
    try:
        import json
        import urllib.request

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=2)
    except Exception:
        pass


def _serialize_row(row: Dict[str, Any] | None) -> Dict[str, Any]:
    if row is None:
        return {}
    out: Dict[str, Any] = {}
    for k, v in row.items():
        if hasattr(v, "isoformat"):
            out[k] = v.isoformat()
        elif isinstance(v, (dict, list)):
            out[k] = v
        else:
            out[k] = v
    # convenience: flatten payload extras for dashboard
    if isinstance(out.get("payload"), dict):
        out.setdefault("payload_json", json.dumps(out["payload"], ensure_ascii=False))
    return out
