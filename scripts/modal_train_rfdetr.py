#!/usr/bin/env python3
"""Run scripts/train_rfdetr.py on a Modal GPU instead of a RunPod pod.

Modal Functions scale to zero automatically when done, so there's no "remember to stop
the pod" step the way RunPod pods needed.

One-time dataset upload (only needed again if data/datasets/model_b_aerial changes):
  modal volume create cityvision-rfdetr-dataset
  modal volume put cityvision-rfdetr-dataset data/datasets/model_b_aerial /

Smoke test (confirms image/volumes/GPU work before spending real GPU-hours):
  modal run scripts/modal_train_rfdetr.py --epochs 2 --name smoke

Full run:
  modal run scripts/modal_train_rfdetr.py --epochs 60 --name v3

Pull the result back locally:
  modal volume get cityvision-rfdetr-output v3/export models/rfdetr/ --force
"""

from __future__ import annotations

from pathlib import Path

import modal

ROOT = Path(__file__).resolve().parents[1]

app = modal.App("cityvision-rfdetr-train")

# Pinned to exactly what .venv-rfdetr has locally (see scripts/eval_aerial.py's module
# docstring for why rfdetr/torch/torchvision live in their own venv, separate from the
# main .venv's ultralytics/torch pins).
image = (
    modal.Image.from_registry("nvidia/cuda:12.4.0-devel-ubuntu22.04", add_python="3.11")
    .pip_install(
        # [train] extra pulls in what RFDETR.train() actually needs (peft, faster-coco-eval,
        # scipy, rf100vl, roboflow, pycocotools, torchmetrics[detection], pytorch_lightning) —
        # pinning the bare package alone is not enough, its training path 404s on import.
        "rfdetr[train]==1.9.3",
        "torch==2.13.0",
        "torchvision==0.28.0",
        "accelerate==1.14.0",
        "supervision==0.30.0",
        "pyyaml",
    )
    .add_local_dir(ROOT / "src" / "cityvision", "/root/src/cityvision")
    .add_local_file(ROOT / "scripts" / "train_rfdetr.py", "/root/scripts/train_rfdetr.py")
    .add_local_file(
        ROOT / "configs" / "model_b_aerial.data.yaml", "/root/configs/model_b_aerial.data.yaml"
    )
    .add_local_file(
        ROOT / "configs" / "model_b_uavpdd_only.data.yaml",
        "/root/configs/model_b_uavpdd_only.data.yaml",
    )
)

# Separate from the output volume so re-running training never re-uploads the ~2000-image
# dataset, and multiple training runs' outputs don't collide with each other or the dataset.
dataset_volume = modal.Volume.from_name("cityvision-rfdetr-dataset", create_if_missing=True)
# UAV-PDD2023 (public, own-footage-free comparison run) — separate volume/mount so it
# never collides with or gets swept up by our own-footage dataset uploads.
uavpdd_volume = modal.Volume.from_name("cityvision-uavpdd-dataset", create_if_missing=True)
output_volume = modal.Volume.from_name("cityvision-rfdetr-output", create_if_missing=True)

DATASET_MOUNT = "/root/data/datasets/model_b_aerial"
UAVPDD_MOUNT = "/root/data/datasets/uav_pdd2023"
OUTPUT_MOUNT = "/root/runs/rfdetr"

_DATA_YAML = {
    "own": "/root/configs/model_b_aerial.data.yaml",
    "uavpdd": "/root/configs/model_b_uavpdd_only.data.yaml",
}


@app.function(
    image=image,
    gpu="L4",
    # Floor so the 4 dataloader workers (train_rfdetr.py --num-workers default) aren't
    # starved by Modal's default CPU allocation for a GPU function.
    cpu=4.0,
    volumes={
        DATASET_MOUNT: dataset_volume,
        UAVPDD_MOUNT: uavpdd_volume,
        OUTPUT_MOUNT: output_volume,
    },
    timeout=6 * 60 * 60,
)
def train(
    epochs: int = 60,
    resolution: int = 1280,
    base_weights: str = "rf-detr-medium.pth",
    variant: str = "ema",
    name: str = "run",
    resume: str = "",
    dataset: str = "own",
) -> str:
    import subprocess

    export_to = f"{OUTPUT_MOUNT}/{name}/export/rfdetr-{name}-{resolution}-{variant}.pth"
    argv = [
        "python",
        "/root/scripts/train_rfdetr.py",
        "--data",
        _DATA_YAML[dataset],
        "--epochs",
        str(epochs),
        "--resolution",
        str(resolution),
        "--base-weights",
        base_weights,
        "--variant",
        variant,
        "--project",
        OUTPUT_MOUNT,
        "--name",
        name,
        "--export-to",
        export_to,
    ]
    if resume:
        # Must be a last.ckpt under OUTPUT_MOUNT/<name>/ — same output_dir as the run that
        # wrote it, or callback/best-score state resumes into the wrong place (see
        # train_rfdetr.py's --resume help).
        argv += ["--resume", resume]
    subprocess.run(argv, check=True, cwd="/root")
    output_volume.commit()
    return export_to


@app.local_entrypoint()
def main(
    epochs: int = 60,
    resolution: int = 1280,
    base_weights: str = "rf-detr-medium.pth",
    variant: str = "ema",
    name: str = "run",
    resume: str = "",
    dataset: str = "own",
) -> None:
    export_to = train.remote(
        epochs=epochs,
        resolution=resolution,
        base_weights=base_weights,
        variant=variant,
        name=name,
        resume=resume,
        dataset=dataset,
    )
    print(f"Checkpoint on Modal volume 'cityvision-rfdetr-output' at: {export_to}")
    print(f"Pull it down with:\n  modal volume get cityvision-rfdetr-output {name}/export models/rfdetr/ --force")
