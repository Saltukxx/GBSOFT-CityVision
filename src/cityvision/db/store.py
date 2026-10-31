from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any, Dict, Generator, List, Optional

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from cityvision.settings import get_settings
from cityvision.tenant import TENANT_ALL, get_tenant_city


class UsernameConflict(Exception):
    """Raised when INSERT would collide with a username in another tenant."""

    def __init__(self, username: str):
        self.username = username
        super().__init__(username)


def database_url() -> str:
    return get_settings().database_url


class Store:
    """PostgreSQL + PostGIS event store."""

    def __init__(self, dsn: str | None = None):
        self.dsn = dsn or database_url()
        self._tx_conn: Optional[psycopg.Connection] = None

    def _apply_tenant(self, conn: psycopg.Connection) -> None:
        """SET LOCAL app.current_city_id for RLS. Unset context → '*' (system path)."""
        city = get_tenant_city()
        if city is None:
            city = TENANT_ALL
        with conn.cursor() as cur:
            cur.execute("SELECT set_config('app.current_city_id', %s, true)", (city,))

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
            self._apply_tenant(conn)
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
            self._apply_tenant(conn)
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

    def get_city(self, city_id: str) -> Optional[Dict[str, Any]]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, name, timezone, props, created_at FROM cities WHERE id = %s",
                    (city_id,),
                )
                row = cur.fetchone()
        return _serialize_row(row) if row else None

    def update_city(
        self,
        city_id: str,
        *,
        name: Optional[str] = None,
        timezone: Optional[str] = None,
        props_merge: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        sets: List[str] = []
        args: List[Any] = []
        if name is not None:
            sets.append("name = %s")
            args.append(name)
        if timezone is not None:
            sets.append("timezone = %s")
            args.append(timezone)
        if props_merge:
            sets.append("props = props || %s")
            args.append(Jsonb(props_merge))
        if not sets:
            return self.get_city(city_id)
        args.append(city_id)
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE cities SET {', '.join(sets)} WHERE id = %s
                    RETURNING id, name, timezone, props, created_at
                    """,
                    args,
                )
                row = cur.fetchone()
            self._commit(conn)
        return _serialize_row(row) if row else None

    def review_stats(self, city_id: Optional[str] = None, days: int = 7) -> Dict[str, Any]:
        """Review activity over the last `days`: decisions, reject reasons, speed."""
        city_clause = " AND e.city_id = %s" if city_id else ""
        base: List[Any] = [days] + ([city_id] if city_id else [])
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT r.label, COUNT(*) AS c
                    FROM review_feedback r JOIN events e ON e.event_id = r.event_id
                    WHERE r.created_at >= NOW() - make_interval(days => %s){city_clause}
                    GROUP BY r.label
                    """,
                    base,
                )
                by_label = {row["label"]: row["c"] for row in cur.fetchall()}
                cur.execute(
                    f"""
                    SELECT COALESCE(r.reason, 'unspecified') AS reason, COUNT(*) AS c
                    FROM review_feedback r JOIN events e ON e.event_id = r.event_id
                    WHERE r.created_at >= NOW() - make_interval(days => %s)
                      AND r.label IN ('wrong', 'false_positive'){city_clause}
                    GROUP BY 1 ORDER BY 2 DESC
                    """,
                    base,
                )
                reasons = {row["reason"]: row["c"] for row in cur.fetchall()}
                cur.execute(
                    f"""
                    SELECT r.reviewer, COUNT(*) AS c
                    FROM review_feedback r JOIN events e ON e.event_id = r.event_id
                    WHERE r.created_at >= NOW() - make_interval(days => %s){city_clause}
                    GROUP BY r.reviewer ORDER BY 2 DESC LIMIT 10
                    """,
                    base,
                )
                by_reviewer = {row["reviewer"]: row["c"] for row in cur.fetchall()}
                # Hours from an event appearing to its first decision.
                cur.execute(
                    f"""
                    SELECT percentile_cont(0.5) WITHIN GROUP (
                             ORDER BY EXTRACT(EPOCH FROM first_review - e.created_at) / 3600.0
                           ) AS median_hours
                    FROM (
                      SELECT event_id, MIN(created_at) AS first_review
                      FROM review_feedback GROUP BY event_id
                    ) f
                    JOIN events e ON e.event_id = f.event_id
                    WHERE f.first_review >= NOW() - make_interval(days => %s){city_clause}
                    """,
                    base,
                )
                median = cur.fetchone()["median_hours"]
                cur.execute(
                    f"""
                    SELECT COUNT(*) AS c FROM edge_video_uploads e
                    WHERE e.created_at >= NOW() - make_interval(days => %s)
                      AND e.status NOT IN ('cancelled', 'duplicate'){city_clause}
                    """,
                    base,
                )
                flights = cur.fetchone()["c"]
        confirmed = sum(by_label.get(k, 0) for k in ("correct", "confirmed", "work_order"))
        rejected = sum(by_label.get(k, 0) for k in ("wrong", "false_positive"))
        decided = confirmed + rejected
        return {
            "days": days,
            "decisions": sum(by_label.values()),
            "confirmed": confirmed,
            "false_alarms": rejected,
            "unsure": by_label.get("unsure", 0),
            "precision": round(confirmed / decided, 3) if decided else None,
            "false_alarm_reasons": reasons,
            "by_reviewer": by_reviewer,
            "median_hours_to_decision": round(float(median), 2) if median is not None else None,
            "flights": flights,
        }

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
        *,
        unit: Optional[str] = None,
        due_date: Optional[Any] = None,
        clear_due_date: bool = False,
        actor: Optional[str] = None,
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
        if unit is not None:
            sets.append("unit = %s")
            args.append(unit)
        if clear_due_date:
            sets.append("due_date = NULL")
        elif due_date is not None:
            sets.append("due_date = %s")
            args.append(due_date)
        args.append(work_order_id)
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE work_orders SET {', '.join(sets)}
                    WHERE id = %s
                    RETURNING id, event_id, unit, note, status, assignee, due_date,
                              created_at, updated_at
                    """,
                    args,
                )
                row = cur.fetchone()
                if row and status is not None:
                    # The event mirrors its work order: done → resolved,
                    # cancelled → back to confirmed, reopened → work order again.
                    event_status = {
                        "resolved": "resolved",
                        "cancelled": "confirmed",
                    }.get(status, "work_order_created")
                    cur.execute(
                        "UPDATE events SET status = %s WHERE event_id = %s",
                        (event_status, row["event_id"]),
                    )
            self._commit(conn)
        if row:
            changes = {
                k: v
                for k, v in {
                    "status": status,
                    "note": note,
                    "assignee": assignee,
                    "unit": unit,
                    "due_date": str(due_date) if due_date is not None else None,
                }.items()
                if v is not None
            }
            if clear_due_date:
                changes["due_date"] = None
            self.add_audit(
                actor=actor or "system",
                action="work_order_update",
                entity_type="work_order",
                entity_id=str(work_order_id),
                detail={"event_id": row["event_id"], **changes},
            )
        return _serialize_row(row) if row else None

        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, event_id, unit, note, status, assignee, due_date,
                           created_at, updated_at
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
                    SELECT wo.id, wo.event_id, wo.unit, wo.note, wo.status, wo.assignee,
                           wo.created_at, wo.updated_at, e.city_id
                    FROM work_orders wo
                    JOIN events e ON e.event_id = wo.event_id
                    WHERE wo.id = %s
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
                    f"""
                    SELECT COUNT(*) AS c FROM work_orders wo
                    JOIN events e ON e.event_id = wo.event_id
                    WHERE wo.status NOT IN ('resolved', 'cancelled')
                    {city_clause.replace('city_id', 'e.city_id') if city_clause else ''}
                    """,
                    city_args,
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

    def list_runs(self, limit: int = 50, city_id: Optional[str] = None) -> List[Dict[str, Any]]:
        clauses = ["1=1"]
        args: List[Any] = []
        if city_id:
            clauses.append("city_id = %s")
            args.append(city_id)
        args.append(limit)
        sql = f"""
            SELECT id, run_dir, source, vehicle_id, camera_id, model_a, model_b,
                   city_id, created_at
            FROM runs
            WHERE {' AND '.join(clauses)}
            ORDER BY id DESC LIMIT %s
        """
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, args)
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
        self,
        lat: float,
        lon: float,
        radius_m: float = 50.0,
        limit: int = 50,
        city_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """PostGIS spatial lookup around a point."""
        city_clause = " AND city_id = %s" if city_id else ""
        args: List[Any] = [lon, lat, lon, lat, radius_m]
        if city_id:
            args.append(city_id)
        args.append(limit)
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT event_id, type, lat, lon, status, confidence, city_id,
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
                      {city_clause}
                    ORDER BY distance_m
                    LIMIT %s
                    """,
                    args,
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

    def events_in_zone(
        self, zone_id: str, limit: int = 200, city_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        city_clause = " AND e.city_id = %s AND z.city_id = %s" if city_id else ""
        args: List[Any] = [zone_id]
        if city_id:
            args.extend([city_id, city_id])
        args.append(limit)
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT e.event_id, e.type, e.lat, e.lon, e.status, e.confidence, e.zone_id, e.city_id
                    FROM events e
                    JOIN zones z ON z.zone_id = %s
                    WHERE e.geom IS NOT NULL
                      AND ST_Within(e.geom::geometry, z.geom::geometry)
                      {city_clause}
                    ORDER BY e.updated_at DESC
                    LIMIT %s
                    """,
                    args,
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
        reason: Optional[str] = None,
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
            "unsure": "under_review",
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
                    INSERT INTO review_feedback (event_id, label, note, reviewer, source, reason)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id, created_at
                    """,
                    (event_id, label, note, reviewer, source, reason),
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
            "reason": reason,
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
            detail={
                "label": label,
                "reason": reason,
                "status": new_status,
                "work_order_id": work_order_id,
                "source": source,
            },
        )
        return out

    def list_reviews(
        self,
        event_id: Optional[str] = None,
        limit: int = 100,
        city_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        clauses = ["1=1"]
        args: List[Any] = []
        if event_id:
            clauses.append("r.event_id = %s")
            args.append(event_id)
        if city_id:
            clauses.append("e.city_id = %s")
            args.append(city_id)
        args.append(limit)
        sql = f"""
            SELECT r.id, r.event_id, r.label, r.reason, r.note, r.reviewer, r.source,
                   r.created_at, e.city_id
            FROM review_feedback r
            JOIN events e ON e.event_id = r.event_id
            WHERE {' AND '.join(clauses)}
            ORDER BY r.created_at DESC
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

    def list_vehicles(self, city_id: Optional[str] = None) -> List[Dict[str, Any]]:
        clauses = ["1=1"]
        args: List[Any] = []
        if city_id:
            clauses.append("city_id = %s")
            args.append(city_id)
        sql = f"""
            SELECT id, name, plate, route_id, city_id, active, props, created_at
            FROM vehicles
            WHERE {' AND '.join(clauses)}
            ORDER BY id
        """
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, args)
                return [_serialize_row(r) for r in cur.fetchall()]

    def list_cameras(
        self, vehicle_id: Optional[str] = None, city_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        clauses = ["1=1"]
        args: List[Any] = []
        if vehicle_id:
            clauses.append("c.vehicle_id = %s")
            args.append(vehicle_id)
        if city_id:
            clauses.append("v.city_id = %s")
            args.append(city_id)
        sql = f"""
            SELECT c.id, c.vehicle_id, c.label, c.facing, c.active, c.props, c.created_at,
                   v.city_id
            FROM cameras c
            LEFT JOIN vehicles v ON v.id = c.vehicle_id
            WHERE {' AND '.join(clauses)}
            ORDER BY c.id
        """
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, args)
                return [_serialize_row(r) for r in cur.fetchall()]

    def list_routes(self, city_id: Optional[str] = None) -> List[Dict[str, Any]]:
        clauses = ["1=1"]
        args: List[Any] = []
        if city_id:
            clauses.append("(city_id = %s OR city = %s)")
            args.extend([city_id, city_id])
        clauses = [c.replace("city_id", "r.city_id").replace("city =", "r.city =") for c in clauses]
        sql = f"""{self._ROUTE_SELECT}
            WHERE {' AND '.join(clauses)}
            ORDER BY r.name
        """
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, args)
                return [_serialize_row(r) for r in cur.fetchall()]

    # ---------- Route planning & flight paths ----------

    _ROUTE_SELECT = """
        SELECT r.id, r.name, r.city, r.city_id, r.props, r.created_at, r.updated_at, r.created_by,
               ST_AsGeoJSON(r.geom::geometry)::json AS geometry,
               ST_Length(r.geom) AS length_m,
               (SELECT COUNT(*) FROM edge_video_uploads u
                 WHERE u.route_id = r.id AND u.status NOT IN ('cancelled', 'duplicate')) AS flights,
               (SELECT MAX(u.created_at) FROM edge_video_uploads u
                 WHERE u.route_id = r.id AND u.status NOT IN ('cancelled', 'duplicate')) AS last_flown
        FROM routes r
    """

    def get_route(self, route_id: str) -> Optional[Dict[str, Any]]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(f"{self._ROUTE_SELECT} WHERE r.id = %s", (route_id,))
                row = cur.fetchone()
        return _serialize_row(row) if row else None

    def save_planned_route(
        self,
        route_id: str,
        *,
        name: str,
        city_id: str,
        coordinates: List[List[float]],
        props: Dict[str, Any],
        actor: str,
    ) -> Dict[str, Any]:
        pts = ", ".join(f"{float(p[0])} {float(p[1])}" for p in coordinates)
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO routes (id, name, city, city_id, geom, props, created_by, updated_at)
                    VALUES (%s, %s, %s, %s, ST_GeogFromText(%s), %s, %s, NOW())
                    ON CONFLICT (id) DO UPDATE SET
                      name = EXCLUDED.name,
                      geom = EXCLUDED.geom,
                      props = EXCLUDED.props,
                      updated_at = NOW()
                    """,
                    (route_id, name, city_id, city_id, f"SRID=4326;LINESTRING({pts})", Jsonb(props), actor),
                )
            self._commit(conn)
        return self.get_route(route_id) or {}

    def delete_route(self, route_id: str) -> bool:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM routes WHERE id = %s", (route_id,))
                ok = cur.rowcount > 0
            self._commit(conn)
        return ok

    def flight_tracks(
        self,
        city_id: Optional[str] = None,
        days: int = 30,
        route_id: Optional[str] = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """Flights that have a GPS track, newest first."""
        clauses = [
            "u.created_at >= NOW() - make_interval(days => %s)",
            "u.status NOT IN ('cancelled', 'duplicate')",
            "jsonb_array_length(COALESCE(r.summary->'track', '[]'::jsonb)) > 1",
        ]
        args: List[Any] = [days]
        if city_id:
            clauses.append("u.city_id = %s")
            args.append(city_id)
        if route_id:
            clauses.append("u.route_id = %s")
            args.append(route_id)
        args.append(limit)
        sql = f"""
            SELECT u.upload_id AS id,
                   COALESCE(u.payload->>'name', u.payload->>'task_name', u.payload->>'run_name') AS name,
                   u.payload->>'flight_date' AS flight_date,
                   u.created_at, u.route_id, u.status, u.holdout,
                   r.summary->'track' AS track,
                   (SELECT COUNT(DISTINCT o.event_id) FROM observations o WHERE o.run_id = r.id) AS candidates
            FROM edge_video_uploads u
            JOIN runs r ON r.run_dir = u.run_dir
            WHERE {' AND '.join(clauses)}
            ORDER BY u.created_at DESC
            LIMIT %s
        """
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, args)
                return [_serialize_row(r) for r in cur.fetchall()]

    def route_adherence(
        self, route_id: str, track_lonlat: List[List[float]], tolerance_m: float = 30.0
    ) -> Optional[Dict[str, Any]]:
        """How closely a flown track followed a planned route.

        coverage: share of the route's length that the track passed within `tolerance_m` of.
        off_route: share of track points farther than `tolerance_m` from the route.
        """
        if len(track_lonlat) < 2:
            return None
        line = "SRID=4326;LINESTRING(" + ", ".join(f"{float(p[0])} {float(p[1])}" for p in track_lonlat) + ")"
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    WITH rt AS (SELECT geom FROM routes WHERE id = %(rid)s AND geom IS NOT NULL),
                         tr AS (SELECT ST_GeogFromText(%(line)s) AS g),
                         pts AS (
                           SELECT (ST_DumpPoints(tr.g::geometry)).geom::geography AS p FROM tr
                         )
                    SELECT
                      ST_Length(rt.geom) AS route_m,
                      -- geography overload: the geometry cast lost the overlap entirely
                      ST_Length(ST_Intersection(rt.geom, ST_Buffer(tr.g, %(tol)s))) AS covered_m,
                      (SELECT AVG(CASE WHEN ST_Distance(pts.p, rt.geom) > %(tol)s THEN 1.0 ELSE 0.0 END) FROM pts)
                        AS off_route,
                      (SELECT MAX(ST_Distance(pts.p, rt.geom)) FROM pts) AS max_deviation_m
                    FROM rt, tr
                    """,
                    {"rid": route_id, "line": line, "tol": tolerance_m},
                )
                row = cur.fetchone()
        if not row or not row["route_m"]:
            return None
        return {
            "tolerance_m": tolerance_m,
            "route_m": round(float(row["route_m"]), 1),
            "coverage": round(min(1.0, float(row["covered_m"] or 0) / float(row["route_m"])), 3),
            "off_route": round(float(row["off_route"] or 0), 3),
            "max_deviation_m": round(float(row["max_deviation_m"] or 0), 1),
        }

    def list_work_orders(
        self,
        status: Optional[str] = None,
        limit: int = 100,
        city_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        clauses = ["1=1"]
        args: List[Any] = []
        if status:
            clauses.append("wo.status = %s")
            args.append(status)
        if city_id:
            clauses.append("e.city_id = %s")
            args.append(city_id)
        args.append(limit)
        sql = f"""
            SELECT wo.id, wo.event_id, wo.unit, wo.note, wo.status, wo.assignee,
                   wo.due_date, wo.created_at, wo.updated_at, e.city_id,
                   e.type AS event_type, e.lat, e.lon, e.confidence, e.confidence_band
            FROM work_orders wo
            JOIN events e ON e.event_id = wo.event_id
            WHERE {' AND '.join(clauses)}
            ORDER BY wo.created_at DESC
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
                    SELECT m.id, m.event_id, m.media_type, m.path, m.content_type,
                           m.bytes, m.object_key, m.created_at, e.city_id
                    FROM event_media m
                    JOIN events e ON e.event_id = m.event_id
                    WHERE m.event_id = %s ORDER BY m.id
                    """,
                    (event_id,),
                )
                return [_serialize_row(r) for r in cur.fetchall()]

    def first_images_for_events(self, event_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """One thumbnail per event (crop preferred over full frame), in one query."""
        if not event_ids:
            return {}
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT DISTINCT ON (m.event_id)
                           m.id, m.event_id, m.media_type, m.path, m.content_type,
                           m.bytes, m.object_key, m.created_at, e.city_id
                    FROM event_media m
                    JOIN events e ON e.event_id = m.event_id
                    WHERE m.event_id = ANY(%s) AND m.media_type IN ('crop', 'image')
                    ORDER BY m.event_id, (m.media_type = 'crop') DESC, m.id
                    """,
                    (list(event_ids),),
                )
                return {r["event_id"]: _serialize_row(r) for r in cur.fetchall()}

    def get_event_media(self, media_id: int) -> Optional[Dict[str, Any]]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT m.id, m.event_id, m.media_type, m.path, m.content_type,
                           m.bytes, m.object_key, m.created_at, e.city_id
                    FROM event_media m
                    JOIN events e ON e.event_id = m.event_id
                    WHERE m.id = %s
                    """,
                    (media_id,),
                )
                row = cur.fetchone()
        return _serialize_row(row) if row else None

    def lookup_storage_key(self, key: str) -> Optional[Dict[str, Any]]:
        """Map an object-store key to a city-scoped row, if any."""
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT m.id, m.event_id, m.object_key, e.city_id
                    FROM event_media m
                    JOIN events e ON e.event_id = m.event_id
                    WHERE m.object_key = %s
                    LIMIT 1
                    """,
                    (key,),
                )
                row = cur.fetchone()
                if row:
                    return _serialize_row(row)
                cur.execute(
                    """
                    SELECT upload_id, object_key, gps_object_key, city_id
                    FROM edge_video_uploads
                    WHERE object_key = %s OR gps_object_key = %s
                    LIMIT 1
                    """,
                    (key, key),
                )
                row = cur.fetchone()
        return _serialize_row(row) if row else None

    def create_job(self, job_type: str, payload: Dict[str, Any]) -> int:
        from cityvision.settings import get_settings

        payload = dict(payload)
        city_id = payload.get("city_id")
        tenant = get_tenant_city()
        if not city_id:
            if tenant and tenant != TENANT_ALL:
                city_id = tenant
            else:
                city_id = get_settings().default_city
        elif tenant and tenant != TENANT_ALL and str(city_id) != str(tenant):
            raise ValueError("job city_id does not match current tenant")
        payload["city_id"] = city_id
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
                    SELECT id, job_type, status, payload, result, error, city_id,
                           progress, created_at, started_at, finished_at
                    FROM jobs WHERE id = %s
                    """,
                    (job_id,),
                )
                row = cur.fetchone()
        return _serialize_row(row) if row else None

    def list_jobs(self, limit: int = 50, city_id: Optional[str] = None) -> List[Dict[str, Any]]:
        clauses = ["1=1"]
        args: List[Any] = []
        if city_id:
            clauses.append("city_id = %s")
            args.append(city_id)
        args.append(limit)
        sql = f"""
            SELECT id, job_type, status, payload, result, error, city_id,
                   created_at, started_at, finished_at
            FROM jobs
            WHERE {' AND '.join(clauses)}
            ORDER BY id DESC LIMIT %s
        """
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, args)
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
        city_id: Optional[str] = None,
    ) -> int:
        from psycopg.errors import IntegrityError, UniqueViolation

        from cityvision.settings import get_settings

        cid = city_id
        if role != "superadmin" and not cid:
            cid = get_settings().default_city
        if role == "superadmin":
            cid = None
        tenant = get_tenant_city()
        if tenant and tenant != TENANT_ALL and cid and str(cid) != str(tenant):
            raise ValueError("user city_id does not match current tenant")
        with self.connect() as conn:
            try:
                with conn.cursor() as cur:
                    if password_hash is not None:
                        cur.execute(
                            """
                            INSERT INTO users (username, display_name, role, password_hash, city_id)
                            VALUES (%s, %s, %s, %s, %s)
                            ON CONFLICT (username) DO UPDATE SET
                              display_name = EXCLUDED.display_name,
                              role = EXCLUDED.role,
                              password_hash = EXCLUDED.password_hash,
                              city_id = CASE
                                WHEN current_setting('app.current_city_id', true) = '*'
                                THEN EXCLUDED.city_id
                                ELSE users.city_id
                              END
                            RETURNING id
                            """,
                            (username, display_name or username, role, password_hash, cid),
                        )
                    else:
                        cur.execute(
                            """
                            INSERT INTO users (username, display_name, role, city_id)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (username) DO UPDATE SET
                              display_name = EXCLUDED.display_name,
                              role = EXCLUDED.role,
                              city_id = CASE
                                WHEN current_setting('app.current_city_id', true) = '*'
                                THEN EXCLUDED.city_id
                                ELSE users.city_id
                              END
                            RETURNING id
                            """,
                            (username, display_name or username, role, cid),
                        )
                    row = cur.fetchone()
                self._commit(conn)
            except UniqueViolation as exc:
                raise UsernameConflict(username) from exc
            except IntegrityError as exc:
                if getattr(exc, "sqlstate", None) == "23505":
                    raise UsernameConflict(username) from exc
                raise
            return int(row["id"])

    def set_user_active(self, username: str, active: bool) -> bool:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET active = %s WHERE username = %s", (active, username)
                )
                ok = cur.rowcount > 0
            self._commit(conn)
        return ok

    def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, username, display_name, role, active, password_hash,
                           city_id, created_at
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
        city_id: Optional[str] = None,
    ) -> int:
        cid = city_id
        if cid is None:
            tenant = get_tenant_city()
            if tenant and tenant != TENANT_ALL:
                cid = tenant
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO audit_log (actor, action, entity_type, entity_id, detail, city_id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (actor, action, entity_type, entity_id, Jsonb(detail or {}), cid),
                )
                row = cur.fetchone()
            self._commit(conn)
            return int(row["id"])

    def list_audit(
        self,
        limit: int = 100,
        entity_type: Optional[str] = None,
        city_id: Optional[str] = None,
        *,
        actor: Optional[str] = None,
        action: Optional[str] = None,
        entity_id: Optional[str] = None,
        before_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        clauses = ["1=1"]
        args: List[Any] = []
        if entity_type:
            clauses.append("entity_type = %s")
            args.append(entity_type)
        if actor:
            clauses.append("actor = %s")
            args.append(actor)
        if action:
            clauses.append("action = %s")
            args.append(action)
        if entity_id:
            clauses.append("entity_id = %s")
            args.append(entity_id)
        if before_id:
            clauses.append("id < %s")
            args.append(before_id)
        if city_id:
            clauses.append("city_id = %s")
            args.append(city_id)
        args.append(limit)
        sql = f"""
            SELECT id, actor, action, entity_type, entity_id, detail, city_id, created_at
            FROM audit_log
            WHERE {' AND '.join(clauses)}
            ORDER BY id DESC
            LIMIT %s
        """
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, args)
                return [_serialize_row(r) for r in cur.fetchall()]

    def list_users(self, city_id: Optional[str] = None) -> List[Dict[str, Any]]:
        clauses = ["1=1"]
        args: List[Any] = []
        if city_id:
            clauses.append("city_id = %s")
            args.append(city_id)
        sql = f"""
            SELECT id, username, display_name, role, active, city_id, created_at
            FROM users
            WHERE {' AND '.join(clauses)}
            ORDER BY id
        """
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, args)
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

    def list_assets(
        self, asset_type: Optional[str] = None, city_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        clauses = ["1=1"]
        args: List[Any] = []
        if asset_type:
            clauses.append("asset_type = %s")
            args.append(asset_type)
        if city_id:
            clauses.append("city_id = %s")
            args.append(city_id)
        sql = f"""
            SELECT id, asset_type, name, lat, lon, zone_id, props, city_id, created_at
            FROM assets
            WHERE {' AND '.join(clauses)}
            ORDER BY id
        """
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, args)
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
        status: str = "received",
    ) -> Dict[str, Any]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO edge_video_uploads (
                      upload_id, device_id, city_id, vehicle_id, route_id,
                      object_key, gps_object_key, bytes, checksum, status, payload
                    ) VALUES (
                      %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
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
                        status,
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
        checksum: Optional[str] = None,
        nbytes: Optional[int] = None,
        gps_object_key: Optional[str] = None,
        payload_merge: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        sets = ["updated_at = NOW()"]
        args: List[Any] = []
        if checksum is not None:
            sets.append("checksum = %s")
            args.append(checksum)
        if nbytes is not None:
            sets.append("bytes = %s")
            args.append(nbytes)
        if gps_object_key is not None:
            sets.append("gps_object_key = %s")
            args.append(gps_object_key)
        if payload_merge:
            sets.append("payload = payload || %s")
            args.append(Jsonb(payload_merge))
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

    # ---------- Phase 4: labelling, model performance, weekly report ----------

    _LABEL_ITEM_SQL = """
        WITH last_review AS (
          SELECT DISTINCT ON (r.event_id) r.event_id, r.label, r.reason, r.reviewer,
                 r.created_at
          FROM review_feedback r
          ORDER BY r.event_id, r.created_at DESC
        ),
        first_run AS (
          SELECT DISTINCT ON (o.event_id) o.event_id, o.run_id
          FROM observations o
          ORDER BY o.event_id, o.id
        )
        SELECT e.event_id, e.type, e.confidence, e.confidence_band, e.model_version,
               e.city_id, e.created_at,
               lr.label AS review_label, lr.reason AS review_reason,
               lr.reviewer, lr.created_at AS reviewed_at,
               fr.run_id, u.upload_id AS flight_id,
               COALESCE(u.payload->>'name', u.payload->>'run_name') AS flight_name,
               COALESCE(u.holdout, FALSE) AS holdout,
               tl.kind AS label_kind, tl.boxes AS label_boxes, tl.media_id AS label_media_id,
               tl.labeller, tl.updated_at AS labelled_at,
               EXISTS (
                 SELECT 1 FROM event_media m
                 WHERE m.event_id = e.event_id AND m.media_type = 'frame'
               ) AS has_clean_frame
        FROM events e
        JOIN last_review lr ON lr.event_id = e.event_id
        LEFT JOIN first_run fr ON fr.event_id = e.event_id
        LEFT JOIN runs ru ON ru.id = fr.run_id
        LEFT JOIN edge_video_uploads u ON u.run_dir = ru.run_dir
        LEFT JOIN training_labels tl ON tl.event_id = e.event_id
    """

    def labelling_queue(
        self, city_id: Optional[str] = None, done: bool = False, limit: int = 200
    ) -> List[Dict[str, Any]]:
        """Reviewed events, unsure first, then false alarms, then confirmations."""
        clauses = ["tl.id IS NOT NULL" if done else "tl.id IS NULL", "lr.label <> 'resolved'"]
        args: List[Any] = []
        if city_id:
            clauses.append("e.city_id = %s")
            args.append(city_id)
        args.append(limit)
        order = (
            "tl.updated_at DESC"
            if done
            else """CASE lr.label WHEN 'unsure' THEN 0 WHEN 'under_review' THEN 0
                       WHEN 'wrong' THEN 1 WHEN 'false_positive' THEN 1 ELSE 2 END,
                     lr.created_at DESC"""
        )
        sql = f"""{self._LABEL_ITEM_SQL}
            WHERE {' AND '.join(clauses)}
            ORDER BY {order}
            LIMIT %s
        """
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, args)
                return [_serialize_row(r) for r in cur.fetchall()]

    def labelling_item(self, event_id: str) -> Optional[Dict[str, Any]]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(f"{self._LABEL_ITEM_SQL} WHERE e.event_id = %s", (event_id,))
                row = cur.fetchone()
        return _serialize_row(row) if row else None

    def labelling_counts(self, city_id: Optional[str] = None) -> Dict[str, Any]:
        city_clause = " AND e.city_id = %s" if city_id else ""
        args: List[Any] = [city_id] if city_id else []
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT COUNT(DISTINCT r.event_id) AS c
                    FROM review_feedback r
                    JOIN events e ON e.event_id = r.event_id
                    LEFT JOIN training_labels tl ON tl.event_id = r.event_id
                    WHERE tl.id IS NULL AND r.label <> 'resolved'{city_clause}
                    """,
                    args,
                )
                todo = cur.fetchone()["c"]
                cur.execute(
                    f"""
                    SELECT tl.kind, COUNT(*) AS c FROM training_labels tl
                    JOIN events e ON e.event_id = tl.event_id
                    WHERE 1=1{city_clause} GROUP BY tl.kind
                    """,
                    args,
                )
                by_kind = {r["kind"]: r["c"] for r in cur.fetchall()}
                cur.execute(
                    f"""
                    SELECT b->>'cls' AS cls, COUNT(*) AS c
                    FROM training_labels tl
                    JOIN events e ON e.event_id = tl.event_id,
                         jsonb_array_elements(tl.boxes) b
                    WHERE tl.kind = 'positive'{city_clause}
                    GROUP BY 1
                    """,
                    args,
                )
                boxes = {r["cls"]: r["c"] for r in cur.fetchall()}
        return {"todo": todo, "by_kind": by_kind, "boxes_by_class": boxes}

    def upsert_training_label(
        self,
        event_id: str,
        *,
        kind: str,
        boxes: List[Dict[str, Any]],
        labeller: str,
        media_id: Optional[int],
        city_id: Optional[str],
    ) -> Dict[str, Any]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO training_labels (event_id, media_id, kind, boxes, labeller, city_id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (event_id) DO UPDATE SET
                      media_id = EXCLUDED.media_id,
                      kind = EXCLUDED.kind,
                      boxes = EXCLUDED.boxes,
                      labeller = EXCLUDED.labeller,
                      updated_at = NOW()
                    RETURNING id, event_id, media_id, kind, boxes, labeller, city_id,
                              created_at, updated_at
                    """,
                    (event_id, media_id, kind, Jsonb(boxes), labeller, city_id),
                )
                row = cur.fetchone()
            self._commit(conn)
        return _serialize_row(row)

    def delete_training_label(self, event_id: str) -> bool:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM training_labels WHERE event_id = %s", (event_id,))
                ok = cur.rowcount > 0
            self._commit(conn)
        return ok

    def training_export_rows(self, city_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Labels ready for export, each with its clean frame and split group."""
        city_clause = " AND e.city_id = %s" if city_id else ""
        args: List[Any] = [city_id] if city_id else []
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    WITH first_run AS (
                      SELECT DISTINCT ON (o.event_id) o.event_id, o.run_id
                      FROM observations o ORDER BY o.event_id, o.id
                    )
                    SELECT tl.event_id, tl.kind, tl.boxes, e.type, e.city_id,
                           m.id AS media_id, m.path, m.object_key,
                           fr.run_id, u.upload_id AS flight_id,
                           COALESCE(u.holdout, FALSE) AS holdout
                    FROM training_labels tl
                    JOIN events e ON e.event_id = tl.event_id
                    LEFT JOIN event_media m ON m.id = tl.media_id AND m.media_type = 'frame'
                    LEFT JOIN first_run fr ON fr.event_id = e.event_id
                    LEFT JOIN runs ru ON ru.id = fr.run_id
                    LEFT JOIN edge_video_uploads u ON u.run_dir = ru.run_dir
                    WHERE tl.kind IN ('positive', 'negative'){city_clause}
                    ORDER BY tl.event_id
                    """,
                    args,
                )
                return [_serialize_row(r) for r in cur.fetchall()]

    def set_flight_holdout(self, upload_id: str, holdout: bool) -> bool:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE edge_video_uploads SET holdout = %s, updated_at = NOW() WHERE upload_id = %s",
                    (holdout, upload_id),
                )
                ok = cur.rowcount > 0
            self._commit(conn)
        return ok

    def model_performance(self, city_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Per model version: what it found and how reviewers judged it."""
        city_clause = " AND e.city_id = %s" if city_id else ""
        args: List[Any] = [city_id] if city_id else []
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT COALESCE(e.model_version, 'unknown') AS model_version,
                           COUNT(*) AS events,
                           COUNT(DISTINCT o.run_id) AS runs,
                           MIN(e.created_at) AS first_seen,
                           MAX(e.created_at) AS last_seen,
                           COUNT(*) FILTER (WHERE e.status IN
                             ('confirmed', 'work_order_created', 'resolved')) AS confirmed,
                           COUNT(*) FILTER (WHERE e.status = 'false_positive') AS false_alarms,
                           COUNT(*) FILTER (WHERE e.status = 'under_review') AS pending
                    FROM events e
                    LEFT JOIN LATERAL (
                      SELECT run_id FROM observations WHERE event_id = e.event_id LIMIT 1
                    ) o ON TRUE
                    WHERE 1=1{city_clause}
                    GROUP BY 1
                    ORDER BY MAX(e.created_at) DESC
                    """,
                    args,
                )
                rows = [_serialize_row(r) for r in cur.fetchall()]
                cur.execute(
                    f"""
                    SELECT COALESCE(e.model_version, 'unknown') AS model_version,
                           COALESCE(r.reason, 'unspecified') AS reason, COUNT(*) AS c
                    FROM review_feedback r JOIN events e ON e.event_id = r.event_id
                    WHERE r.label IN ('wrong', 'false_positive'){city_clause}
                    GROUP BY 1, 2
                    """,
                    args,
                )
                reasons: Dict[str, Dict[str, int]] = {}
                for r in cur.fetchall():
                    reasons.setdefault(r["model_version"], {})[r["reason"]] = r["c"]
        for row in rows:
            decided = row["confirmed"] + row["false_alarms"]
            row["precision"] = round(row["confirmed"] / decided, 3) if decided else None
            row["false_alarm_reasons"] = reasons.get(row["model_version"], {})
        return rows

    def weekly_report(self, city_id: Optional[str], start: Any, end: Any) -> Dict[str, Any]:
        """Activity between `start` (inclusive) and `end` (exclusive) dates."""
        ec = " AND e.city_id = %s" if city_id else ""
        cargs: List[Any] = [city_id] if city_id else []
        rng: List[Any] = [start, end]
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT COUNT(*) AS flights, COALESCE(SUM(bytes), 0) AS bytes,
                           COUNT(*) FILTER (WHERE e.status = 'succeeded') AS processed
                    FROM edge_video_uploads e
                    WHERE e.created_at >= %s AND e.created_at < %s
                      AND e.status NOT IN ('cancelled', 'duplicate'){ec}
                    """,
                    rng + cargs,
                )
                flights = dict(cur.fetchone())
                cur.execute(
                    f"""
                    SELECT e.type, COUNT(*) AS c FROM events e
                    WHERE e.created_at >= %s AND e.created_at < %s{ec}
                    GROUP BY e.type ORDER BY 2 DESC
                    """,
                    rng + cargs,
                )
                new_by_type = {r["type"]: r["c"] for r in cur.fetchall()}
                cur.execute(
                    f"""
                    SELECT r.label, COALESCE(r.reason, '') AS reason, COUNT(*) AS c
                    FROM review_feedback r JOIN events e ON e.event_id = r.event_id
                    WHERE r.created_at >= %s AND r.created_at < %s{ec}
                    GROUP BY 1, 2
                    """,
                    rng + cargs,
                )
                labels: Dict[str, int] = {}
                reasons: Dict[str, int] = {}
                for r in cur.fetchall():
                    labels[r["label"]] = labels.get(r["label"], 0) + r["c"]
                    if r["label"] in ("wrong", "false_positive"):
                        key = r["reason"] or "unspecified"
                        reasons[key] = reasons.get(key, 0) + r["c"]
                cur.execute(
                    f"""
                    SELECT
                      COUNT(*) FILTER (WHERE wo.created_at >= %s AND wo.created_at < %s) AS opened,
                      COUNT(*) FILTER (WHERE wo.status = 'resolved'
                                        AND wo.updated_at >= %s AND wo.updated_at < %s) AS resolved,
                      COUNT(*) FILTER (WHERE wo.status NOT IN ('resolved', 'cancelled')) AS open_now,
                      COUNT(*) FILTER (WHERE wo.status NOT IN ('resolved', 'cancelled')
                                        AND wo.due_date < CURRENT_DATE) AS overdue
                    FROM work_orders wo JOIN events e ON e.event_id = wo.event_id
                    WHERE 1=1{ec}
                    """,
                    rng + rng + cargs,
                )
                work_orders = dict(cur.fetchone())
                cur.execute(
                    f"""
                    SELECT DISTINCT ON (e.event_id) e.event_id, e.type, e.lat, e.lon, e.status,
                           e.confidence, e.confidence_band, r.created_at AS decided_at
                    FROM review_feedback r JOIN events e ON e.event_id = r.event_id
                    WHERE r.created_at >= %s AND r.created_at < %s
                      AND e.status IN ('confirmed', 'work_order_created', 'resolved'){ec}
                    ORDER BY e.event_id, r.created_at DESC
                    """,
                    rng + cargs,
                )
                confirmed_events = [_serialize_row(r) for r in cur.fetchall()]
                cur.execute(
                    f"""
                    SELECT DISTINCT COALESCE(e.model_version, 'unknown') AS m FROM events e
                    WHERE e.created_at >= %s AND e.created_at < %s{ec}
                    """,
                    rng + cargs,
                )
                models = sorted(r["m"] for r in cur.fetchall())
        confirmed = sum(labels.get(k, 0) for k in ("correct", "confirmed", "work_order"))
        rejected = sum(labels.get(k, 0) for k in ("wrong", "false_positive"))
        decided = confirmed + rejected
        return {
            "start": str(start),
            "end": str(end),
            "flights": flights,
            "new_candidates": sum(new_by_type.values()),
            "new_by_type": new_by_type,
            "decisions": sum(labels.values()),
            "confirmed": confirmed,
            "false_alarms": rejected,
            "unsure": labels.get("unsure", 0),
            "precision": round(confirmed / decided, 3) if decided else None,
            "false_alarm_reasons": reasons,
            "work_orders": work_orders,
            "confirmed_events": confirmed_events,
            "model_versions": models,
        }

    def set_job_progress(self, job_id: int, progress: float) -> None:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE jobs SET progress = %s WHERE id = %s",
                    (max(0.0, min(1.0, float(progress))), job_id),
                )
            self._commit(conn)

    def delete_edge_video_upload(self, upload_id: str) -> bool:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM edge_video_uploads WHERE upload_id = %s", (upload_id,))
                deleted = cur.rowcount > 0
            self._commit(conn)
        return deleted

    # A flight is an edge_video_uploads row plus its job, run and candidate count.
    _FLIGHT_SELECT = """
        SELECT u.upload_id, u.device_id, u.city_id, u.vehicle_id, u.route_id,
               u.object_key, u.gps_object_key, u.bytes, u.status, u.job_id, u.run_dir,
               u.error, u.payload, u.created_at, u.updated_at, u.holdout,
               d.name AS device_name,
               j.status AS job_status, j.progress AS job_progress, j.error AS job_error,
               j.started_at AS job_started_at, j.finished_at AS job_finished_at,
               r.id AS run_id,
               (SELECT COUNT(DISTINCT o.event_id) FROM observations o WHERE o.run_id = r.id)
                 AS candidates
        FROM edge_video_uploads u
        LEFT JOIN edge_devices d ON d.id = u.device_id
        LEFT JOIN jobs j ON j.id = u.job_id
        LEFT JOIN runs r ON r.run_dir = u.run_dir
    """

    def list_flights(
        self,
        city_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        clauses = ["u.status <> 'cancelled'"]
        args: List[Any] = []
        if city_id:
            clauses.append("u.city_id = %s")
            args.append(city_id)
        if status:
            clauses.append("u.status = %s")
            args.append(status)
        args.append(limit)
        sql = f"""{self._FLIGHT_SELECT}
            WHERE {' AND '.join(clauses)}
            ORDER BY u.created_at DESC
            LIMIT %s
        """
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, args)
                return [_serialize_row(r) for r in cur.fetchall()]

    def get_flight(self, upload_id: str) -> Optional[Dict[str, Any]]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(f"{self._FLIGHT_SELECT} WHERE u.upload_id = %s", (upload_id,))
                row = cur.fetchone()
        return _serialize_row(row) if row else None

    def list_run_event_ids(self, run_id: int) -> List[str]:
        """Events with at least one observation from this run."""
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT DISTINCT event_id FROM observations WHERE run_id = %s",
                    (run_id,),
                )
                return [r["event_id"] for r in cur.fetchall()]

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
