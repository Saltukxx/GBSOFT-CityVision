# GBSoft City Vision

Belediye araçlarını hareketli şehir sensörlerine dönüştüren platform iskeleti.

```text
Video (+ GPS + Zones)
   → Dual Detector (Model A/B) + Tracking
   → Traffic analytics
   → Geofence (bus-stop obstruction candidates)
   → Event fusion + composite confidence
   → Evidence packs
   → HTML report (map + events)
   → Human review feedback loop
```

## Kurulum

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pip install -e .
```

## Tam pipeline (YOLO)

```bash
python scripts/run_pipeline.py \
  --source data/samples/demo.mp4 \
  --output outputs/demo_001 \
  --gps configs/gps.example.csv \
  --zones configs/zones.example.geojson \
  --vehicle-id BUS-17 \
  --camera-id FRONT

# Clip a window without editing yaml (e.g. 5 minutes starting at 0):
# python scripts/run_pipeline.py --source data/samples/d100_osmancik.mp4 \
#   --output outputs/d100_5m --start-sec 0 --duration 300 --stride 2
```

Çıktılar:

- `detections.jsonl` — frame bazlı detection (+ GPS)
- `events.json` — fused municipal events
- `traffic.json` — unique tracks / line crossings / vpm-vph
- `evidence/<EVENT_ID>/` — event.jpg, crop, clip, event.json
- `annotated.mp4` — HUD + bbox + count line
- `report.html` — operatör ekranı (harita + tablo)

## Backend (PostgreSQL + PostGIS + FastAPI)

Plan §21 iskeleti: fleet, routes, events, observations, detections (özet), event_media, zones, users, work_orders, model_versions.

```bash
docker compose up -d db
pip install -r requirements.txt
python db/migrate.py
python scripts/seed_backend.py
python scripts/ingest_run.py outputs/simulate_001
python scripts/serve_api.py --port 8088
```

- Dashboard (4 ekran):
  - Harita: http://127.0.0.1:8088/map
  - Güzergâh: http://127.0.0.1:8088/live
  - Tespit videosu: http://127.0.0.1:8088/detect
  - Olay detay: http://127.0.0.1:8088/events/{id}
- OpenAPI: http://127.0.0.1:8088/docs
- Health: `/health` · KPIs: `/api/kpis`
- Fleet: `/api/vehicles` `/api/cameras` `/api/routes` `/api/assets`
- Events: `/api/events` `/api/events/{id}` (media + observations)
- Media: `/api/media/{id}` · Object store: `/api/storage/evidence/...`
- Async jobs: `POST /api/jobs/ingest` → `GET /api/jobs/{id}`
- Redis worker (optional): `docker compose --profile redis up -d` then `REDIS_URL=redis://localhost:6380/0 python scripts/job_worker.py`
- MinIO/S3 (optional): `docker compose --profile minio up -d` + set `CITYVISION_S3_ENDPOINT=http://127.0.0.1:9000`
- Work orders: `PATCH /api/work-orders/{id}` (`status` / `assignee`)
- Auth (optional): `CITYVISION_API_KEY` and/or JWT (`POST /api/auth/login`)
  - **Kanıt medyası kimliğe bağlı:** API key veya JWT secret set edildiği anda
    `/api/storage/*`, `/api/media/*` ve `/api/runs/{id}/annotated` kimlik ister.
    Tarayıcı `<img>`/`<video>` etiketi header gönderemediği için listeleme
    uçları kısa ömürlü **imzalı URL** döndürür (`?exp=…&sig=…`,
    `CITYVISION_MEDIA_URL_TTL_SEC`). İkisi de boşsa API tamamen açıktır —
    laptop demosu için uygun, kurulum için değil.
  - Dashboard'da token: tarayıcı konsolundan `CV.setToken("<jwt>")` veya
    `?token=<jwt>` query parametresi (localStorage'a yazılır).
- **Memphis (pilot, Jetson yok):** araçtan video+GPS → merkezi YOLO
  - Admin: `POST /api/edge/devices` (token bir kez)
  - Device: `POST /api/edge/heartbeat`, `POST /api/edge/video` (`file` mp4 + optional `gps` jsonl) + `X-Edge-Token`
  - Status: `GET /api/edge/video/{upload_id}` → job `analyze_video` → pipeline → ingest/merge
  - Lab uploader: `python -m cityvision.edge.agent upload --video seg.mp4 --gps gps.jsonl --token … --outbox`
  - GPS sidecar satırı: `{"timestamp_ms":0,"lat":39.9,"lon":41.27}` (jsonl) veya CSV `timestamp_ms,lat,lon`
  - Jetson on-device AI: **faz-2** (şimdi yok); events zip upload API ileride edge için duruyor
- Edge events zip (faz-2 / hazır API): `POST /api/edge/upload` → `GET /api/edge/uploads/{id}`
- Local jobs without Redis: `CITYVISION_JOB_INLINE=1`
- Audit: `GET /api/audit` · CSV: `GET /api/events/export.csv` · Job SSE: `/api/jobs/{id}/stream`
- Zones: `python scripts/ingest_zones.py …` · Review DB: `cityvision review … --db`
- `DATABASE_URL` → `.env` / `.env.example` (port **5435**)

## Offline event demo (YOLO gerekmez)

Üç otobüsün aynı çukuru görmesi + durak geofence senaryosu:

```bash
docker compose up -d db
python db/migrate.py
python scripts/demo_e2e.py
python scripts/serve_api.py --port 8088
# tarayıcı: http://127.0.0.1:8088/map
```

Sadece rapor:

```bash
python scripts/simulate_events_demo.py
open outputs/simulate_001/report.html
```

## Test & lint

```bash
pytest          # tests/ dizinini toplar; DB kapalıysa PostGIS testleri skip
ruff check .
```

DB'ye bağlı testleri gerçekten koşturmak için önce `docker compose up -d db`
ve `python db/migrate.py`. CI (`.github/workflows/ci.yml`) PostGIS servisiyle
çalışır ve testler skip'e düşerse job'ı kırar.

## Human-in-the-loop

```bash
python -m cityvision.cli review \
  --output outputs/simulate_001 \
  --event-id POT-00001 \
  --label correct \
  --apply
```

## Config

- `configs/pipeline.yaml` — detection, tracking, GPS, geofence, traffic, fusion, evidence
- `configs/classes.yaml` — MVP taxonomy + COCO bootstrap map
- `configs/zones.example.geojson` — bus stop polygons
- `configs/gps.example.csv` — timestamped GPS sidecar

## Model A / B

| Model | Rol | Varsayılan |
| ----- | --- | ---------- |
| A | car/bus/truck/motorcycle/person… | `yolov8n.pt` |
| B road | pothole / road_crack / road_damage | `models/infra-b-road-rdd.pt` ([HF YOLOv8s RDD](https://huggingface.co/vinothvikas1987/pothole-detection-yolov8); aliases in `configs/classes.yaml`) |
| B waste | overflowing_container | `models/infra-b-waste.pt` |

Model B eğitimi: [`docs/training-model-b.md`](docs/training-model-b.md)

```bash
# Hazır pothole dataset (Hugging Face RoadEye)
python scripts/prepare_public_pothole.py --train-limit 1500
python scripts/train_model_b.py --data configs/model_b_road.data.yaml --epochs 40 --device mps --export-to models/infra-b-road.pt
python scripts/run_pipeline.py --source data/samples/demo.mp4 --output outputs/demo_b --model-b models/infra-b-road.pt
```

## CVAT (etiketleme)

```bash
bash scripts/cvat_up.sh
# http://localhost:8080
# admin: docker exec -it cvat_server bash -ic 'python3 ~/manage.py createsuperuser'
```

Rehber: [`docs/cvat-setup.md`](docs/cvat-setup.md)

## Gate 0 dokümanları

`docs/gate-0/` ve `docs/week-1-checklist.md`

## Lisans notu

Production öncesi Ultralytics Enterprise vs alternatif stack kararı verilmelidir.
