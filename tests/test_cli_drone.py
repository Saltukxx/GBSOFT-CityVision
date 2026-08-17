import numpy as np

from cityvision.cli import build_parser
from cityvision.config import DEFAULT_PROFILE
from cityvision.pipeline.annotate import draw_detections


def test_cli_drone_id_and_profile():
    args = build_parser().parse_args(
        [
            "run",
            "--source",
            "a.mp4",
            "--output",
            "out",
            "--drone-id",
            "DJI-99",
            "--profile",
            "nadir",
        ]
    )
    assert args.drone_id == "DJI-99"
    assert args.profile == "nadir"
    assert args.vehicle_id is None


def test_cli_profile_default_is_oblique_via_constant():
    args = build_parser().parse_args(["run", "--source", "a.mp4", "--output", "out"])
    assert args.profile is None
    assert DEFAULT_PROFILE == "oblique"
    assert (args.profile or DEFAULT_PROFILE) == "oblique"


def test_hud_omits_count_line_when_traffic_disabled():
    frame = np.zeros((80, 160, 3), dtype=np.uint8)
    out = draw_detections(frame, [], line_y=None, hud_lines=["DJI-01/AERIAL"])
    with_line = draw_detections(frame, [], line_y=40.0, hud_lines=["DJI-01/AERIAL"])
    assert with_line[40].sum() > out[40].sum()


def test_hud_draws_count_line_when_requested():
    frame = np.zeros((80, 160, 3), dtype=np.uint8)
    out = draw_detections(frame, [], line_y=40.0)
    assert out[40].sum() > 0
