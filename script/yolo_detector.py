#!/usr/bin/env python3

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class YoloDetectionConfig:
    model_path: str = "yolov8n.pt"
    confidence_threshold: float = 0.5
    image_size: int = 640
    device: str | None = None
    verbose: bool = False


class YoloDetector:
    """
    Thin adapter around Ultralytics YOLO.

    The rest of the project consumes plain dictionaries, so this class keeps
    tensor/model-specific details out of the ROS node and vision schema.
    """

    def __init__(self, config: YoloDetectionConfig | None = None):
        self.config = config or YoloDetectionConfig()
        self.last_debug_info: dict = {}

        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise RuntimeError(
                "ultralytics is required for YOLO inference. "
                "Install it with: pip install ultralytics"
            ) from exc

        self.model = YOLO(self.config.model_path)

    def detect(self, frame: Any) -> list[dict]:
        results = self.model.predict(
            source=frame,
            imgsz=self.config.image_size,
            conf=self.config.confidence_threshold,
            device=self.config.device,
            verbose=self.config.verbose,
        )

        if not results:
            self.last_debug_info = {
                "result_count": 0,
                "box_count": 0,
                "summary": "no YOLO results returned",
            }
            return []

        result = results[0]
        detections = parse_ultralytics_result(result)
        self.last_debug_info = summarize_ultralytics_result(result, detections)
        return detections


def parse_ultralytics_result(result: Any) -> list[dict]:
    names = getattr(result, "names", {}) or {}
    boxes = getattr(result, "boxes", None)

    if boxes is None or getattr(boxes, "xyxy", None) is None:
        return []

    xyxy_rows = _to_list(boxes.xyxy)
    confidence_rows = _to_list(getattr(boxes, "conf", []))
    class_rows = _to_list(getattr(boxes, "cls", []))

    detections: list[dict] = []

    for index, xyxy in enumerate(xyxy_rows):
        if len(xyxy) < 4:
            continue

        class_id = int(_scalar_at(class_rows, index, default=-1))
        confidence = float(_scalar_at(confidence_rows, index, default=0.0))
        label = names.get(class_id, str(class_id))

        x1, y1, x2, y2 = [float(value) for value in xyxy[:4]]

        detections.append(
            {
                "label": label,
                "class_id": class_id,
                "confidence": confidence,
                "bbox": {
                    "x1": x1,
                    "y1": y1,
                    "x2": x2,
                    "y2": y2,
                },
                "center": {
                    "x": (x1 + x2) / 2.0,
                    "y": (y1 + y2) / 2.0,
                },
                "source": "yolo",
            }
        )

    return detections


def summarize_ultralytics_result(result: Any, detections: list[dict]) -> dict:
    boxes = getattr(result, "boxes", None)
    speed = getattr(result, "speed", {}) or {}
    orig_shape = getattr(result, "orig_shape", None)

    try:
        yolo_summary = result.verbose()
    except Exception:
        yolo_summary = ""

    return {
        "result_count": 1,
        "box_count": len(detections),
        "orig_shape": list(orig_shape) if orig_shape else None,
        "speed_ms": {
            key: float(value)
            for key, value in speed.items()
        },
        "yolo_summary": str(yolo_summary).strip(),
        "has_boxes": boxes is not None,
        "top_detections": detections[:10],
    }


def _to_list(value: Any) -> list:
    if value is None:
        return []

    if hasattr(value, "detach"):
        value = value.detach()

    if hasattr(value, "cpu"):
        value = value.cpu()

    if hasattr(value, "tolist"):
        return value.tolist()

    return list(value)


def _scalar_at(rows: list, index: int, default: float) -> float:
    try:
        value = rows[index]
    except (IndexError, TypeError):
        return default

    if isinstance(value, list):
        if not value:
            return default
        value = value[0]

    return float(value)
