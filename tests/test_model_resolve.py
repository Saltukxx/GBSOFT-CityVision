from pathlib import Path

from cityvision.config import ROOT
from cityvision.pipeline.model_resolve import resolve_model_b_paths


def test_resolve_skips_missing_and_finds_road(tmp_path, monkeypatch):
    models = ROOT / "models"
    road = models / "infra-b-road.pt"
    # road may already exist from prior training
    cfg = {
        "model_b_list": [
            "models/infra-b-road.pt",
            "models/infra-b-waste.pt",
            "models/does-not-exist.pt",
        ],
        "auto_discover_model_b": False,
        "model_b_fallbacks": [],
    }
    paths = resolve_model_b_paths(cfg)
    names = [p.name for p in paths]
    assert "does-not-exist.pt" not in names
    if road.exists():
        assert "infra-b-road.pt" in names
    assert "infra-b-waste.pt" not in names or (models / "infra-b-waste.pt").exists()


def test_fallback_used_until_export_exists():
    cfg = {
        "model_b_list": ["models/infra-b-waste.pt"],
        "auto_discover_model_b": False,
        "model_b_fallbacks": ["runs/model_b/train_waste_overflow/weights/best.pt"],
    }
    paths = resolve_model_b_paths(cfg)
    names = [p.name for p in paths]
    waste_export = ROOT / "models" / "infra-b-waste.pt"
    waste_best = ROOT / "runs" / "model_b" / "train_waste_overflow" / "weights" / "best.pt"
    if waste_export.exists():
        assert "infra-b-waste.pt" in names
        assert "best.pt" not in names
    elif waste_best.exists():
        assert "best.pt" in names
