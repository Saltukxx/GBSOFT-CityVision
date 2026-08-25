-- Users belong to exactly one city. NULL city_id is reserved for superadmin
-- (cross-city staff); the application layer enforces that pairing.
ALTER TABLE users ADD COLUMN IF NOT EXISTS city_id TEXT REFERENCES cities(id);

UPDATE users
SET city_id = 'erzurum'
WHERE city_id IS NULL AND role IS DISTINCT FROM 'superadmin';

CREATE INDEX IF NOT EXISTS idx_users_city ON users(city_id);

-- edge_devices / edge_uploads already have city_id (007_edge.sql / 008).
