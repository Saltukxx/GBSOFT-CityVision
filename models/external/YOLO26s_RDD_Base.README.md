---
license: agpl-3.0
library_name: ultralytics
pipeline_tag: object-detection
tags:
- yolo
- yolo26
- road-damage
- pothole-detection
- crack-detection
- knowledge-distillation
model-index:
- name: YOLO26s_RDD_Base
  results:
  - task: {type: object-detection, name: Road Damage Detection}
    dataset: {name: Unified Road Defect Dataset (held-out val, 4509 imgs), type: TamAko783/Unified_Road_Defect_Dataset}
    metrics:
    - {type: mAP50, value: 0.687, name: mAP@50}
    - {type: mAP50-95, value: 0.372, name: mAP@50-95}
    - {type: F1, value: 0.665, name: F1}
---
# YOLO26s · Base (small, GT-only)

A **YOLO26s** road-damage detector (4-class CRDDC: D00 longitudinal, D10 transverse,
D20 alligator, D40 pothole) on the [Unified Road Defect Dataset](https://huggingface.co/datasets/TamAko783/Unified_Road_Defect_Dataset).

**Method:** **Ground-truth only** — no distillation. Larger-capacity supervised baseline.

## Metrics — RDD held-out validation (4,509 images, 11,470 boxes)
| Class | mAP@50 | mAP@50-95 | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|
| D00 Longitudinal | 0.630 | 0.351 | 0.699 | 0.564 | 0.625 |
| D10 Transverse | 0.669 | 0.352 | 0.710 | 0.583 | 0.640 |
| D20 Alligator | 0.715 | 0.396 | 0.742 | 0.640 | 0.687 |
| D40 Pothole | 0.733 | 0.388 | 0.774 | 0.649 | 0.706 |
| **Overall** | **0.687** | **0.372** | **0.731** | **0.609** | **0.665** |

## Full model comparison (same held-out val)
All five models in this study, evaluated identically (imgsz 640):

| Model | Variant | Params | Distillation | mAP@50 | mAP@50-95 | F1 |
|---|---|---:|---|---:|---:|---:|
| [YOLO26n_RDD_Base](https://huggingface.co/TamAko783/YOLO26n_RDD_Base) | YOLO26n | 2.4M | — (GT only) | 0.635 | 0.334 | 0.621 |
| [YOLO26n_RDD_FRDC_Distilled](https://huggingface.co/TamAko783/YOLO26n_RDD_FRDC_Distilled) | YOLO26n | 2.4M | 1 teacher (Co-DETR) | 0.640 | 0.337 | 0.625 |
| [YOLO26n_RDD_FRDC_Distilled_v2](https://huggingface.co/TamAko783/YOLO26n_RDD_FRDC_Distilled_v2) | YOLO26n | 2.4M | 2 teachers (Co-DETR+RTMDet) | 0.638 | 0.337 | 0.626 |
| **➤ YOLO26s_RDD_Base** (this model) | YOLO26s | 9M | — (GT only) | **0.687** | **0.372** | **0.665** |
| [YOLO26s_RDD_FRDC_Distilled_v2](https://huggingface.co/TamAko783/YOLO26s_RDD_FRDC_Distilled_v2) | YOLO26s | 9M | 2 teachers (Co-DETR+RTMDet) | 0.692 | 0.375 | 0.672 |

**Reading it:**
- **Distillation helps** — every distilled model beats its GT-only baseline.
- **Capacity helps most** — the YOLO26s models (+~0.05 mAP@50) clearly outperform the nano ones on this val.
- **One vs two teachers** is a near-tie at nano size; the two-teacher set's edge is small.
- **Cross-domain check (independent RDDC2024-ID, Indonesia, 8,901 imgs):** distilled models
  generalized *better* than baselines, while the larger GT-only model generalized *worse* —
  evidence the distillation's added data improves robustness, not just in-domain fit.

> RDD ground truth has known missing annotations, so absolute precision/recall are conservative
> for all models. The comparison is fair — every model uses the identical held-out val, never trained on.

## Usage
```python
from ultralytics import YOLO
model = YOLO("YOLO26s_RDD_Base.pt")
results = model("road.jpg")
```

## Models in this suite
- [YOLO26n_RDD_Base](https://huggingface.co/TamAko783/YOLO26n_RDD_Base) · [YOLO26n_RDD_FRDC_Distilled (v1)](https://huggingface.co/TamAko783/YOLO26n_RDD_FRDC_Distilled) · [YOLO26n_RDD_FRDC_Distilled_v2](https://huggingface.co/TamAko783/YOLO26n_RDD_FRDC_Distilled_v2)
- [YOLO26s_RDD_Base](https://huggingface.co/TamAko783/YOLO26s_RDD_Base) · [YOLO26s_RDD_FRDC_Distilled_v2](https://huggingface.co/TamAko783/YOLO26s_RDD_FRDC_Distilled_v2)

## Datasets
- Base: [TamAko783/Unified_Road_Defect_Dataset](https://huggingface.co/datasets/TamAko783/Unified_Road_Defect_Dataset)
- Distillation sets: [v1](https://huggingface.co/datasets/TamAko783/Unified_Road_Defect_FRDC_Pseudolabeled) ·
  [v2 (two-teacher)](https://huggingface.co/datasets/TamAko783/Unified_Road_Defect_FRDC_Pseudolabeled_v2)

## Credits
- Datasets: RDD-2022 (Arya et al.) · UAV-PDD2023 · RoadDamageVision (Silva Zendron & Leithardt, CC BY 4.0).
- Distillation teachers: **Co-DETR Swin-L + RTMDet-x** — FRDC (Wang Fangjun et al.), ORDDC'2024 winner.
- Student: YOLO26s, AGPL-3.0 (Ultralytics).
