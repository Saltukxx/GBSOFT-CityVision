# CityVision — UI / UX Plan

**Goal:** a web app a municipality can use daily during a 2-month drone pilot, without GBSoft staff in the room.
**Principle:** the model proposes, a person decides. Every screen is built to make that decision fast and well-evidenced.
**North-star metric:** time-to-decision per correct event (see `plan.md` §13).

---

## 1. Where the UI is today

| Page | File | State |
| --- | --- | --- |
| Operator queue | `api/static/index.html` | Works: list + confirm / false alarm / work order / resolved (Turkish labels) |
| Event detail | `api/static/event.html` | Works: evidence + same 4 actions |
| Map | `api/static/map.html` | Leaflet map of events |
| Detections | `api/static/detect.html` | Per-run detection viewer (internal) |
| Route | `api/static/live.html` | Per-run GPS track (internal) |
| Landing | `api/static/landing.html` | Marketing page |

**Gaps blocking a pilot**

- No login screen — token is set from the browser console (`CV.setToken`).
- No way for the municipality to upload a flight or see flight processing status.
- No flight list / flight detail (the unit the pilot is organised around).
- Work orders exist in the API but have no screen.
- No user management, no city settings, no audit view.
- No KPI / weekly pilot report.
- Review actions don't capture *why* something was wrong, so they can't feed retraining.
- Nav is inconsistent (index has no nav; nav shows internal tools).
- Turkish only, hard-coded strings — no translation layer.

## 2. Users

| Persona | Role (`domain/statuses.py`) | Main job | Device |
| --- | --- | --- | --- |
| **Reviewer** (municipal operator) | `operator` | Clear the queue: confirm / reject candidates | Desktop, 2–4 h/day |
| **Unit manager** (public works / sanitation) | `operator` | Turn confirmed events into work orders, track closure | Desktop + tablet |
| **Drone pilot** | `operator` | Upload flights, see they processed | Laptop in the field |
| **City admin** | `admin` | Users, zones, routes, retention settings | Desktop |
| **Leadership** (deputy mayor) | `viewer` | See pilot results, weekly report | Phone / PDF |
| **GBSoft ML / support** | `superadmin` | Cross-city health, labelling, model versions | Desktop |

## 3. Information architecture

```text
Login
└─ App shell (city switcher for superadmin, user menu, language switcher — EN only at launch)
   ├─ Overview          — KPIs, this week, pending queue count
   ├─ Review queue      — the core screen
   │   └─ Event detail  — evidence, map, history, decision
   ├─ Map               — all events, filters, zones, flight tracks
   ├─ Flights           — list, upload, processing status
   │   └─ Flight detail — track, video timeline, events from this flight
   ├─ Work orders       — kanban/list by status
   ├─ Reports           — weekly pilot report, CSV export
   └─ Admin             — users, zones & routes, settings, audit log
GBSoft internal (superadmin only)
   ├─ Labelling queue   — rejected/corrected events → training data
   ├─ Model versions    — which model ran on which flight, eval results
   └─ Detections / Route debug (today's detect.html, live.html)
```

## 4. Screens

Priority: **P0** = needed before pilot day 1 · **P1** = needed by pilot week 3 · **P2** = later.

### 4.1 Login — P0
- Username + password → JWT (`POST /api/auth/login`), stored, auto-redirect.
- Session expiry → back to login with a message, not a silent 401.
- Remove the `?token=` URL path for normal users.

### 4.2 App shell — P0
- Left sidebar on desktop, bottom tab bar on phone.
- Badge on "Review queue" with pending count.
- City name always visible (tenancy must be obvious; superadmin gets a switcher).
- Menu items hidden by role, not just disabled.

### 4.3 Review queue — P0 (most important screen)
**Layout:** list on the left, selected event on the right (no page change per event).

- Each row: thumbnail crop, type (Waste / Pothole / …), confidence, place name, flight date, "seen N times".
- Filters: type, confidence band, flight, zone, date. Default sort: confidence high → low.
- Right pane: large evidence frame with box (later SAM3 mask), toggle crop/full frame, short clip, mini-map.
- **Decision bar:** `Confirm` · `False alarm` · `Not sure` · `Create work order`.
- **Keyboard first:** `J/K` next/prev, `A` confirm, `R` reject, `U` unsure, `W` work order, `Z` undo. Target: < 5 s per obvious event.
- On *False alarm*, one-click reason chips: `manhole`, `shadow`, `vehicle`, `paint/marking`, `leaves`, `other`. Optional "draw correct box".
  → This is the bridge to retraining during the pilot (see 4.10).
- Undo toast for 5 s after every decision.
- Empty state: "Queue clear — next flight scheduled …".
- Bulk select for duplicates ("merge into one event").

API: `GET /events`, `POST /events/{id}/review` (add `reason`, `corrected_box`), `PATCH /events/{id}/status`.

### 4.4 Event detail — P0
Full page (shareable link) for one event:
- All observations of the event across flights (timeline strip) — shows recurrence of a dump site.
- Map with estimated target position + accuracy circle, drone position separately (`plan.md` §6).
- History: who decided what, when (from audit).
- Linked work order, if any.

