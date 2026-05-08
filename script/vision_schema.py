#!/usr/bin/env python3

from __future__ import annotations

try:
    from script.action_schema import VALID_OBJECTS
except ImportError:
    from action_schema import VALID_OBJECTS


CONFIDENCE_THRESHOLD = 0.5

LABEL_MAP = {
    "dog": "dog",
    "cat": "cat",
    "person": "person",
    "sports ball": "ball",
    "sports_ball": "ball",
    "ball": "ball",
    "bowl": "bowl",
    "bed": "bed",
    "chair": "chair",
    "potted plant": "potted_plant",
    "potted_plant": "potted_plant",
}

VALID_VISION_LABELS = set(LABEL_MAP)


def normalize_label(raw_label: str | None) -> str | None:
    """
    Convert a detector label into the project object name used by the executor.
    """

    if not raw_label:
        return None

    normalized_key = str(raw_label).strip().lower().replace("-", " ")
    object_name = LABEL_MAP.get(normalized_key)

    if object_name not in VALID_OBJECTS:
        return None

    return object_name


def normalize_detection(raw_detection: dict) -> dict | None:
    """
    Normalize one YOLO-like detection into the shared vision schema.

    Expected output:
    {
        "label": str,
        "confidence": float,
        "bbox": {"x1": int|float, "y1": int|float, "x2": int|float, "y2": int|float},
        "center": {"x": float, "y": float},
        "source": str,
    }
    """

    # TODO: Convert the real YOLO result format here if the detector returns
    # class IDs, tensor boxes, or xywh boxes instead of this YOLO-like dict.
    object_name = normalize_label(raw_detection.get("label"))
    if object_name is None:
        return None

    try:
        confidence = float(raw_detection.get("confidence", 0.0))
    except (TypeError, ValueError):
        return None

    if confidence < CONFIDENCE_THRESHOLD:
        return None

    bbox = raw_detection.get("bbox") or {}
    center = raw_detection.get("center")

    if center is None and {"x1", "y1", "x2", "y2"}.issubset(bbox):
        center = {
            "x": (float(bbox["x1"]) + float(bbox["x2"])) / 2.0,
            "y": (float(bbox["y1"]) + float(bbox["y2"])) / 2.0,
        }

    return {
        "label": object_name,
        "confidence": confidence,
        "bbox": bbox,
        "center": center or {},
        "source": raw_detection.get("source", "yolo"),
    }


def filter_detections(raw_detections: list[dict]) -> list[dict]:
    """
    Keep confident project objects, deduplicate by label, and sort by confidence.
    """

    best_by_label: dict[str, dict] = {}

    for raw_detection in raw_detections:
        detection = normalize_detection(raw_detection)
        if detection is None:
            continue

        label = detection["label"]
        previous = best_by_label.get(label)

        if previous is None or detection["confidence"] > previous["confidence"]:
            best_by_label[label] = detection

    return sorted(
        best_by_label.values(),
        key=lambda detection: detection["confidence"],
        reverse=True,
    )
