-- Work-order planning fields for the web app board.
ALTER TABLE work_orders ADD COLUMN IF NOT EXISTS due_date DATE;
CREATE INDEX IF NOT EXISTS idx_work_orders_status ON work_orders(status);

-- Audit log browsing: newest-first paging and filters.
CREATE INDEX IF NOT EXISTS idx_audit_city_id_desc ON audit_log(city_id, id DESC);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action);
CREATE INDEX IF NOT EXISTS idx_review_feedback_created ON review_feedback(created_at);
