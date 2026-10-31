"""Blur people and licence plates in evidence images and clips.

Evidence is what reviewers, crews and reports see, so it is anonymised when it
is written. People are blurred whole. Vehicles get their plate blurred when a
plate is found; a vehicle close enough for its plate to be legible but with no
plate found is blurred whole — when unsure, privacy wins. Cities with stricter
rules can blur every vehicle (vehicles="full").

The blur is pixelation followed by a Gaussian blur, which can't be reversed.
The original video is untouched; it lives under access control and the city's
retention period (see privacy.retention).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Literal, Optional, Sequence, Tuple

import cv2
import numpy as np

log = logging.getLogger(__name__)

METHOD = "person-vehicle+plate-cascade/v1"
# COCO names, plus VisDrone names so an aerial-trained detector drops straight in.
PERSON = {"person", "pedestrian", "people"}
VEHICLE = {"car", "bus", "truck", "motorcycle", "van", "motor", "tricycle", "awning-tricycle"}

Box = Tuple[int, int, int, int]
Detector = Callable[[np.ndarray], List[Tuple[str, Box]]]


@dataclass
class Region:
    box: Box
    kind: str  # "person" | "plate" | "vehicle"


@dataclass
class Anonymizer:
    model_path: str = "yolov8n.pt"
    conf: float = 0.2
    imgsz: int = 1920
    vehicles: Literal["plates", "full", "off"] = "plates"
    # Split large frames into tiles×tiles overlapping pieces: people and cars seen
    # from a drone are a few dozen pixels and vanish when a 4K frame is shrunk.
    tiles: int = 1
    # A vehicle covering more than this share of the frame is close enough for
    # its plate to be read; with no plate found it is blurred whole.
    legible_vehicle_ratio: float = 0.004
    detector: Optional[Detector] = None  # injectable for tests
    _model: Any = field(default=None, init=False, repr=False)
    _cascades: List[Any] = field(default_factory=list, init=False, repr=False)

    # ---------- detection ----------

    def _detect(self, frame: np.ndarray) -> List[Tuple[str, Box]]:
        if self.detector is not None:
            return self.detector(frame)
        if self._model is None:
            from ultralytics import YOLO

            self._model = YOLO(self.model_path)
        out: List[Tuple[str, Box]] = []
        for (ox, oy), piece in _tiles(frame, self.tiles):
            res = self._model.predict(piece, conf=self.conf, imgsz=self.imgsz, verbose=False)[0]
            for b in res.boxes:
                name = res.names[int(b.cls)]
                if name in PERSON or name in VEHICLE:
                    x1, y1, x2, y2 = (int(v) for v in b.xyxy[0].tolist())
                    out.append((name, (x1 + ox, y1 + oy, x2 + ox, y2 + oy)))
        return out

    def _plates(self, crop: np.ndarray) -> List[Box]:
        if not self._cascades:
            for name in ("haarcascade_russian_plate_number.xml", "haarcascade_license_plate_rus_16stages.xml"):
                c = cv2.CascadeClassifier(cv2.data.haarcascades + name)
                if not c.empty():
                    self._cascades.append(c)
        if crop.size == 0:
            return []
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        found: List[Box] = []
        for c in self._cascades:
            for x, y, w, h in c.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(16, 6)):
                if 1.8 <= w / max(h, 1) <= 6.5:  # plate-shaped only
                    found.append((int(x), int(y), int(x + w), int(y + h)))
        return found

    def regions(self, frame: np.ndarray) -> List[Region]:
        h, w = frame.shape[:2]
        out: List[Region] = []
        for name, (x1, y1, x2, y2) in self._detect(frame):
            if name in PERSON:
                out.append(Region(_grow((x1, y1, x2, y2), 0.15, w, h), "person"))
                continue
            if name not in VEHICLE or self.vehicles == "off":
                continue
            if self.vehicles == "full":
                out.append(Region(_grow((x1, y1, x2, y2), 0.05, w, h), "vehicle"))
                continue
            plates = self._plates(frame[max(0, y1) : y2, max(0, x1) : x2])
            if plates:
                out.extend(Region(_grow((x1 + a, y1 + b, x1 + c, y1 + d), 0.3, w, h), "plate") for a, b, c, d in plates)
            elif (x2 - x1) * (y2 - y1) / float(w * h) >= self.legible_vehicle_ratio:
                out.append(Region(_grow((x1, y1, x2, y2), 0.05, w, h), "vehicle"))
        return out

    # ---------- blurring ----------

    @staticmethod
    def blur(frame: np.ndarray, regions: Sequence[Region]) -> np.ndarray:
        out = frame.copy()
        for r in regions:
            x1, y1, x2, y2 = r.box
            patch = out[y1:y2, x1:x2]
            if patch.size == 0:
                continue
            ph, pw = patch.shape[:2]
            # Pixelate to ~8 blocks across, then soften the block edges.
            small = cv2.resize(patch, (max(1, pw // max(1, pw // 8)), max(1, ph // max(1, ph // 8))), interpolation=cv2.INTER_LINEAR)
            blocky = cv2.resize(small, (pw, ph), interpolation=cv2.INTER_NEAREST)
            k = max(3, (min(pw, ph) // 4) | 1)
            out[y1:y2, x1:x2] = cv2.GaussianBlur(blocky, (k, k), 0)
        return out

    def anonymize(self, frame: np.ndarray) -> Tuple[np.ndarray, List[Region]]:
        try:
            regs = self.regions(frame)
        except Exception:  # noqa: BLE001
            # Fail closed: if we can't check the image, it must not be shown as-is.
            log.exception("anonymiser failed; blurring the whole frame")
            h, w = frame.shape[:2]
            regs = [Region((0, 0, w, h), "frame")]
        return self.blur(frame, regs), regs

    def stream(self, every: int = 3) -> "ClipStream":
        """Anonymise a clip frame by frame without holding it in memory."""
        return ClipStream(self, every)


class ClipStream:
    """Detect on every `every`-th frame; carry the regions (grown a little) to the frames between."""

    def __init__(self, anonymizer: Anonymizer, every: int = 3):
        self.a = anonymizer
        self.every = max(1, every)
        self.i = 0
        self.regs: List[Region] = []
        self.total = 0  # most regions blurred in any one frame

    def __call__(self, frame: np.ndarray) -> np.ndarray:
        if self.i % self.every == 0:
            _, regs = self.a.anonymize(frame)
            h, w = frame.shape[:2]
            self.regs = [Region(_grow(r.box, 0.15, w, h), r.kind) for r in regs]
            self.total = max(self.total, len(self.regs))
        self.i += 1
        return self.a.blur(frame, self.regs)


def _tiles(frame: np.ndarray, n: int, overlap: float = 0.08):
    """Yield ((x, y) offset, view) for an n×n grid of overlapping tiles (n=1: the frame)."""
    h, w = frame.shape[:2]
    if n <= 1:
        yield (0, 0), frame
        return
    tw, th = int(w / n * (1 + overlap)), int(h / n * (1 + overlap))
    for i in range(n):
        for j in range(n):
            x = min(int(j * w / n), w - tw)
            y = min(int(i * h / n), h - th)
            yield (max(0, x), max(0, y)), frame[max(0, y) : max(0, y) + th, max(0, x) : max(0, x) + tw]


def _grow(box: Box, frac: float, w: int, h: int) -> Box:
    x1, y1, x2, y2 = box
    dx, dy = int((x2 - x1) * frac), int((y2 - y1) * frac)
    return max(0, x1 - dx), max(0, y1 - dy), min(w, x2 + dx), min(h, y2 + dy)


def from_config(cfg: Dict[str, Any]) -> Optional[Anonymizer]:
    """Build from the pipeline's `privacy` section; None when anonymising is switched off."""
    p = cfg.get("privacy") or {}
    if not p.get("enabled", True):
        return None
    return Anonymizer(
        model_path=str(p.get("model", "yolov8n.pt")),
        conf=float(p.get("conf", 0.2)),
        imgsz=int(p.get("imgsz", 1920)),
        vehicles=str(p.get("vehicles", "plates")),  # type: ignore[arg-type]
        legible_vehicle_ratio=float(p.get("legible_vehicle_ratio", 0.004)),
        tiles=int(p.get("tiles", 1)),
    )
