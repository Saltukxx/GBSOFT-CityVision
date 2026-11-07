---
license: apache-2.0

pipeline_tag: object-detection

library_name: rfdetr

datasets:
  - dronefreak/RDD2022

tags:
  - object-detection
  - detectionbench
  - rfdetr
  - pytorch
  - computer-vision
  - road-damage
  - pavement-distress
  - infrastructure
  - pothole-detection
  - autonomous-driving
metrics:
  - map50
  - map50-95
  - precision
  - recall
  - f1

base_model: "Roboflow/rf-detr-small"

model-index:
  - name: RF-DETR Small Finetuned on RDD2022 Road Damage
    results:
      - task:
          type: object-detection
          name: Object Detection
        dataset:
          name: RDD2022 Road Damage
          type: rdd2022
        metrics:
          - type: mAP50
            value: 64.71
            name: mAP@50 (test split)
          - type: mAP50-95
            value: 35.73
            name: mAP@50-95 (test split)
          - type: precision
            value: 65.69
            name: Precision (test split)
          - type: recall
            value: 59.41
            name: Recall (test split)
        source:
          url: https://github.com/dronefreak/DetectionBench
          name: DetectionBench
---


# RF-DETR Small Finetuned on RDD2022 Road Damage

Fine-tuned RF-DETR Small object detector on the **RDD2022 Road Damage** benchmark dataset, trained and evaluated as part of [DetectionBench](https://github.com/dronefreak/DetectionBench) -- a framework for reproducibly benchmarking modern object detectors with identical training recipes and evaluation metrics across multiple real-world datasets.

<p align="center">
  <img src="rdd2022_rfdetr-small_showcase.jpg" alt="RDD2022 Road Damage Detection Demo" width="900">
</p>

<br>

<!-- ROW 1: Identity & Tech Stack -->
<div style="display: flex; justify-content: center; align-items: center; gap: 8px; margin-bottom: 8px; flex-wrap: wrap;">
  <img src="https://img.shields.io/badge/Task-Object_Detection-blue?style=flat-square" alt="Task">
  <img src="https://img.shields.io/badge/Framework-RF--DETR-0aa1a7?style=flat-square" alt="Framework">
  <img src="https://img.shields.io/badge/Base_Model-RF--DETR_Small-purple?style=flat-square" alt="Base Model">
</div>

<!-- ROW 2: Performance Metrics -->
<div style="display: flex; justify-content: center; align-items: center; gap: 8px; margin-bottom: 8px; flex-wrap: wrap;">
  <img src="https://img.shields.io/badge/mAP@50-64.71%25-success?style=flat-square" alt="mAP@50">
  <img src="https://img.shields.io/badge/mAP@50:95-35.73%25-orange?style=flat-square" alt="mAP@50:95">
  <img src="https://img.shields.io/badge/Params-32.1M-lightgrey?style=flat-square" alt="Params">
</div>

<!-- ROW 3: Metadata -->
<div style="display: flex; justify-content: center; align-items: center; gap: 8px; margin-bottom: 24px; flex-wrap: wrap;">
  <img src="https://img.shields.io/badge/License-Apache--2.0-lightgrey?style=flat-square" alt="License">
  <a href="https://github.com/dronefreak/DetectionBench"><img src="https://img.shields.io/badge/Source-DetectionBench-black?style=flat-square" alt="Source"></a>
</div>

---

## Usage

### Install Dependencies

```bash
pip install rfdetr huggingface_hub
```

### Load Model from Hugging Face

```python
from huggingface_hub import hf_hub_download
import rfdetr

weights = hf_hub_download(
    repo_id="dronefreak/rdd2022-rfdetr-small",
    filename="checkpoint_best_total.pth"
)

model = rfdetr.RFDETRSmall(pretrain_weights=weights)
```

### Run Inference

```python
detections = model.predict("image.jpg", threshold=0.25)
```
---

## Performance

Evaluated on the RDD2022 Road Damage **test** split, using DetectionBench's standard evaluation pipeline (`detectionbench-evaluate`).

| Metric     | Score (%)       |
| ---------- | --------------- |
| mAP@50     | 64.71     |
| mAP@50-95  | 35.73   |
| Precision  | 65.69 |
| Recall     | 59.41    |
| F1 Score   | 62.39        |
| Parameters | 32.1M    |
| FLOPs      | N/A (not published upstream)     |

---

## RDD2022 Road Damage Model Zoo

Every model DetectionBench has trained and evaluated on RDD2022 Road Damage so far, for full transparency -- see [DetectionBench](https://github.com/dronefreak/DetectionBench) for the smaller, curated comparison set used on the project README.

| Model                | mAP@50        | mAP@50-95       | Precision         | Recall         |
| --------------------- | ------------- | --------------- | ----------------- | -------------- |
| RF-DETR Medium | 65.08 | 36.02 | 71.18 | 55.98 |
| **RF-DETR Small** | **64.71** | **35.73** | **65.69** | **59.41** |
| YOLOv8m | 62.03 | 34.08 | 65.61 | 57.42 |
| YOLOv8s | 61.45 | 33.53 | 64.55 | 57.18 |
| YOLO26s | 61.27 | 33.3 | 64.42 | 57.13 |
| YOLO26m | 61.24 | 33.38 | 63.7 | 57.27 |
| RF-DETR Nano | 60.85 | 33.22 | 65.49 | 54.3 |
| YOLOv8n | 58.8 | 32.05 | 62.03 | 56.08 |
| YOLO11x | 51.05 | 26.54 | 56.64 | 49.54 |
---

## Per-Class Performance

| Class                      | mAP@50          | mAP@50-95         |
| -------------------------- | --------------- | ----------------- |
| longitudinal_crack       | 58.38 | 30.83 |
| transverse_crack       | 58.96 | 29.61 |
| alligator_crack       | 66.66 | 35.23 |
| pothole       | 74.86 | 47.24 |

This model was evaluated with [Supervision](https://github.com/roboflow/supervision)'s detection metrics, which report mAP/Precision/Recall directly but don't produce a confusion-matrix plot the way Ultralytics' validator does.

---

## Dataset

This model was trained on **RDD2022 Road Damage**. For the full dataset description, provenance, license, and citation, see the dataset card:

https://huggingface.co/datasets/dronefreak/RDD2022

### Classes

* longitudinal_crack
* transverse_crack
* alligator_crack
* pothole
---

## Training Configuration

| Setting          | Value                           |
| ---------------- | -------------------------------- |
| Dataset          | RDD2022 Road Damage       |
| Framework        | RF-DETR                  |
| Training Toolkit | DetectionBench                   |
| Epochs (configured max) | 50 |
| Epochs (actually trained) | 30 |
| Early Stopping Patience | 10 |
| Batch Size | 6 |
| Resolution | 512 |
| Optimizer | adamw |
| Learning Rate | 0.0001 |
| Seed | 42 |
---

## Repository Contents

```text
checkpoint_best_total.pth
metrics.csv
config.json
rdd2022_rfdetr-small_showcase.jpg
README.md
```

---

## Related Resources

* [RDD2022 Road Damage dataset card](https://huggingface.co/datasets/dronefreak/RDD2022) on Hugging Face
* [DetectionBench](https://github.com/dronefreak/DetectionBench) -- reproducible benchmarks for modern object detectors on real-world datasets
* [RDD2022 paper preprint (arXiv:2209.08538)](https://arxiv.org/abs/2209.08538)
* [RDD2022 project repository (official data source)](https://github.com/sekilab/RoadDamageDetector)

---

## Training Framework

This model was trained using [DetectionBench](https://github.com/dronefreak/DetectionBench), an open-source framework for benchmarking object detectors across multiple real-world datasets with a common pipeline.

Features include:

* A dataset-adapter registry for converting real-world datasets into a canonical format
* Identical training/evaluation recipes across model families (Ultralytics YOLO/RT-DETR, RF-DETR)
* Hardware profiling (latency, FPS, VRAM, parameters, FLOPs)
* One-command reproducibility via versioned Hydra configs

If you find this model useful, please consider starring the repository.

---

## Known Limitations

* Not comparable to the official CRDDC2022 leaderboard: the challenge test set has no public labels, so the `test` split here is a held-out 15% slice (70/15/15 split) of the publicly-labelled images, merged across countries -- scores are only comparable between the models listed in this card's Model Zoo.
* Class imbalance: `longitudinal_crack` (44.0%) is the most common class, while `pothole` (18.1%) and `alligator_crack` (17.9%) are the rarest of the four -- per-class accuracy differs noticeably between them.
* Four-class taxonomy only: the source data's 5th "other" bucket (block cracks, road repairs and country-specific codes, ~6.5k boxes) was dropped to match the four damage types the CRDDC2022 challenge scores, so those damage types are not detected.
* Sparse, thin targets: about a third of images contain no in-taxonomy damage (clean-road frames), with 1.5 boxes per image on average, and cracks are thin structures that are easily lost when large frames (some over 4000 pixels wide) are downscaled to the model's input size.
* Uneven country and imaging-setup mix: the images come from six countries and several capture setups (smartphone, dashboard camera, drone) in very different proportions, so performance can vary substantially by country and generalization to unseen regions or damage conventions is untested.
* Share-alike data: the RDD2022 images are CC BY-SA 4.0 -- see the Dataset section above for attribution and the dataset card for the full terms.
---

## Citation

If you use this model in your research, please consider citing the dataset and the model architecture:

```
@article{arya2022rdd2022,
  title = {RDD2022: A multi-national image dataset for automatic Road Damage Detection},
  author = {Arya, Deeksha and Maeda, Hiroya and Ghosh, Sanjay Kumar and Toshniwal, Durga and Sekimoto, Yoshihide},
  journal = {arXiv preprint arXiv:2209.08538},
  year = {2022}
}
```

```bibtex
@inproceedings{robinson2026rfdetr,
  title     = {RF-DETR: Real-Time Detection Transformer},
  author    = {Robinson, Isaac and Robicheaux, Peter and Popov, Matvei and Ramanan, Deva and Peri, Neehar},
  booktitle = {International Conference on Learning Representations (ICLR)},
  year      = {2026},
  url       = {https://arxiv.org/abs/2511.09554}
}

@article{oquab2023dinov2,
  title={DINOv2: Learning Robust Visual Features without Supervision},
  author={Oquab, Maxime and Darcet, Timoth{\'e}e and Moutakanni, Theo and Vo, Huy and Szafraniec, Marc and Khalidov, Vasil and Fernandez, Pierre and Haziza, Daniel and Massa, Francisco and El-Nouby, Alaaeldin and others},
  journal={arXiv preprint arXiv:2304.07193},
  year={2023}
}
```