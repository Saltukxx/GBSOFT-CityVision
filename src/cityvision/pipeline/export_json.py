from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, TextIO

from cityvision.pipeline.types import Detection, RunMeta


class JsonlWriter:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh: Optional[TextIO] = None

    def open(self) -> None:
        self._fh = self.path.open("w", encoding="utf-8")

    def write_meta(self, meta: RunMeta) -> None:
        self._write({"type": "meta", **meta.to_dict()})

    def write_detection(self, det: Detection) -> None:
        self._write({"type": "detection", **det.to_dict()})

    def write_summary(self, summary: Dict[str, Any]) -> None:
        self._write({"type": "summary", **summary})

    def _write(self, obj: Dict[str, Any]) -> None:
        if self._fh is None:
            raise RuntimeError("JsonlWriter is not open")
        self._fh.write(json.dumps(obj, ensure_ascii=False) + "\n")

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None

    def __enter__(self) -> "JsonlWriter":
        self.open()
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
