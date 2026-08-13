# Model B dataset (YOLO format)

```text
model_b/
  images/train/*.jpg
  images/val/*.jpg
  labels/train/*.txt
  labels/val/*.txt
```

Each label line:

```text
class_id x_center y_center width height
```

All values normalized 0–1. Class IDs:

| id | class |
| -- | ----- |
| 0 | overflowing_container |
| 1 | street_waste |
| 2 | pothole |
| 3 | road_crack |
| 4 | road_damage |

## CVAT → YOLO

1. Project labels exactly as table above (order matters).
2. Export **YOLO 1.1** / Ultralytics YOLO.
3. Split ~80/20 train/val (video-aware: aynı sahnedeki frame’leri ayırma).

## Minimum ilk eğitim

- ≥ 300–500 pozitif pothole örneği
- ≥ 200 waste/container örneği
- Bol hard-negative (yama, gölge, kar) içeren arka plan frame’leri
