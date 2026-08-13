-- City Vision core schema (PostgreSQL + PostGIS)
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS vehicles (
  id TEXT PRIMARY KEY,
  name TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS cameras (
  id TEXT PRIMARY KEY,
  vehicle_id TEXT REFERENCES vehicles(id),
  label TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS runs (
  id BIGSERIAL PRIMARY KEY,
  run_dir TEXT UNIQUE NOT NULL,
  source TEXT,
  vehicle_id TEXT,
  camera_id TEXT,
  model_a TEXT,
  model_b JSONB,
  summary JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS events (
  id BIGSERIAL PRIMARY KEY,
  event_id TEXT UNIQUE NOT NULL,
  run_id BIGINT REFERENCES runs(id) ON DELETE SET NULL,
  type TEXT NOT NULL,
  lat DOUBLE PRECISION,
  lon DOUBLE PRECISION,
  geom GEOGRAPHY(POINT, 4326),
  severity TEXT,
  confidence DOUBLE PRECISION,
  confidence_band TEXT,
  observations INTEGER DEFAULT 1,
  status TEXT NOT NULL DEFAULT 'under_review',
  model_version TEXT,
  zone_id TEXT,
  evidence_dir TEXT,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  first_seen_ms DOUBLE PRECISION,
  last_seen_ms DOUBLE PRECISION,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_events_type ON events(type);
CREATE INDEX IF NOT EXISTS idx_events_status ON events(status);
CREATE INDEX IF NOT EXISTS idx_events_geom ON events USING GIST (geom);

CREATE TABLE IF NOT EXISTS zones (
  zone_id TEXT PRIMARY KEY,
  name TEXT,
  zone_type TEXT NOT NULL DEFAULT 'bus_stop',
  geom GEOGRAPHY(POLYGON, 4326),
  props JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_zones_geom ON zones USING GIST (geom);

CREATE TABLE IF NOT EXISTS work_orders (
  id BIGSERIAL PRIMARY KEY,
  event_id TEXT NOT NULL REFERENCES events(event_id) ON DELETE CASCADE,
  unit TEXT NOT NULL,
  note TEXT,
  status TEXT NOT NULL DEFAULT 'created',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS model_versions (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  path TEXT NOT NULL,
  role TEXT NOT NULL, -- A | B_road | B_waste
  metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE OR REPLACE FUNCTION cityvision_set_event_geom()
RETURNS TRIGGER AS $$
BEGIN
  IF NEW.lat IS NOT NULL AND NEW.lon IS NOT NULL THEN
    NEW.geom := ST_SetSRID(ST_MakePoint(NEW.lon, NEW.lat), 4326)::geography;
  END IF;
  NEW.updated_at := NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_events_geom ON events;
CREATE TRIGGER trg_events_geom
BEFORE INSERT OR UPDATE ON events
FOR EACH ROW EXECUTE FUNCTION cityvision_set_event_geom();
