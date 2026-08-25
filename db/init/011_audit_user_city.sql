-- Audit rows scoped to a city; users.city_id pairing enforced in the database.

ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS city_id TEXT REFERENCES cities(id);
CREATE INDEX IF NOT EXISTS idx_audit_city ON audit_log(city_id);

DROP POLICY IF EXISTS city_isolation ON audit_log;
CREATE POLICY city_isolation ON audit_log
  USING (
    current_setting('app.current_city_id', true) = '*'
    OR city_id = current_setting('app.current_city_id', true)
  )
  WITH CHECK (
    current_setting('app.current_city_id', true) = '*'
    OR city_id = current_setting('app.current_city_id', true)
  );
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log FORCE ROW LEVEL SECURITY;

-- superadmin ↔ NULL city; everyone else must belong to a city.
UPDATE users
SET city_id = 'erzurum'
WHERE city_id IS NULL AND role IS DISTINCT FROM 'superadmin';

UPDATE users
SET city_id = NULL
WHERE role = 'superadmin' AND city_id IS NOT NULL;

ALTER TABLE users DROP CONSTRAINT IF EXISTS users_city_superadmin_chk;
ALTER TABLE users ADD CONSTRAINT users_city_superadmin_chk
  CHECK (
    (role = 'superadmin' AND city_id IS NULL)
    OR (role IS DISTINCT FROM 'superadmin' AND city_id IS NOT NULL)
  );
