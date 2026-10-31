-- Phase 4: turning reviewer decisions into training data.

-- One label per event: boxes on its evidence frame, or a hard negative
-- (nothing worth detecting — e.g. a manhole cover, shadow, paint).
CREATE TABLE IF NOT EXISTS training_labels (
  id BIGSERIAL PRIMARY KEY,
  event_id TEXT NOT NULL UNIQUE REFERENCES events(event_id) ON DELETE CASCADE,
  media_id BIGINT REFERENCES event_media(id) ON DELETE SET NULL,
  kind TEXT NOT NULL CHECK (kind IN ('positive', 'negative', 'skip')),
  -- [{"cls": "pothole", "x": 0.31, "y": 0.52, "w": 0.08, "h": 0.06}] — top-left, 0..1 of the frame
  boxes JSONB NOT NULL DEFAULT '[]'::jsonb,
  labeller TEXT NOT NULL,
  city_id TEXT REFERENCES cities(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_training_labels_city ON training_labels(city_id);

-- Flights kept out of training entirely; their events only ever go to the test split.
ALTER TABLE edge_video_uploads ADD COLUMN IF NOT EXISTS holdout BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_events_model_version ON events(model_version);
CREATE INDEX IF NOT EXISTS idx_events_created ON events(created_at);

DROP POLICY IF EXISTS city_isolation ON training_labels;
CREATE POLICY city_isolation ON training_labels
  USING (
    current_setting('app.current_city_id', true) = '*'
    OR city_id = current_setting('app.current_city_id', true)
  )
  WITH CHECK (
    current_setting('app.current_city_id', true) = '*'
    OR city_id = current_setting('app.current_city_id', true)
  );
ALTER TABLE training_labels ENABLE ROW LEVEL SECURITY;
ALTER TABLE training_labels FORCE ROW LEVEL SECURITY;

-- Data fix: ingest used to file object_crop.jpg as a full image (it only
-- recognised names *starting* with "crop"). Re-file those as crops.
UPDATE event_media SET media_type = 'crop'
WHERE media_type = 'image'
  AND (COALESCE(object_key, path) LIKE '%/object_crop.%' OR COALESCE(object_key, path) LIKE '%crop%.jpg');
