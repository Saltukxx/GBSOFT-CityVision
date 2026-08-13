-- Backend domain tables (plan §21)

CREATE TABLE IF NOT EXISTS users (
  id BIGSERIAL PRIMARY KEY,
  username TEXT UNIQUE NOT NULL,
  display_name TEXT,
  role TEXT NOT NULL DEFAULT 'operator', -- operator | admin | viewer
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS routes (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  city TEXT DEFAULT 'erzurum',
  geom GEOGRAPHY(LINESTRING, 4326),
  props JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_routes_geom ON routes USING GIST (geom);

-- Extend fleet links
ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS plate TEXT;
ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS route_id TEXT REFERENCES routes(id);
ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS active BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS props JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE cameras ADD COLUMN IF NOT EXISTS facing TEXT;
ALTER TABLE cameras ADD COLUMN IF NOT EXISTS active BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE cameras ADD COLUMN IF NOT EXISTS props JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE runs ADD COLUMN IF NOT EXISTS route_id TEXT REFERENCES routes(id);
ALTER TABLE runs ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'ingested';

CREATE TABLE IF NOT EXISTS assets (
  id TEXT PRIMARY KEY,
  asset_type TEXT NOT NULL, -- bin | bus_stop | road_segment | other
  name TEXT,
  lat DOUBLE PRECISION,
  lon DOUBLE PRECISION,
  geom GEOGRAPHY(POINT, 4326),
  zone_id TEXT REFERENCES zones(zone_id),
  props JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_assets_geom ON assets USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_assets_type ON assets(asset_type);

CREATE TABLE IF NOT EXISTS observations (
  id BIGSERIAL PRIMARY KEY,
  event_id TEXT NOT NULL REFERENCES events(event_id) ON DELETE CASCADE,
  run_id BIGINT REFERENCES runs(id) ON DELETE SET NULL,
  vehicle_id TEXT,
  camera_id TEXT,
  track_id INTEGER,
  lat DOUBLE PRECISION,
  lon DOUBLE PRECISION,
  confidence DOUBLE PRECISION,
  frame_idx INTEGER,
  seen_ms DOUBLE PRECISION,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_observations_event ON observations(event_id);
CREATE INDEX IF NOT EXISTS idx_observations_run ON observations(run_id);

-- Aggregated detection stats per run (full frame dumps stay on disk as JSONL)
CREATE TABLE IF NOT EXISTS detections (
  id BIGSERIAL PRIMARY KEY,
  run_id BIGINT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  class_name TEXT NOT NULL,
  model_role TEXT, -- A | B
  count INTEGER NOT NULL DEFAULT 0,
  avg_confidence DOUBLE PRECISION,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE (run_id, class_name, model_role)
);

CREATE INDEX IF NOT EXISTS idx_detections_run ON detections(run_id);

CREATE TABLE IF NOT EXISTS event_media (
  id BIGSERIAL PRIMARY KEY,
  event_id TEXT NOT NULL REFERENCES events(event_id) ON DELETE CASCADE,
  media_type TEXT NOT NULL, -- image | crop | clip | json | other
  path TEXT NOT NULL,
  content_type TEXT,
  bytes BIGINT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (event_id, path)
);

CREATE INDEX IF NOT EXISTS idx_event_media_event ON event_media(event_id);

-- Helpful event columns for fleet attribution
ALTER TABLE events ADD COLUMN IF NOT EXISTS vehicle_id TEXT;
ALTER TABLE events ADD COLUMN IF NOT EXISTS camera_id TEXT;
ALTER TABLE events ADD COLUMN IF NOT EXISTS route_id TEXT;

CREATE OR REPLACE FUNCTION cityvision_set_asset_geom()
RETURNS TRIGGER AS $$
BEGIN
  IF NEW.lat IS NOT NULL AND NEW.lon IS NOT NULL THEN
    NEW.geom := ST_SetSRID(ST_MakePoint(NEW.lon, NEW.lat), 4326)::geography;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_assets_geom ON assets;
CREATE TRIGGER trg_assets_geom
BEFORE INSERT OR UPDATE ON assets
FOR EACH ROW EXECUTE FUNCTION cityvision_set_asset_geom();