### 4.5 Map — P0
- Clustered markers coloured by status; type icons.
- Layers: events, zones (`/zones.geojson`), flight tracks, heat map of recurrence.
- Filter panel shared with the review queue (same filter state/URL params).
- Click marker → side drawer with event summary + "open in review".
- Before/after slider for the same spot across two flights — P2.

### 4.6 Flights — P0
- **List:** date, route, pilot, duration, status (`uploading → processing → ready / failed`), number of candidates.
- **Upload:** drag-and-drop video + SRT/telemetry, route picker, resumable multipart upload with progress bar; works on hotel/field Wi-Fi.
- Live processing progress (existing `GET /jobs/{id}/stream`).
- Clear error states: "telemetry missing", "outside approved corridor", "unsupported format".
- FlightHub-synced flights appear automatically with a "FlightHub" tag.

### 4.7 Flight detail — P1
- Track on map, video player with a timeline showing where candidates occur; click a marker to jump.
- Flight quality checks vs route spec (altitude, speed, gimbal) — warns when data won't be comparable.

### 4.8 Work orders — P1
- Kanban: `Created → Assigned → In progress → Resolved / Cancelled`.
- Assign to unit/person, due date, note, close with "after" photo (optional).
- CSV export (exists: `/events/export.csv`); API/webhook adapter later.

### 4.9 Overview + Reports — P1
- Overview cards: candidates this week, reviewed %, confirmed, false alarms per flight hour, median review time, open work orders.
- Show the pilot targets from `plan.md` §7 next to actual values (green/amber/red).
- **Weekly pilot report:** one-click PDF for leadership — map snapshot, top events, KPIs vs targets, model improvement since last week.

