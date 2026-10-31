"""Anonymising evidence: people and plates blurred, nothing shown un-anonymised."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from cityvision.privacy.anonymize import Anonymizer, Region


def _frame(w=800, h=600):
    rng = np.random.default_rng(0)
    return rng.integers(0, 255, (h, w, 3), dtype=np.uint8)


def _changed(a, b, box):
    x1, y1, x2, y2 = box
    return not np.array_equal(a[y1:y2, x1:x2], b[y1:y2, x1:x2])


def test_people_blurred_rest_untouched():
    img = _frame()
    anon = Anonymizer(detector=lambda f: [("person", (100, 100, 160, 260)), ("dog", (500, 300, 560, 360))])
    out, regs = anon.anonymize(img)
    assert [r.kind for r in regs] == ["person"]
    assert _changed(img, out, (100, 100, 160, 260))
    assert np.array_equal(img[400:, 500:], out[400:, 500:])  # far from the person: identical


def test_close_vehicle_without_plate_is_blurred_whole_far_one_is_not():
    img = _frame()
    big, small = (300, 200, 500, 400), (10, 10, 30, 22)
    anon = Anonymizer(detector=lambda f: [("car", big), ("car", small)])
    anon._plates = lambda crop: []  # no plate found
    out, regs = anon.anonymize(img)
    assert [r.kind for r in regs] == ["vehicle"]
    assert _changed(img, out, big) and not _changed(img, out, (10, 10, 30, 22))


def test_found_plate_blurs_only_the_plate_and_full_mode_blurs_vehicles():
    img = _frame()
    car = (300, 200, 500, 400)
    anon = Anonymizer(detector=lambda f: [("car", car)])
    anon._plates = lambda crop: [(80, 150, 130, 165)]
    out, regs = anon.anonymize(img)
    assert [r.kind for r in regs] == ["plate"]
    assert _changed(img, out, (380, 350, 430, 365)) and not _changed(img, out, (300, 200, 340, 240))
    full = Anonymizer(detector=lambda f: [("car", car)], vehicles="full")
    assert [r.kind for r in full.anonymize(img)[1]] == ["vehicle"]
    off = Anonymizer(detector=lambda f: [("car", car)], vehicles="off")
    assert off.anonymize(img)[1] == []


def test_detector_failure_fails_closed():
    def boom(_):
        raise RuntimeError("model missing")

    img = _frame()
    out, regs = Anonymizer(detector=boom).anonymize(img)
    assert regs[0].kind == "frame" and _changed(img, out, (0, 0, 800, 600))


def test_blur_removes_fine_detail():
    # Fine detail (what makes a face or plate readable) is what must go.
    img = _frame()
    out = Anonymizer.blur(img, [Region((100, 100, 160, 260), "person")])
    sharp = lambda a: cv2.Laplacian(cv2.cvtColor(a[100:260, 100:160], cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()  # noqa: E731
    assert sharp(out) < sharp(img) * 0.05


def test_clip_stream_carries_regions_between_detections():
    calls = []

    def det(f):
        calls.append(1)
        return [("person", (100, 100, 160, 260))]

    stream = Anonymizer(detector=det).stream(every=3)
    frames = [_frame() for _ in range(7)]
    outs = [stream(f) for f in frames]
    assert len(calls) == 3  # frames 0, 3, 6
    assert all(_changed(f, o, (100, 100, 160, 260)) for f, o in zip(frames, outs))


def test_evidence_files_are_anonymised(tmp_path: Path):
    from cityvision.events.evidence import write_evidence_packs
    from cityvision.pipeline.types import MunicipalEvent

    video = tmp_path / "v.mp4"
    wr = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"mp4v"), 10, (320, 240))
    for _ in range(20):
        wr.write(np.full((240, 320, 3), 200, dtype=np.uint8))
    wr.release()
    ev = MunicipalEvent(
        event_id="E1", type="pothole", lat=None, lon=None, severity="low", confidence=0.9,
        confidence_band="probable", first_seen_ms=0, last_seen_ms=1, observations=1,
        status="under_review", model_version="t", sample_frame=10, sample_bbox=[150, 100, 200, 150],
    )
    marker = (20, 20, 80, 120)

    def det(f):
        return [("person", marker)]

    # Paint a high-contrast "person" so blurring is measurable.
    out = write_evidence_packs(video, [ev], tmp_path, fps=10, seconds_before=0.5, seconds_after=0.5,
                               anonymizer=Anonymizer(detector=det))
    assert out[0].privacy_blurred == 1 and out[0].privacy_method
    for name in ("event.jpg", "frame_clean.jpg"):
        assert (tmp_path / "evidence" / "E1" / name).exists()
    assert (tmp_path / "evidence" / "E1" / "event.mp4").exists()


@pytest.mark.parametrize("mode", ["plates", "full", "off"])
def test_config_builds_anonymizer(mode):
    from cityvision.privacy.anonymize import from_config

    a = from_config({"privacy": {"vehicles": mode}})
    assert a is not None and a.vehicles == mode
    assert from_config({"privacy": {"enabled": False}}) is None


def test_tiles_cover_frame_and_map_back():
    from cityvision.privacy.anonymize import _tiles

    img = _frame(1000, 600)
    pieces = list(_tiles(img, 2))
    assert len(pieces) == 4
    covered = np.zeros(img.shape[:2], bool)
    for (x, y), v in pieces:
        assert np.array_equal(v, img[y : y + v.shape[0], x : x + v.shape[1]])
        covered[y : y + v.shape[0], x : x + v.shape[1]] = True
    assert covered.all()


def test_visdrone_names_are_understood():
    img = _frame()
    anon = Anonymizer(detector=lambda f: [("pedestrian", (10, 10, 40, 80)), ("van", (300, 200, 500, 400))])
    anon._plates = lambda crop: []
    assert sorted(r.kind for r in anon.anonymize(img)[1]) == ["person", "vehicle"]
