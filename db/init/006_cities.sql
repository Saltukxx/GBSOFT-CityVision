-- Multi-city scope + indexes for tenant filtering
CREATE TABLE IF NOT EXISTS cities (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  timezone TEXT DEFAULT 'Europe/Istanbul',
  props JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO cities (id, name)
VALUES ('erzurum', 'Erzurum')
ON CONFLICT (id) DO NOTHING;

ALTER TABLE events ADD COLUMN IF NOT EXISTS city_id TEXT REFERENCES cities(id);
ALTER TABLE zones ADD COLUMN IF NOT EXISTS city_id TEXT REFERENCES cities(id);
ALTER TABLE runs ADD COLUMN IF NOT EXISTS city_id TEXT REFERENCES cities(id);
ALTER TABLE assets ADD COLUMN IF NOT EXISTS city_id TEXT REFERENCES cities(id);
ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS city_id TEXT REFERENCES cities(id);
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS city_id TEXT REFERENCES cities(id);
ALTER TABLE routes ADD COLUMN IF NOT EXISTS city_id TEXT REFERENCES cities(id);

-- Backfill from routes.city / default
UPDATE events SET city_id = 'erzurum' WHERE city_id IS NULL;
UPDATE zones SET city_id = 'erzurum' WHERE city_id IS NULL;
UPDATE runs SET city_id = 'erzurum' WHERE city_id IS NULL;
UPDATE assets SET city_id = 'erzurum' WHERE city_id IS NULL;
UPDATE vehicles SET city_id = 'erzurum' WHERE city_id IS NULL;
UPDATE jobs SET city_id = 'erzurum' WHERE city_id IS NULL;
UPDATE routes SET city_id = COALESCE(city_id, city, 'erzurum') WHERE city_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_events_city ON events(city_id);
CREATE INDEX IF NOT EXISTS idx_zones_city ON zones(city_id);
CREATE INDEX IF NOT EXISTS idx_runs_city ON runs(city_id);
CREATE INDEX IF NOT EXISTS idx_assets_city ON assets(city_id);
CREATE INDEX IF NOT EXISTS idx_vehicles_city ON vehicles(city_id);
CREATE INDEX IF NOT EXISTS idx_jobs_city ON jobs(city_id);
CREATE INDEX IF NOT EXISTS idx_routes_city ON routes(city_id);