### 4.10 Labelling & model loop (GBSoft internal) — P1
Makes the "collect 2 months of images and train on them" plan workable.
- Queue of rejected events (with reasons), "unsure" events, and corrected boxes.
- Fast box editor (reuse the existing browser labeller's interaction model; SAM3 click-to-mask later).
- Mark frames as **test-only** (held-out flights) so they never enter training.
- Export to the RF-DETR training format; show which model version is live per city.

### 4.11 Admin — P1
- Users: invite, role, deactivate (`POST /auth/users`).
- Zones & routes: upload GeoJSON/KML, draw on map, approved-corridor polygon.
- Settings: retention days, confidence threshold per type, enabled event types.
- Audit log viewer with filters (`GET /audit`).

### 4.12 Search (SAM3 visual search) — P2
- Search box: known types answer instantly from the index; new text queries show "searching N candidate frames…" then results (see `docs/sam3-visual-search-plan.md`).
- "Find similar" button on any event.

## 5. UX rules

1. **Evidence first.** Never show a type/confidence without the image next to it.
2. **Plain words, not ML words.** "Confidence: High / Medium / Low" instead of `0.73`; raw score in a tooltip.
3. **One event = one card**, even if the drone saw it in 40 frames.
4. **Every decision is reversible** (undo, status history) and audited.
5. **Location honesty:** always show the accuracy radius; never imply exactness.
6. **Privacy by default:** faces/plates blurred in evidence shown to viewers; raw frames only for operators.
7. **Fast on modest hardware:** municipal PCs and 1080p screens; proxies not raw 4K.
8. **English first, translation-ready:** launch in English only, but every user-facing string goes through the i18n layer from day one (see §7a), so Turkish, Finnish, Croatian etc. can be added without code changes.
9. **Accessible:** status never conveyed by colour alone; keyboard reachable; WCAG AA contrast.

## 6. Visual design

- Keep the current identity (IBM Plex Sans/Mono, `app.css` tokens) and formalise it into a small design system: colours, type scale, spacing, status colours, event-type icons.
- Light theme default (offices), dark theme for map-heavy use.
- Components to build once: AppShell, DataTable, FilterBar, EvidenceViewer (frame + box/mask + crop toggle), MapView, DecisionBar, StatusPill, KPI card, Upload dropzone, Toast, Empty/Error states.
- Do the visual design in Figma first for: review queue, map, flights upload, overview.

## 7. Technical approach

Today's pages are vanilla JS + Leaflet (~1k lines). The new scope (stateful queue, keyboard flows, uploads, kanban, i18n, role-based nav) will outgrow that.

**Recommendation:** a single-page app in `web/` — **React + TypeScript + Vite**, TanStack Query for API state, React Router, MapLibre GL (or keep Leaflet), i18next. Built to static files and served by FastAPI under `/app`, so deployment stays one container. Keep `landing.html` as is.

Backend work the UI needs:

| Need | Endpoint change |
| --- | --- |
| Reject reasons, corrected boxes, "unsure" | extend `POST /events/{id}/review` |
| Flight entity (list/detail/status) | new `GET /flights`, `GET /flights/{id}` (wrap runs + FlightHub) |
| Resumable upload | presigned multipart upload to object storage |
| Event observations timeline | `GET /events/{id}/observations` |
| KPIs vs targets, weekly report | extend `/api/kpis`, add `GET /reports/weekly` (PDF) |
| Work order assign/notes | extend `PATCH /work-orders/{id}` |
| Labelling export / test-only flag | new `/labelling/*` (superadmin) |
| Settings | `GET/PATCH /cities/{id}/settings` |

### 7a. Languages

- **Launch language: English.** All P0/P1 screens ship in English only.
- **Translation-ready from day one:** every string lives in `web/src/locales/en.json` (i18next keys like `review.actions.confirm`); no text hard-coded in components.
- Dates, numbers and distances formatted with `Intl` (locale-aware), never by hand.
- Layouts tolerate ~40 % longer text (Finnish, German, Croatian) — no fixed-width buttons.
- Backend returns codes, not sentences (`status: "false_positive"`, `reason: "manhole"`); the UI translates them.
- Language stored per user, defaulting to the city's language setting.
- **Adding a language later** = add `xx.json`, translate, review with a native speaker. Likely order follows the sales pipeline: Turkish → Croatian → Finnish.
- Existing Turkish strings in `api/static/*` become the seed for `tr.json`.

## 8. Build order

| Phase | Weeks | Deliverable |
| --- | --- | --- |
| **0. Design** | 1 | Figma for P0 screens, design tokens, component list; walkthrough with 1–2 real municipal staff if possible |
| **1. Shell + core** ✅ | 2–3 | i18n setup (EN), login, app shell, review queue with keyboard flow and reasons, event detail, map |
| **2. Flights** ✅ | 4 | Flight list, resumable upload, processing status |
| **Pilot starts** | — | P0 complete |
| **3. Operations** ✅ | 5–6 | Work orders, overview KPIs, admin (users, zones, settings, audit) |
| **4. Learning loop** ✅ | 6–7 | Labelling queue, test-only flags, model versions, weekly PDF report |
| **5. Later** | — | SAM3 search, flight video timeline, before/after compare, mobile field app |

### Build notes

- **Phase 1 + 2 done (30 Oct 2026)** in `web/` — see `web/README.md`. Phase 0 (Figma) was skipped; the design system lives in `web/src/styles.css`.
- **Uploads go through the API in 8 MB chunks**, not presigned direct-to-S3 as first planned: works the same with local disk and MinIO/S3, needs no bucket CORS, and resumes from whatever chunks the server already holds. Revisit if pilot uploads get large enough to load the API server.
- **Phase 3 done (31 Oct 2026):** work-order board, admin (users, zones & routes, settings, audit log), 7-day review stats on the overview. Settings only expose what the app uses today (city name, time zone, language, work-order units); retention, thresholds and enabled event types wait until the pipeline reads them.
- **Phase 4 done (31 Oct 2026):** labelling queue + box editor (GBSoft only), test-flight hold-out, YOLO training-set export (`/api/labelling/export.zip`, same layout `scripts/train_rfdetr.py` reads; flight-level train/val split, held-out flights → test; manhole only as hard negative), per-model accuracy from reviewer decisions (Admin → Models), weekly report page with print-to-PDF.
- **Routes & flight paths (31 Oct 2026):** Routes page (draw/edit waypoints on the map, altitude/speed/gimbal, camera-footprint band, distance + flight-time estimate, KML/GeoJSON export for the pilot), flight-path layer on the main map, planned-vs-flown comparison on each flight with route adherence (coverage within 30 m, time off route, max deviation — PostGIS). Migration `016`.
- **Training images must be clean.** `event.jpg` has the detector's box drawn on it; the pipeline now also saves `frame_clean.jpg`, and only clean frames can be labelled/exported. Older events: `scripts/backfill_clean_frames.py` recovers the exact frame from the evidence clip.
- **Evidence storage keys are now per run** (`evidence/<event>/<run>/…`). Event IDs repeat across runs, and the old shared key let later runs overwrite earlier files.
- **Pilot targets** on the overview show a live value only for queue precision, and only after 20+ confirm/reject decisions. Recall and top-20 precision need the gold set.
- **A flight = an `edge_video_uploads` row**, whichever way it arrived (browser, drone device, FlightHub). See `src/cityvision/api/routers/flights.py`.

## 9. How we'll know the UX works

- Median time per review decision < 10 s (obvious cases < 5 s).
- Reviewer can clear a typical flight's queue in < 15 min.
- New municipal user completes upload → review → work order without help on first try.
- ≥ 90 % of rejections carry a reason (feeds retraining).
- Leadership opens the weekly report (track opens/downloads).

## 10. Open questions

1. Who in the pilot municipality does the reviewing — dedicated staff or existing unit staff part-time? (Changes how much keyboard/bulk tooling matters.)
2. Do they need to push work orders into an existing system (e.g. CRM/ERP), or is our kanban enough for the pilot?
3. Is a phone UI needed for field crews in the pilot, or desktop only?
4. Designer available, or do we design directly in code from the component list?
