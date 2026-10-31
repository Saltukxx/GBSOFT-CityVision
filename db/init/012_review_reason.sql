-- Why a reviewer rejected a candidate (manhole, shadow, ...). Feeds hard-negative
-- mining for retraining. NULL for confirmations and older reviews.
ALTER TABLE review_feedback ADD COLUMN IF NOT EXISTS reason TEXT;
CREATE INDEX IF NOT EXISTS idx_review_feedback_reason ON review_feedback(reason);
