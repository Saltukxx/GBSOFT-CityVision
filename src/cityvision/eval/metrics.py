from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List, Sequence, Tuple


def prf(tp: int, fp: int, fn: int) -> Dict[str, float]:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


def false_events_per_km(false_positives: int, route_km: float) -> float:
    if route_km <= 0:
        return 0.0
    return round(false_positives / route_km, 4)


def match_centers(
    preds: Sequence[Tuple[float, float]],
    gts: Sequence[Tuple[float, float]],
    radius: float,
) -> Tuple[int, int, int]:
    """Greedy match in 2D (GPS meters approximated by caller, or pixel space)."""
    used = set()
    tp = 0
    for p in preds:
        best_i = None
        best_d = None
        for i, g in enumerate(gts):
            if i in used:
                continue
            d = ((p[0] - g[0]) ** 2 + (p[1] - g[1]) ** 2) ** 0.5
            if d <= radius and (best_d is None or d < best_d):
                best_d = d
                best_i = i
        if best_i is not None:
            used.add(best_i)
            tp += 1
    fp = len(preds) - tp
    fn = len(gts) - tp
    return tp, fp, fn


def classwise_counts(items: Iterable[str]) -> Dict[str, int]:
    out: Dict[str, int] = defaultdict(int)
    for c in items:
        out[c] += 1
    return dict(out)
