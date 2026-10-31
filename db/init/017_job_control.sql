-- Job control for the worker queue.
-- heartbeat_at: a running job proves it is alive; only silent jobs are reclaimed
--               (started_at made long video analyses look stuck and run twice).
-- cancel_requested: a user asked to stop; the worker checks it while running.
-- attempts: reclaimed jobs are retried a bounded number of times.
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS heartbeat_at TIMESTAMPTZ;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS cancel_requested BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS attempts INTEGER NOT NULL DEFAULT 0;
CREATE INDEX IF NOT EXISTS idx_jobs_running_heartbeat ON jobs(heartbeat_at) WHERE status = 'running';
