# Multi-tenancy plan: converting the backend to serve multiple municipalities

## Current state (verified against the code, 2026-08-21)

The backend is a FastAPI app (`src/cityvision/api/app.py`, routers under
`src/cityvision/api/routers/`) backed by Postgres/PostGIS, with raw SQL access via
`src/cityvision/db/store.py` (no ORM, no Alembic — migrations are hand-written SQL in
`db/init/*.sql`).

It is **single-tenant today**, with a partial, unenforced city-scoping layer:

- `db/init/006_cities.sql` added a `cities` table and a `city_id` column to `events`,
  `zones`, `runs`, `assets`, `vehicles`, `jobs`, `routes` — the migration's own comment
  says "Multi-city scope + indexes for **tenant filtering**", so the intent was there.
- But `users` (`db/init/003_backend.sql`) has **no `city_id` column** — users are
  global, not scoped to a city.
- JWTs (`src/cityvision/api/security.py:35-49`) carry only `sub` (username) and `role`
  — no city/org claim.
- `Principal` (`src/cityvision/api/deps.py:16-18`) mirrors this: `username`, `role`
  only.
- `resolve_city_id()` (`src/cityvision/api/deps.py:106-110`) just takes the caller's
  optional `city_id` query param and falls back to one global
  `settings.default_city` (`CITYVISION_DEFAULT_CITY=erzurum`). **The server never
  derives which city a request is for from who's logged in.**
- Several endpoints don't even have that: `ingest.py`'s `list_runs`,
  `run_detections`, `run_track`, `run_annotated`, and `media_jobs.py`'s `list_jobs`,
  `get_job`, `event_media_list` have **no city filtering at all** — broader gap than
  just "not enforced," these routes don't scope by city in any form yet.
- `ApiKeyMiddleware` (`src/cityvision/api/auth.py:14-26`) defines `OPEN_READ_PREFIXES`
  — `/api/events`, `/api/zones`, `/api/vehicles`, `/api/cameras`, `/api/routes`,
  `/api/assets`, `/api/runs`, `/api/reviews`, `/api/work-orders`, `/api/jobs`,
  `/api/users` — where **GET requires no credential at all**. This looks like a
  deliberate "operator dashboard polls without a credential" design choice, not a bug
  (see comment at `auth.py:11`) — but it means today, with no city enforcement, an
  unauthenticated caller can read *any* city's data by passing a different
  `city_id` query param.
- Single shared secrets for the whole deployment: one `DATABASE_URL`, one
  `CITYVISION_JWT_SECRET`, one `CITYVISION_API_KEY`, one `CITYVISION_DEFAULT_CITY`
  (`.env.example`, `docker-compose.yml`).

**Bottom line:** the schema anticipated multi-city use but auth was never wired to
it. This is a backend security-hardening project, not a rewrite — the hardest
structural piece (partitioning tables by city) is already ~80% done.

## Goals

1. Every user belongs to exactly one city (with an explicit path for staff who need
   cross-city access).
2. The server derives which city a request is scoped to from the authenticated
   principal — never trusts a client-supplied `city_id` for anything but display
   convenience within that user's own city.
3. A structural guarantee (not just "we audited every endpoint") that one city's data
   cannot leak into another's response, even if a future endpoint forgets a filter.
4. Decide deliberately what stays "open read within your city" vs. requires auth —
   not by omission.
5. No loss of existing Erzurum data or downtime beyond a normal migration window.

## Non-goals (for this pass)

- Full database-per-tenant or schema-per-tenant isolation. Row-level scoping in a
  shared database is the right pattern here given how much of the schema is already
  built around a shared `city_id` column — physical DB separation is a much bigger
  lift with little benefit unless a specific municipality's contract demands it.
- A generic "organizations" concept beyond city. If a non-municipal tenant type is
  ever needed, city_id can be generalized to org_id later; don't build that now.

---

## Phase 1 — Schema: tie users to a city

