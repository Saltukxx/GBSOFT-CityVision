-- Human review feedback linked to municipal events
CREATE TABLE IF NOT EXISTS review_feedback (
  id BIGSERIAL PRIMARY KEY,
  event_id TEXT NOT NULL REFERENCES events(event_id) ON DELETE CASCADE,
  label TEXT NOT NULL,
  note TEXT,
  reviewer TEXT NOT NULL DEFAULT 'operator',
  source TEXT NOT NULL DEFAULT 'api', -- api | cli | jsonl
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_review_feedback_event ON review_feedback(event_id);
CREATE INDEX IF NOT EXISTS idx_review_feedback_label ON review_feedback(label);
