-- Memphis: central video analysis uploads (no on-device YOLO)
CREATE TABLE IF NOT EXISTS edge_video_uploads (
  id BIGSERIAL PRIMARY KEY,
  upload_id TEXT UNIQUE NOT NULL,
  device_id TEXT NOT NULL REFERENCES edge_devices(id),
  city_id TEXT REFERENCES cities(id),
  vehicle_id TEXT,
  route_id TEXT,
  object_key TEXT NOT NULL,
  gps_object_key TEXT,
  bytes BIGINT,
  checksum TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'received',
  -- received | queued | analyzing | succeeded | failed
  job_id BIGINT REFERENCES jobs(id) ON DELETE SET NULL,
  run_dir TEXT,
  error TEXT,
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_edge_video_device_checksum
  ON edge_video_uploads(device_id, checksum);

CREATE INDEX IF NOT EXISTS idx_edge_video_device ON edge_video_uploads(device_id);
CREATE INDEX IF NOT EXISTS idx_edge_video_status ON edge_video_uploads(status);
CREATE INDEX IF NOT EXISTS idx_edge_video_created ON edge_video_uploads(created_at DESC);
