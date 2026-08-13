-- Edge devices + upload ledger
CREATE TABLE IF NOT EXISTS edge_devices (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  city_id TEXT REFERENCES cities(id),
  vehicle_id TEXT,
  token_hash TEXT NOT NULL,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  last_seen_at TIMESTAMPTZ,
  props JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_edge_devices_city ON edge_devices(city_id);
CREATE INDEX IF NOT EXISTS idx_edge_devices_token ON edge_devices(token_hash);

CREATE TABLE IF NOT EXISTS edge_uploads (
  id BIGSERIAL PRIMARY KEY,
  upload_id TEXT UNIQUE NOT NULL,
  device_id TEXT NOT NULL REFERENCES edge_devices(id),
  city_id TEXT REFERENCES cities(id),
  vehicle_id TEXT,
  run_dir TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'received', -- received | queued | ingesting | succeeded | failed
  bytes BIGINT,
  checksum TEXT,
  job_id BIGINT REFERENCES jobs(id) ON DELETE SET NULL,
  error TEXT,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_edge_uploads_device ON edge_uploads(device_id);
CREATE INDEX IF NOT EXISTS idx_edge_uploads_status ON edge_uploads(status);
CREATE INDEX IF NOT EXISTS idx_edge_uploads_created ON edge_uploads(created_at DESC);
