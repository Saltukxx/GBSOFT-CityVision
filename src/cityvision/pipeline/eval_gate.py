"""Acceptance thresholds for aerial Model B.

A class with fewer than MIN_SUPPORT ground-truth boxes in the evaluated split
must not be read as a failure — n=3 can swing mAP from 0.33 to 0.66.

Checks are taxonomy-aware. `support` is keyed on the class names of the data
yaml under evaluation (see `count_instances`), so a check whose class is absent
from that taxonomy is skipped instead of graded: the 3-class distress
experiment has no `road_crack`, and grading it would pin every verdict to `n/a`.
A class that *is* in the taxonomy but under-represented still reports `n/a`.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping

PASS = "pass"
FAIL = "fail"
NOT_MEASURED = "n/a"

MIN_SUPPORT = 50

THRESHOLDS: Dict[str, float] = {
    "manhole_recall": 0.85,
    "pothole_map50": 0.50,
    "road_crack_map50": 0.30,
    # Merge experiment (configs/model_b_distress.data.yaml): road_crack + road_damage.
    # Collapsing two classes lifts per-class mAP mechanically — the confusion between
    # them leaves the metric and the instance count doubles — so the bar sits above
    # what either class scored apart (v3 val: crack 0.000, damage 0.127). Below this,
    # a gain is not evidence that the label definition was the problem.
    "road_distress_map50": 0.35,
}

CHECKS: Dict[str, tuple[str, str]] = {
    "manhole_recall": ("manhole", "recall"),
    "pothole_map50": ("pothole", "map50"),
    "road_crack_map50": ("road_crack", "map50"),
    "road_distress_map50": ("road_distress", "map50"),
}


def evaluate_gate(
    per_class: Mapping[str, Mapping[str, float]],
    support: Mapping[str, int],
) -> Dict[str, Dict[str, Any]]:
    """Grade per-class metrics against THRESHOLDS, flagging unmeasurable classes."""
    out: Dict[str, Dict[str, Any]] = {}
    for key, (class_name, metric) in CHECKS.items():
        if class_name not in support:
            # Not part of this dataset's taxonomy — the check does not apply.
            continue
        instances = int(support.get(class_name, 0))
        value = float(per_class.get(class_name, {}).get(metric, 0.0))
        if instances < MIN_SUPPORT:
            status = NOT_MEASURED
        elif value >= THRESHOLDS[key]:
            status = PASS
        else:
            status = FAIL
        out[key] = {
            "value": round(value, 4),
            "threshold": THRESHOLDS[key],
            "instances": instances,
            "status": status,
        }
    return out


def gate_verdict(checks: Mapping[str, Mapping[str, Any]]) -> str:
    """`fail` if any measurable check failed, `n/a` if something is unmeasurable."""
    if not checks:
        # No applicable check ran (e.g. a result JSON written before support was
        # recorded). Silence is not a pass.
        return NOT_MEASURED
    statuses = {row["status"] for row in checks.values()}
    if FAIL in statuses:
        return FAIL
    if NOT_MEASURED in statuses:
        return NOT_MEASURED
    return PASS


def check_split_manifest(
    current: str, baseline: Mapping[str, Any] | None
) -> str | None:
    """None if comparable. Warning text if the baseline has no hash. ValueError if they differ."""
    if not baseline:
        return None
    prev = baseline.get("split_manifest")
    if not prev:
        return "baseline split_manifest yok, karşılaştırma yine de yapılıyor"
    if prev != current:
        raise ValueError(
            f"split_manifest uyuşmuyor: baseline={prev} current={current}. "
            "Farklı export; --baseline ile kıyaslanamaz."
        )
    return None
