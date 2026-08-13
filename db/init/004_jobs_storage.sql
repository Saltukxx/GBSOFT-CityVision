-- Jobs queue + media object keys
ALTER TABLE event_media ADD COLUMN IF NOT EXISTS object_key TEXT;

CREATE TABLE IF NOT EXISTS jobs (
  id BIGSERIAL PRIMARY KEY,
  job_type TEXT NOT NULL, -- ingest_run | ingest_zones
  status TEXT NOT NULL DEFAULT 'queued', -- queued | running | succeeded | failed
  payload JSONB NOT NULL DEFAULT '{}'::jsonb,
  result JSONB,
  error TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at DESC);

ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS assignee TEXT;
