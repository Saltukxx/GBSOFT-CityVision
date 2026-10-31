-- Route planning in the web app: who made a route and when it last changed.
-- Flight parameters (altitude, speed, gimbal, notes) live in routes.props.
ALTER TABLE routes ADD COLUMN IF NOT EXISTS created_by TEXT;
ALTER TABLE routes ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
CREATE INDEX IF NOT EXISTS idx_edge_video_route ON edge_video_uploads(route_id);
