# clip10 / clip11 — 18 Ağu 2026 etiket oturumu

Kaynak: Downloads’taki 18 Ağu “2. video” (1080p) ve “4. video” (4K).
Kareler: `data/datasets/model_b_aerial/raw_frames/` (`clip10_*` 1920, `clip11_*` 3840, 1 fps).

## Durum (18 Ağu 17:20)

| | clip10 (2. video, ~71 sn) | clip11 (4. video, ~4.8 dk) |
|---|---|---|
| Kare | 72 | 291 |
| Kutulu | 40 | 57 |
| Temiz (B) | 17 | 51 |
| Atlanan | 15 | 183 |
| Kutu | 210 | 134 |
| pothole | 10 | 41 |
| road_crack | 167 | 33 |
| manhole | 5 | 8 |
| road_damage | 28 | 52 |

clip10 asıl katkısı **çatlak**. clip11 asıl katkısı **çukur**. İkisi de v4 eğitimine girdi.

## Kontrol notları

Genel sınıf ayrımı doğru (çukur / yama / çatlak / rögar). Eğitimden önce clip9 tamir şeridi `pothole` → `road_damage` çevrildi; `clip9_0046000ms` üçüncü kapak `manhole`.

Eksik rögar (kare zaten kutulu, kapak çizilmemiş — sonraki tur):

- `clip11_0092000ms` Telekom kapağı
- `clip11_0111000ms` kapak
- `clip11_0152000ms`–`0154000ms` kapak
- clip8 `0067000` / `0068000` Telekom (önceki oturum)

`clip11_0111000ms` üç küçük çukur kutusu gürültülü olabilir (moloz / sığ leke); silinmedi.

## Eğitim

```bash
python scripts/label_aerial.py --export
python scripts/train_model_b.py \
  --data configs/model_b_aerial.data.yaml \
  --model yolov8s.pt --imgsz 1280 --epochs 100 --batch 4 --device mps \
  --degrees 180 --flipud 0.5 --close-mosaic 15 --patience 25 \
  --name train_aerial_v4 --export-to models/infra-b-road-aerial-v4.pt
```

clip3 hold-out test olarak kaldı.
