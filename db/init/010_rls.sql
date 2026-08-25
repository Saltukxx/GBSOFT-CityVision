-- Row-level security: a connection may only see rows for app.current_city_id,
-- or all rows when that GUC is '*'. Store.connect() always SET LOCAL this GUC.
-- FORCE is required because the app role owns the tables and would otherwise
-- bypass RLS.

-- Direct city_id columns
DO $$
DECLARE
  t TEXT;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'events', 'zones', 'runs', 'assets', 'vehicles', 'jobs', 'routes',
    'users', 'edge_devices', 'edge_uploads', 'edge_video_uploads'
  ]
  LOOP
    EXECUTE format('DROP POLICY IF EXISTS city_isolation ON %I', t);
    EXECUTE format(
      'CREATE POLICY city_isolation ON %I
         USING (
           current_setting(''app.current_city_id'', true) = ''*''
           OR city_id = current_setting(''app.current_city_id'', true)
         )
         WITH CHECK (
           current_setting(''app.current_city_id'', true) = ''*''
           OR city_id = current_setting(''app.current_city_id'', true)
         )',
      t
    );
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
  END LOOP;
END
$$;

-- Child tables: isolate via the parent row's city_id
DROP POLICY IF EXISTS city_isolation ON observations;
CREATE POLICY city_isolation ON observations
  USING (
    current_setting('app.current_city_id', true) = '*'
    OR EXISTS (
      SELECT 1 FROM events e
      WHERE e.event_id = observations.event_id
        AND e.city_id = current_setting('app.current_city_id', true)
    )
  )
  WITH CHECK (
    current_setting('app.current_city_id', true) = '*'
    OR EXISTS (
      SELECT 1 FROM events e
      WHERE e.event_id = observations.event_id
        AND e.city_id = current_setting('app.current_city_id', true)
    )
  );
ALTER TABLE observations ENABLE ROW LEVEL SECURITY;
ALTER TABLE observations FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS city_isolation ON event_media;
CREATE POLICY city_isolation ON event_media
  USING (
    current_setting('app.current_city_id', true) = '*'
    OR EXISTS (
      SELECT 1 FROM events e
      WHERE e.event_id = event_media.event_id
        AND e.city_id = current_setting('app.current_city_id', true)
    )
  )
  WITH CHECK (
    current_setting('app.current_city_id', true) = '*'
    OR EXISTS (
      SELECT 1 FROM events e
      WHERE e.event_id = event_media.event_id
        AND e.city_id = current_setting('app.current_city_id', true)
    )
  );
ALTER TABLE event_media ENABLE ROW LEVEL SECURITY;
ALTER TABLE event_media FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS city_isolation ON review_feedback;
CREATE POLICY city_isolation ON review_feedback
  USING (
    current_setting('app.current_city_id', true) = '*'
    OR EXISTS (
      SELECT 1 FROM events e
      WHERE e.event_id = review_feedback.event_id
        AND e.city_id = current_setting('app.current_city_id', true)
    )
  )
  WITH CHECK (
    current_setting('app.current_city_id', true) = '*'
    OR EXISTS (
      SELECT 1 FROM events e
      WHERE e.event_id = review_feedback.event_id
        AND e.city_id = current_setting('app.current_city_id', true)
    )
  );
ALTER TABLE review_feedback ENABLE ROW LEVEL SECURITY;
ALTER TABLE review_feedback FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS city_isolation ON work_orders;
CREATE POLICY city_isolation ON work_orders
  USING (
    current_setting('app.current_city_id', true) = '*'
    OR EXISTS (
      SELECT 1 FROM events e
      WHERE e.event_id = work_orders.event_id
        AND e.city_id = current_setting('app.current_city_id', true)
    )
  )
  WITH CHECK (
    current_setting('app.current_city_id', true) = '*'
    OR EXISTS (
      SELECT 1 FROM events e
      WHERE e.event_id = work_orders.event_id
        AND e.city_id = current_setting('app.current_city_id', true)
    )
  );
ALTER TABLE work_orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE work_orders FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS city_isolation ON detections;
CREATE POLICY city_isolation ON detections
  USING (
    current_setting('app.current_city_id', true) = '*'
    OR EXISTS (
      SELECT 1 FROM runs r
      WHERE r.id = detections.run_id
        AND r.city_id = current_setting('app.current_city_id', true)
    )
  )
  WITH CHECK (
    current_setting('app.current_city_id', true) = '*'
    OR EXISTS (
      SELECT 1 FROM runs r
      WHERE r.id = detections.run_id
        AND r.city_id = current_setting('app.current_city_id', true)
    )
  );
ALTER TABLE detections ENABLE ROW LEVEL SECURITY;
ALTER TABLE detections FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS city_isolation ON cameras;
CREATE POLICY city_isolation ON cameras
  USING (
    current_setting('app.current_city_id', true) = '*'
    OR EXISTS (
      SELECT 1 FROM vehicles v
      WHERE v.id = cameras.vehicle_id
        AND v.city_id = current_setting('app.current_city_id', true)
    )
  )
  WITH CHECK (
    current_setting('app.current_city_id', true) = '*'
    OR EXISTS (
      SELECT 1 FROM vehicles v
      WHERE v.id = cameras.vehicle_id
        AND v.city_id = current_setting('app.current_city_id', true)
    )
  );
ALTER TABLE cameras ENABLE ROW LEVEL SECURITY;
ALTER TABLE cameras FORCE ROW LEVEL SECURITY;
