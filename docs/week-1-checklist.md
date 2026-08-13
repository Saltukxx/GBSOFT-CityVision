# Hafta 1+ Checklist (enhanced)

## Gate 0

- [ ] `docs/gate-0/*` belediye ile kilitlendi
- [ ] Pilot güzergâh + GPS/zones dosyaları gerçek veri ile dolduruldu

## Pipeline (kodda hazır)

- [x] Dual-model detector (A + opsiyonel B)
- [x] Tracking (ByteTrack)
- [x] Min-area / conf discard filtreleri
- [x] GPS sidecar + interpolasyon
- [x] Geofence → potential bus stop obstruction
- [x] Traffic counting (unique tracks, line cross, vpm/vph)
- [x] Event fusion + composite confidence
- [x] Evidence packs (jpg/crop/clip/json)
- [x] HTML report (map + events)
- [x] Human-in-the-loop review CLI
- [x] Offline simulate demo
- [x] Unit tests (geo/events/traffic)

## Senin sıradaki işler

- [ ] Gerçek sokak videosu `data/samples/demo.mp4`
- [ ] Gerçek GPS log eşleştir
- [ ] CVAT + pothole/waste annotation
- [ ] Model B fine-tune → `detection.model_b` path

## Henüz bilerek yok (sonraki faz)

- FastAPI / PostGIS cloud backend
- Jetson edge deploy
- MLflow registry
- Canlı dashboard servisi (şu an static `report.html`)
