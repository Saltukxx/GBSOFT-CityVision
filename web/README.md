# CityVision operator web app

React + TypeScript + Vite. Served by the FastAPI backend at **`/app`**. Plan: `docs/ui-ux-plan.md`.

## Develop

```bash
# backend on :8088 (needs the cityvision-db container)
.venv/bin/python scripts/serve_api.py --port 8088

# frontend with hot reload on :5173, /api proxied to :8088
cd web && npm install && npm run dev      # open http://localhost:5173/app/
```

## Build

```bash
cd web && npm run build   # → web/dist, served by FastAPI at /app
```

`Dockerfile.api` builds it automatically.

## Languages

English only at launch. All text lives in `src/locales/en.json` — never hard-code strings in
components. To add a language: copy `en.json` to `xx.json`, translate, register it in
`src/i18n.ts` (`resources` + `SUPPORTED_LANGUAGES`).

## Structure

- `src/api/` — typed API client (`client.ts`) and response types
- `src/auth/` — sign-in state; dev mode when the server has no JWT secret
- `src/components/` — shell, decision bar, evidence viewer, map, filters, toasts
- `src/pages/` — overview, review queue, event detail, map, login
