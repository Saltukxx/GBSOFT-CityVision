from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any

import yaml

log = logging.getLogger(__name__)

_TAL_PATCHED = False


def materialize_data_yaml(src: Path, default_root: Path | None = None) -> Path:
    data: dict[str, Any] = yaml.safe_load(src.read_text(encoding="utf-8")) or {}
    path_val = data.get("path")
    if path_val:
        p = Path(path_val)
        if not p.is_absolute():
            # resolve relative to repo root (parent of configs/)
            repo = src.resolve().parents[1] if src.parent.name == "configs" else Path.cwd()
            p = (repo / p).resolve()
        data["path"] = str(p)
    elif default_root is not None:
        data["path"] = str(default_root.resolve())

    tmp = Path(tempfile.mkdtemp(prefix="cityvision-data-")) / "data.yaml"
    tmp.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return tmp


def count_dataset_images(data_yaml: Path) -> tuple[int, int, Path]:
    data = yaml.safe_load(data_yaml.read_text(encoding="utf-8")) or {}
    path_val = data.get("path")
    if not path_val:
        raise ValueError("data yaml missing path")
    root = Path(path_val)
    if not root.is_absolute():
        repo = data_yaml.resolve().parents[1] if data_yaml.parent.name == "configs" else Path.cwd()
        root = (repo / root).resolve()
    train_dir = root / "images" / "train"
    exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    n_img = len([p for p in train_dir.glob("*") if p.suffix.lower() in exts]) if train_dir.exists() else 0
    label_dir = root / "labels" / "train"
    n_lbl = len(list(label_dir.glob("*.txt"))) if label_dir.exists() else 0
    return n_img, n_lbl, root


def patch_tal_for_mps() -> bool:
    """
    Run the task-aligned assigner on CPU while the rest of training stays on MPS.

    PyTorch's MPS backend miscounts boolean-mask indexing on expanded, non-contiguous
    tensors, so `TaskAlignedAssigner.get_box_metrics` can select a different number of
    elements on each side of a masked write and abort training mid-run:

        RuntimeError: shape mismatch: value tensor of shape [6772] cannot be broadcast
        to indexing result of shape [6480]

    It is non-deterministic — it depends on how many boxes land in a batch — so it can
    surface hours in (v3 died at epoch 25/100). Ultralytics 8.4 already falls back to
    CPU here, but only for out-of-memory errors, so a shape mismatch still propagates.

    Installing this is a no-op on CPU and CUDA: the wrapper only diverts when the
    incoming tensors are actually on MPS. Assignment is a small slice of each step, so
    the extra host transfer costs far less than a crashed run.
    """
    global _TAL_PATCHED
    if _TAL_PATCHED:
        return False
    from ultralytics.utils.tal import TaskAlignedAssigner

    original = TaskAlignedAssigner.forward

    def forward(self, pd_scores, pd_bboxes, anc_points, gt_labels, gt_bboxes, mask_gt):
        if gt_bboxes.device.type != "mps":
            return original(self, pd_scores, pd_bboxes, anc_points, gt_labels, gt_bboxes, mask_gt)
        device = gt_bboxes.device
        on_cpu = original(
            self,
            pd_scores.cpu(),
            pd_bboxes.cpu(),
            anc_points.cpu(),
            gt_labels.cpu(),
            gt_bboxes.cpu(),
            mask_gt.cpu(),
        )
        return tuple(t.to(device) for t in on_cpu)

    TaskAlignedAssigner.forward = forward
    _TAL_PATCHED = True
    log.info("TaskAlignedAssigner will run on CPU when training on MPS")
    return True
