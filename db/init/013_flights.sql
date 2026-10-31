-- Flights in the web app are rows of edge_video_uploads (drone device, FlightHub
-- or browser upload). Browser uploads start in status 'uploading' with a
-- placeholder checksum until all chunks arrive.
-- Statuses: uploading | received | queued | analyzing | succeeded | failed | cancelled | duplicate

-- Fraction done (0..1) for long jobs such as video analysis; NULL when unknown.
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS progress REAL;

CREATE INDEX IF NOT EXISTS idx_edge_video_city_created
  ON edge_video_uploads(city_id, created_at DESC);
