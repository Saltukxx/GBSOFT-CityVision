from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import yaml


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
