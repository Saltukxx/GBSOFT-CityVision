"""Unit tests for Memphis thin uploader outbox (no DB)."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.error import URLError

from cityvision.edge.agent.uploader import drain_outbox, upload_with_outbox


def test_outbox_queues_on_failure(tmp_path: Path, monkeypatch):
    video = tmp_path / "a.mp4"
    video.write_bytes(b"fake")
    gps = tmp_path / "gps.jsonl"
    gps.write_text('{"timestamp_ms":0,"lat":1,"lon":2}\n', encoding="utf-8")
    outbox = tmp_path / "outbox"

    def boom(**kwargs):
        raise URLError("down")

    monkeypatch.setattr("cityvision.edge.agent.uploader.upload_video_file", boom)

    try:
        upload_with_outbox(
            api_base="http://127.0.0.1:9",
            token="t",
            video_path=video,
            gps_path=gps,
            outbox_dir=outbox,
            max_retries=2,
            backoff_s=0.01,
            city_id="erzurum",
        )
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "queued" in str(exc)

    kids = list(outbox.iterdir())
    assert len(kids) == 1
    meta = json.loads((kids[0] / "meta.json").read_text(encoding="utf-8"))
    assert meta["video"] == "a.mp4"
    assert meta["kwargs"]["city_id"] == "erzurum"


def test_drain_outbox_success(tmp_path: Path, monkeypatch):
    dest = tmp_path / "outbox" / "pkg1"
    dest.mkdir(parents=True)
    (dest / "a.mp4").write_bytes(b"v")
    (dest / "meta.json").write_text(
        json.dumps({"video": "a.mp4", "gps": None, "kwargs": {}}),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "cityvision.edge.agent.uploader.upload_video_file",
        lambda **kwargs: {"ok": True, "upload_id": "x"},
    )
    results = drain_outbox(api_base="http://x", token="t", outbox_dir=tmp_path / "outbox")
    assert results and results[0]["ok"]
    assert not dest.exists()