New migration `db/init/009_multitenancy.sql`:

```sql
-- Users belong to exactly one city. NULL means "cross-city" (see role below) --
-- only allowed for a new 'superadmin' role, enforced at the application layer.
ALTER TABLE users ADD COLUMN IF NOT EXISTS city_id TEXT REFERENCES cities(id);

-- Backfill existing users to the current single-city deployment.
UPDATE users SET city_id = 'erzurum' WHERE city_id IS NULL AND role <> 'superadmin';

CREATE INDEX IF NOT EXISTS idx_users_city ON users(city_id);

-- Add the cross-city role. Ordinary admin/operator/viewer stay single-city.
-- (Extends whatever check/constraint exists on users.role today — verify against
-- the live schema before writing this, domain/statuses.py is the source of truth
-- for role literals and will need 'superadmin' added there too.)
```

Also add `city_id` to `edge_devices` / `edge_uploads` if not already present from
`007_edge.sql` / `008_memphis_video.sql` (verify — `edge.py` already threads
`city_id` through device registration and uploads, so this may already exist; confirm
before assuming a gap).

## Phase 2 — Auth: put the city in the token

`src/cityvision/api/security.py`:
- `create_access_token(username, role, city_id, expires_minutes=...)` — add `city_id`
  to the JWT payload (`"city_id": city_id`, `None`/omitted for `superadmin`).
- Wherever `create_access_token` is currently called (find via
  `grep -rn create_access_token src/`), pass the user's `city_id` from their DB row.

