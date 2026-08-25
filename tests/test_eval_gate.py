from cityvision.pipeline.eval_gate import (
    MIN_SUPPORT,
    THRESHOLDS,
    evaluate_gate,
    gate_verdict,
)

FULL_SUPPORT = {"manhole": MIN_SUPPORT, "pothole": MIN_SUPPORT, "road_crack": MIN_SUPPORT}


def _metrics(manhole_r: float, pothole_ap: float, crack_ap: float) -> dict:
    return {
        "manhole": {"recall": manhole_r, "map50": 0.9},
        "pothole": {"recall": 0.5, "map50": pothole_ap},
        "road_crack": {"recall": 0.5, "map50": crack_ap},
    }


def test_all_thresholds_met_passes():
    checks = evaluate_gate(_metrics(0.9, 0.6, 0.4), FULL_SUPPORT)
    assert {row["status"] for row in checks.values()} == {"pass"}
    assert gate_verdict(checks) == "pass"


def test_below_threshold_fails():
    checks = evaluate_gate(_metrics(0.9, 0.6, 0.2), FULL_SUPPORT)
    assert checks["road_crack_map50"]["status"] == "fail"
    assert gate_verdict(checks) == "fail"


def test_class_absent_from_split_is_not_a_failure():
    support = {"manhole": MIN_SUPPORT, "pothole": 0, "road_crack": 0}
    checks = evaluate_gate({"manhole": {"recall": 0.96, "map50": 0.99}}, support)
    assert checks["manhole_recall"]["status"] == "pass"
    assert checks["pothole_map50"]["status"] == "n/a"
    assert checks["road_crack_map50"]["status"] == "n/a"
    assert gate_verdict(checks) == "n/a"


def test_low_support_is_not_a_failure():
    support = {"manhole": MIN_SUPPORT, "pothole": 3, "road_crack": MIN_SUPPORT - 1}
    checks = evaluate_gate(_metrics(0.9, 0.0, 0.0), support)
    assert checks["pothole_map50"]["status"] == "n/a"
    assert checks["road_crack_map50"]["status"] == "n/a"
    assert checks["manhole_recall"]["status"] == "pass"
    assert gate_verdict(checks) == "n/a"


def test_real_failure_outranks_unmeasurable():
    support = {"manhole": MIN_SUPPORT, "pothole": 5, "road_crack": 0}
    checks = evaluate_gate(_metrics(0.5, 0.1, 0.0), support)
    assert checks["manhole_recall"]["status"] == "fail"
    assert checks["pothole_map50"]["status"] == "n/a"
    assert gate_verdict(checks) == "fail"


def test_exact_threshold_counts_as_pass():
    checks = evaluate_gate(
        _metrics(
            THRESHOLDS["manhole_recall"],
            THRESHOLDS["pothole_map50"],
            THRESHOLDS["road_crack_map50"],
        ),
        FULL_SUPPORT,
    )
    assert gate_verdict(checks) == "pass"


def test_missing_class_entry_is_treated_as_zero():
    checks = evaluate_gate({}, FULL_SUPPORT)
    assert checks["manhole_recall"]["value"] == 0.0
    assert gate_verdict(checks) == "fail"


DISTRESS_SUPPORT = {
    "pothole": MIN_SUPPORT,
    "road_distress": MIN_SUPPORT,
    "manhole": MIN_SUPPORT,
}


def test_distress_taxonomy_skips_road_crack_check():
    """The 3-class merge experiment has no road_crack; grading it would pin every
    verdict to n/a and make the experiment undecidable."""
    checks = evaluate_gate(
        {
            "pothole": {"map50": 0.6},
            "road_distress": {"map50": 0.4},
            "manhole": {"recall": 0.9},
        },
        DISTRESS_SUPPORT,
    )
    assert "road_crack_map50" not in checks
    assert checks["road_distress_map50"]["status"] == "pass"
    assert gate_verdict(checks) == "pass"


def test_aerial_taxonomy_skips_road_distress_check():
    checks = evaluate_gate(_metrics(0.9, 0.6, 0.4), FULL_SUPPORT)
    assert "road_distress_map50" not in checks
    assert gate_verdict(checks) == "pass"


def test_merge_gain_below_bar_fails():
    """A modest lift over v3 (crack 0.000 / damage 0.127) is the mechanical effect of
    collapsing two classes, not evidence that the label definition was the problem."""
    checks = evaluate_gate(
        {"road_distress": {"map50": 0.22}, "manhole": {"recall": 0.9}, "pothole": {"map50": 0.6}},
        DISTRESS_SUPPORT,
    )
    assert checks["road_distress_map50"]["status"] == "fail"
    assert gate_verdict(checks) == "fail"


def test_low_distress_support_is_unmeasurable():
    support = dict(DISTRESS_SUPPORT, road_distress=MIN_SUPPORT - 1)
    checks = evaluate_gate(
        {"road_distress": {"map50": 0.9}, "manhole": {"recall": 0.9}, "pothole": {"map50": 0.6}},
        support,
    )
    assert checks["road_distress_map50"]["status"] == "n/a"
    assert gate_verdict(checks) == "n/a"


def test_empty_support_is_not_a_pass():
    """A result JSON written before `support` was recorded must not grade as pass."""
    checks = evaluate_gate({"manhole": {"recall": 0.99}}, {})
    assert checks == {}
    assert gate_verdict(checks) == "n/a"
