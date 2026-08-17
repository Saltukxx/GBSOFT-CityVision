from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Union

import numpy as np

from cityvision.config import load_class_config, resolve_class_name
from cityvision.pipeline.model_resolve import ModelBSpec
from cityvision.pipeline.types import Detection

PathLike = Union[str, Path]


class YoloDetector:
    """Single Ultralytics YOLO wrapper with City Vision class mapping."""

    def __init__(
        self,
        model_path: str,
        model_id: str = "A",
        conf: float = 0.35,
        iou: float = 0.45,
        imgsz: int = 640,
        device: Optional[str] = None,
        class_config: Optional[Dict[str, Any]] = None,
        allowed_classes: Optional[Sequence[str]] = None,
        min_box_area: float = 0.0,
        conf_discard: float = 0.55,
        keep_low_conf: bool = False,
    ):
        from ultralytics import YOLO

        self.model_path = model_path
        self.model_id = model_id
        self.conf = conf
        self.iou = iou
        self.imgsz = imgsz
        self.device = device
        self.model = YOLO(model_path)
        self.class_cfg = class_config or load_class_config()
        # Model A COCO bootstrap drops unknown labels; Model B uses native taxonomy names.
        default_bootstrap = self.model_id == "A" and bool(
            self.class_cfg.get("bootstrap_coco_only", True)
        )
        self.bootstrap_coco_only = default_bootstrap
        self.model_version = str(getattr(self.model, "ckpt_path", None) or model_path)
        self.allowed: Optional[Set[str]] = set(allowed_classes) if allowed_classes else None
        self.min_box_area = float(min_box_area)
        self.conf_discard = float(conf_discard)
        self.keep_low_conf = bool(keep_low_conf)

    def predict(self, image: np.ndarray, frame_idx: int, timestamp_ms: float) -> List[Detection]:
        results = self.model.predict(
            source=image,
            conf=self.conf,
            iou=self.iou,
            imgsz=self.imgsz,
            device=self.device,
            verbose=False,
        )
        return self._parse_results(results, frame_idx, timestamp_ms, tracked=False)

    def track(
        self,
        image: np.ndarray,
        frame_idx: int,
        timestamp_ms: float,
        tracker: str,
    ) -> List[Detection]:
        results = self.model.track(
            source=image,
            conf=self.conf,
            iou=self.iou,
            imgsz=self.imgsz,
            device=self.device,
            tracker=tracker,
            persist=True,
            verbose=False,
        )
        return self._parse_results(results, frame_idx, timestamp_ms, tracked=True)

    def _parse_results(
        self,
        results: Any,
        frame_idx: int,
        timestamp_ms: float,
        tracked: bool,
    ) -> List[Detection]:
        detections: List[Detection] = []
        if not results:
            return detections

        result = results[0]
        names = result.names or {}
        boxes = result.boxes
        if boxes is None:
            return detections

        xyxy = boxes.xyxy.cpu().numpy()
        confs = boxes.conf.cpu().numpy()
        clss = boxes.cls.cpu().numpy().astype(int)
        track_ids = None
        if tracked and boxes.id is not None:
            track_ids = boxes.id.cpu().numpy().astype(int)

        for i, (box, conf, cls_id) in enumerate(zip(xyxy, confs, clss)):
            raw_name = str(names.get(int(cls_id), cls_id))
            city_name = resolve_class_name(
                raw_name,
                self.class_cfg,
                bootstrap_coco_only=self.bootstrap_coco_only,
            )
            if city_name is None:
                continue

            if self.allowed is not None and city_name not in self.allowed:
                continue

            x1, y1, x2, y2 = (float(v) for v in box)
            area = max(0.0, x2 - x1) * max(0.0, y2 - y1)
            if area < self.min_box_area:
                continue

            low = float(conf) < self.conf_discard
            if low and not self.keep_low_conf:
                continue

            tid = int(track_ids[i]) if track_ids is not None else None
            detections.append(
                Detection(
                    frame=frame_idx,
                    timestamp_ms=timestamp_ms,
                    class_name=city_name,
                    confidence=float(conf),
                    bbox_xyxy=(x1, y1, x2, y2),
                    track_id=tid,
                    model_id=self.model_id,
                    discarded_low_conf=low,
                )
            )
        return detections


class DualModelDetector:
    """Model A (general) + one or more Model B infrastructure weights."""

    def __init__(
        self,
        model_a: str,
        model_b: Optional[
            Union[PathLike, ModelBSpec, Sequence[Union[PathLike, ModelBSpec]]]
        ] = None,
        conf: float = 0.35,
        iou: float = 0.45,
        imgsz: int = 640,
        device: Optional[str] = None,
        class_config: Optional[Dict[str, Any]] = None,
        allowed_classes: Optional[Sequence[str]] = None,
        min_box_area: float = 0.0,
        conf_discard: float = 0.55,
        keep_low_conf: bool = False,
    ):
        cfg = class_config or load_class_config()
        common = dict(
            conf=conf,
            iou=iou,
            imgsz=imgsz,
            device=device,
            class_config=cfg,
            allowed_classes=allowed_classes,
            min_box_area=min_box_area,
            conf_discard=conf_discard,
            keep_low_conf=keep_low_conf,
        )
        self.det_a = YoloDetector(model_path=model_a, model_id="A", **common)
        self.det_b_list: List[YoloDetector] = []
        b_items: List[Union[PathLike, ModelBSpec]] = []
        if model_b is None:
            b_items = []
        elif isinstance(model_b, (list, tuple)):
            b_items = list(model_b)
        else:
            b_items = [model_b]

        self.model_b_paths: List[str] = []
        for i, item in enumerate(b_items):
            if isinstance(item, ModelBSpec):
                path_s = str(item.path)
                allowed = (
                    item.allowed_classes
                    if item.allowed_classes is not None
                    else allowed_classes
                )
            else:
                path_s = str(item)
                allowed = allowed_classes
            kwargs = dict(common)
            kwargs["allowed_classes"] = allowed
            self.det_b_list.append(
                YoloDetector(model_path=path_s, model_id=f"B{i}", **kwargs)
            )
            self.model_b_paths.append(path_s)

        # backward-compat alias
        self.det_b = self.det_b_list[0] if self.det_b_list else None
        versions = [self.det_a.model_version] + [d.model_version for d in self.det_b_list]
        self.model_version = "+".join(versions)

    def infer(
        self,
        image: np.ndarray,
        frame_idx: int,
        timestamp_ms: float,
        tracking: bool,
        tracker: str,
    ) -> List[Detection]:
        if tracking:
            dets = self.det_a.track(image, frame_idx, timestamp_ms, tracker=tracker)
        else:
            dets = self.det_a.predict(image, frame_idx, timestamp_ms)

        for det_b in self.det_b_list:
            # Infrastructure models: detect only (no cross-model track merge yet)
            dets.extend(det_b.predict(image, frame_idx, timestamp_ms))
        return dets