`src/cityvision/api/deps.py`:
- `Principal` gains a `city_id: Optional[str]` field.
- `resolve_principal()` reads `payload.get("city_id")` into the new field.
- API-key principal (`Principal(username="api_key", role="admin")`) is inherently
  cross-city today — decide whether the shared API key should be retired in favor of
  per-city keys (recommended, see Phase 6) or explicitly treated as a superadmin-
  equivalent bypass (document it clearly if so; don't leave it ambiguous).

## Phase 3 — Request scoping: stop trusting the caller's `city_id`

This is the actual fix. Replace `resolve_city_id(city_id)` with something that takes
the principal:

```python
def resolve_city_id(principal: Principal, requested_city_id: Optional[str] = None) -> Optional[str]:
    """Derive the effective city scope from who's asking, not what they asked for."""
    if principal.role == "superadmin" or principal.username == "api_key":
        # Cross-city staff may request a specific city; None means "no filter" for
        # endpoints that support listing across cities (audit which ones should).
        return requested_city_id
    if principal.city_id is None:
        raise HTTPException(status_code=403, detail="user has no assigned city")
    if requested_city_id and requested_city_id != principal.city_id:
        raise HTTPException(status_code=403, detail="cannot access another city's data")
    return principal.city_id
```

Every call site changes from `resolve_city_id(city_id)` to
`resolve_city_id(principal, city_id)`, which means every route using it needs
`principal: Principal = Depends(get_principal)` added if it doesn't already take one.

**Endpoints found to have `resolve_city_id()` calls today** (all need this update):
- `routers/events.py:30`
- `routers/auth_export.py:132`
- `routers/health.py:41`
- `routers/fleet.py:72`
- `routers/zones.py:21,29`

**Endpoints found with `city_id` handling but not via `resolve_city_id()`** — audit
these separately, they have their own ad hoc logic (`routers/edge.py:76,110,137,306`)
— device registration/uploads. These matter for Phase 6 (edge tokens should be
per-city too).

**Endpoints found with *zero* city scoping today** — these are new work, not just a
fix:
- `routers/ingest.py`: `list_runs`, `run_detections`, `run_track`, `run_annotated`
- `routers/media_jobs.py`: `list_jobs`, `get_job`, `event_media_list`, and the
  `/jobs/ingest*` POST endpoints

For open-read endpoints (per `auth.py`'s `OPEN_READ_PREFIXES`), decide explicitly:
either (a) require auth going forward so `resolve_city_id` has a principal to work
from, or (b) keep them open but restrict to a *single default city per deployment*
(only viable if each municipality truly gets its own deployment, which defeats the
point of multi-tenancy) — **(a) is the right call** if this is genuinely going
multi-tenant; keeping anonymous cross-city reads open is incompatible with the goal.

## Phase 4 — Defense in depth: Postgres Row-Level Security

Given how much of the schema already has `city_id`, RLS is a natural fit and turns
"we hope every query has the right WHERE clause" into "the database physically cannot
return the wrong city's rows."

```sql
-- Per table with city_id (events, zones, runs, assets, vehicles, jobs, routes, users, ...):
ALTER TABLE events ENABLE ROW LEVEL SECURITY;
CREATE POLICY city_isolation ON events
  USING (city_id = current_setting('app.current_city_id', true) OR
         current_setting('app.current_city_id', true) = '*');
```

The app sets `app.current_city_id` per-request (e.g. `SET LOCAL app.current_city_id =
%s` at the start of each request/transaction in `store.py`, using the value from
`resolve_city_id()`), and uses the sentinel `'*'` only for the superadmin path. This
means even a future endpoint that forgets a `WHERE city_id = ...` clause still cannot
leak cross-city rows — RLS blocks it at the database layer.

This is the single highest-leverage item in this plan for a government/municipal
data product — recommend treating it as required, not optional, given the audit
surface found in Phase 3 (several endpoints already have zero scoping today, and
future endpoints will too if a human has to remember every time).

## Phase 5 — Secrets and edge devices

- Retire the single global `CITYVISION_API_KEY` granting full cross-city admin, or
  explicitly scope it to a `superadmin`-only break-glass use, documented as such.
- Edge device tokens (`routers/edge.py`) should be minted per-city — a compromised
  device credential from one municipality's field hardware should not be able to
  touch another's data. Check how edge tokens are currently issued/verified
  (`x-edge-token` header, referenced in `auth.py:71-75`) and add city binding there.

## Phase 6 — Testing: prove isolation, don't just implement it

Before calling this done, write an explicit cross-tenant leak test suite:
- Create two test cities with a user each.
- For every endpoint, authenticate as city A's user and attempt to read/write city
  B's resources by ID and by `city_id` override — assert 403/404, not data.
- Same test again with the RLS policies temporarily disabled (comment out
  `ENABLE ROW LEVEL SECURITY`) to confirm the *application-layer* checks alone would
  have caught it — this tells you whether you're actually relying on RLS as the real
  boundary or if the app-layer checks are doing the work (both should hold
  independently).

## Sequencing / rollout

1. Phase 1 (schema) — safe, additive, no behavior change yet.
2. Phase 2 (JWT city claim) — additive, old tokens still work until they expire since
   `city_id` is optional in the payload; treat missing `city_id` as "erzurum" during
   transition.
3. Phase 3 (request scoping) — this is the behavior change. Ship behind a feature
   flag (e.g. `CITYVISION_STRICT_TENANCY=1`) so it can be enabled in staging first
   and rolled back instantly if something breaks.
4. Phase 4 (RLS) — ship after Phase 3 is stable; RLS policies should make Phase 3
   bugs *loud* (403s) rather than *silent* (wrong data), so sequencing this second
   catches app-layer bugs during the Phase 3 rollout instead of masking them.
5. Phase 5 (secrets/edge) — can happen in parallel with Phase 4.
6. Phase 6 (test suite) — write alongside Phase 3, not after; it's what tells you
   Phase 3 actually worked.

## Effort estimate

This is contained backend work, not a rewrite — most of the partitioning already
exists in the schema. The bulk of the effort is: writing and testing the RLS
policies (Phase 4), and auditing every route for correct scoping (Phase 3), since
that's where a missed endpoint becomes a real data leak. Budget for careful,
testable, incremental delivery (feature-flagged) over a big-bang cutover.
