# Hafta 1+ Checklist (enhanced)

## Gate 0

- [ ] `docs/gate-0/*` belediye ile kilitlendi
- [ ] Pilot güzergâh + GPS/zones dosyaları gerçek veri ile dolduruldu

## Pipeline (kodda hazır)

- [x] Dual-model detector (A + opsiyonel B)
- [x] Tracking (ByteTrack)
- [x] Min-area / conf discard filtreleri
- [x] GPS sidecar + interpolasyon
- [x] Event fusion + composite confidence
- [x] Evidence packs (jpg/crop/clip/json)
- [x] HTML report (map + events)
- [x] Human-in-the-loop review CLI
- [x] Offline simulate demo
- [x] Unit tests (geo/events/traffic)

## Senin sıradaki işler

- [ ] Gerçek drone videosu `data/samples/demo.mp4`
- [ ] Gerçek GPS log eşleştir
- [ ] CVAT + pothole/waste annotation
- [ ] Model B fine-tune → `detection.model_b` path

## Henüz bilerek yok (sonraki faz)

- Devam edebilir çok parçalı nesne depo yüklemesi
- GPU worker lease / heartbeat / retry
- Kare ve aday bazlı detection index
- MLflow registry
