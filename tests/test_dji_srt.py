from pathlib import Path

from cityvision.geo.dji_srt import parse_dji_srt
from cityvision.geo.gps import discover_gps_sidecar, load_gps_sidecar

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "dji_sample.srt"


def test_parse_dji_srt_fixture():
    fixes = parse_dji_srt(FIXTURE)
    assert len(fixes) == 3
    assert fixes[0].timestamp_ms == 0.0
    assert fixes[0].lat == 41.0083
    assert fixes[0].lon == 28.9784
    assert fixes[0].heading is None
    assert fixes[1].timestamp_ms == 1000.0
    assert fixes[1].lat == 41.0084
    assert fixes[2].timestamp_ms == 2000.0
    assert abs(fixes[2].lon - 28.9786) < 1e-9


def test_load_gps_sidecar_srt():
    fixes = load_gps_sidecar(FIXTURE)
    assert len(fixes) == 3


def test_discover_gps_sidecar(tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"mp4")
    srt = tmp_path / "clip.srt"
    srt.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    found = discover_gps_sidecar(video)
    assert found is not None
    assert found.samefile(srt)
    assert discover_gps_sidecar(tmp_path / "missing.mp4") is None
