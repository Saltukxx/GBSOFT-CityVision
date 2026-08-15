from __future__ import annotations

from typing import Dict


def composite_confidence(
    ai_conf: float,
    observations: int,
    has_gps: bool,
    multi_vehicle: bool,
    repeat_bonus: float = 0.10,
    multi_vehicle_bonus: float = 0.10,
    gps_bonus: float = 0.05,
) -> float:
    score = float(ai_conf)
    if observations >= 2:
        score += repeat_bonus
    if observations >= 3:
        score += repeat_bonus * 0.5
    if multi_vehicle:
        score += multi_vehicle_bonus
    if has_gps:
        score += gps_bonus
    return max(0.0, min(1.0, score))


def confidence_band(score: float, bands: Dict[str, float]) -> str:
    """
    bands keys: discard, review, probable  (thresholds)
    < discard → discard
    discard–review → manual_review
    review–probable → probable
    >= probable → high
    """
    discard = float(bands.get("discard", 0.70))
    review = float(bands.get("review", 0.85))
    probable = float(bands.get("probable", 0.95))
    if score < discard:
        return "discard"
    if score < review:
        return "manual_review"
    if score < probable:
        return "probable"
    return "high"


def severity_from_class(class_name: str, confidence: float) -> str:
    if class_name in {"pothole", "road_damage"} and confidence >= 0.9:
        return "high"
    if class_name in {"overflowing_container", "street_waste", "pothole", "road_crack"}:
        return "medium"
    if class_name == "potential_bus_stop_obstruction":
        return "medium"
    return "low"
