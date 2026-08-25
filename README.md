# GBSoft City Vision

DJI drone ile tekrarlanabilir koridor taraması: tespit + GPS + fusion + insan onayı.

```text
Drone video (+ DJI SRT GPS)
   → Dual Detector (Model A/B) + Tracking
   → Manhole overlays pothole (IoU)
   → Event fusion + composite confidence
   → Evidence packs
   → HTML report (map + events)
   → Human review feedback loop
```

Varsayılan sensör **DJI drone** (`nadir` tarama veya `oblique` alçak inceleme). Trafik çizgisi ve durak geofence motoru durur; MVP’de kapalıdır.

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
  --source data/samples/dji_fly_20260816.mp4 \
  --output outputs/dji_001 \
  --drone-id DJI-01 \
  --profile oblique

# Nadir (kuşbakışı) tarama:
# python scripts/run_pipeline.py --source clip.mp4 --output outputs/nadir \
#   --profile nadir --drone-id DJI-01

# GPS: --gps path veya videonun yanındaki .SRT otomatik
# python scripts/run_pipeline.py --source clip.mp4 --output out --gps clip.SRT
```

Çıktılar:

- `detections.jsonl` — frame bazlı detection (+ GPS)
- `events.json` — fused municipal events (`manhole` iş emri değildir)
- `traffic.json` — boş (MVP’de trafik çizgisi kapalı)
- `evidence/<EVENT_ID>/` — event.jpg, crop, clip, event.json
- `annotated.mp4` — HUD + bbox (count line yok)
- `report.html` — operatör ekranı (harita + tablo)

## Backend (PostgreSQL + PostGIS + FastAPI)

Plan §21 iskeleti: fleet, routes, events, observations, detections (özet), event_media, zones, users, work_orders, model_versions.

`vehicle_id` API/DB’de asset anahtarıdır (drone / dock id).

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
- **Drone upload (pilot, onboard Jetson yok):** Dock/Fly MP4+SRT → merkezi YOLO
  - Admin: `POST /api/edge/devices` (token bir kez)
  - Device: `POST /api/edge/heartbeat`, `POST /api/edge/video` (`file` mp4 + optional `gps` jsonl) + `X-Edge-Token`
  - Status: `GET /api/edge/video/{upload_id}` → job `analyze_video` → pipeline → ingest/merge
  - Lab uploader: `python -m cityvision.edge.agent upload --video seg.mp4 --gps gps.jsonl --token … --outbox`
  - GPS sidecar: DJI `.SRT`, JSONL `{"timestamp_ms":0,"lat":39.9,"lon":41.27}` veya CSV `timestamp_ms,lat,lon`
  - Jetson on-device AI: **faz-2** (şimdi yok); events zip upload API ileride edge için duruyor
- Edge events zip (faz-2 / hazır API): `POST /api/edge/upload` → `GET /api/edge/uploads/{id}`
- Local jobs without Redis: `CITYVISION_JOB_INLINE=1`
- Audit: `GET /api/audit` · CSV: `GET /api/events/export.csv` · Job SSE: `/api/jobs/{id}/stream`
- Zones: `python scripts/ingest_zones.py …` · Review DB: `cityvision review … --db`
- `DATABASE_URL` → `.env` / `.env.example` (port **5435**)

## DJI Dock (FlightHub 2)

Dock tek bir buluta bağlanır, o yüzden uçuş operasyonu FlightHub 2'de kalır ve CityVision
biten uçuşları OpenAPI ile çeker; tespit tamamen local. Donanım gelmeden mock ile
çalıştırılabilir:

```bash
python scripts/flighthub_sync.py mock --video data/samples/smoke.mp4   # 1. terminal
CITYVISION_FH2_BASE_URL=http://127.0.0.1:8099 \
CITYVISION_FH2_USER_TOKEN=mock-organization-key \
  python scripts/flighthub_sync.py pull                                # 2. terminal
```

Rehber: [`docs/flighthub-integration.md`](docs/flighthub-integration.md) — doğrulanmamış
endpoint'ler ve ilk uçuş öncesi kontrol listesi orada.

## Offline event demo (YOLO gerekmez)

Üç bakışın aynı çukuru görmesi senaryosu:

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

- `configs/pipeline.yaml` — drone-first detection, GPS, fusion, evidence
- `configs/profiles/nadir.yaml` / `oblique.yaml` — uçuş profili overlay
- `configs/classes.yaml` — MVP taxonomy + COCO bootstrap map
- `configs/zones.example.geojson` — zone polygons (geofence MVP kapalı)
- `configs/gps.example.csv` — timestamped GPS sidecar (DJI SRT tercih)

## Model A / B

| Model | Rol | Varsayılan |
| ----- | --- | ---------- |
| A | car/bus/truck/motorcycle/person… | `yolov8n.pt` |
| B road | pothole / road_crack / road_damage | `models/infra-b-road-rdd.pt` ([HF YOLOv8s RDD](https://huggingface.co/vinothvikas1987/pothole-detection-yolov8); aliases in `configs/classes.yaml`) |
| B manhole | rögar (çukur değil; iş emri değil) | `models/infra-b-road-svrdd.pt` (`allowed_classes: [manhole]`) |
| B waste | overflowing_container | `models/infra-b-waste.pt` |

Model B eğitimi: [`docs/training-model-b.md`](docs/training-model-b.md)

```bash
# Hazır pothole dataset (Hugging Face RoadEye)
python scripts/prepare_public_pothole.py --train-limit 1500
python scripts/train_model_b.py --data configs/model_b_road.data.yaml --epochs 40 --device mps --export-to models/infra-b-road.pt
python scripts/run_pipeline.py --source data/samples/demo.mp4 --output outputs/demo_b --model-b models/infra-b-road.pt

# SVRDD (çukur + çatlak + rögar; yama hard-negative)
python scripts/prepare_svrdd.py
python scripts/train_model_b.py --data configs/model_b_svrdd.data.yaml --epochs 40 --device mps --name train_svrdd --export-to models/infra-b-road-svrdd.pt
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
