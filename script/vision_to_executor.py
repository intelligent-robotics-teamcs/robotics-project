#!/usr/bin/env python3

from __future__ import annotations

try:
    from script.action_schema import ActionStatus, validate_step
    from script.vision_schema import filter_detections
except ImportError:
    from action_schema import ActionStatus, validate_step
    from vision_schema import filter_detections


OBSERVE_OBJECTS = {
    "dog",
    "cat",
    "person",
    "potted_plant",
}

APPROACH_OBJECTS = {
    "ball",
    "bowl",
    "bed",
    "chair",
}

OBSERVE_PARAMS = {
    "duration_sec": 5.0,
}

APPROACH_PARAMS = {
    "timeout_sec": 60.0,
    "goal_tolerance_m": 0.25,
    "retry_count": 2,
}


def select_primary_detection(detections: list[dict]) -> dict | None:
    if not detections:
        return None

    return max(
        detections,
        key=lambda detection: float(detection.get("confidence", 0.0)),
    )


def detection_to_step(detection: dict, step_id: int = 1) -> dict | None:
    object_name = detection.get("label")

    if object_name in OBSERVE_OBJECTS:
        step = {
            "step_id": step_id,
            "action": "observe",
            "object": object_name,
            "params": dict(OBSERVE_PARAMS),
        }
    elif object_name in APPROACH_OBJECTS:
        step = {
            "step_id": step_id,
            "action": "approach",
            "object": object_name,
            "params": dict(APPROACH_PARAMS),
        }
    else:
        return None

    if validate_step(step) != ActionStatus.SUCCESS:
        return None

    return step


def build_sequence_from_detections(detections: list[dict]) -> list[dict]:
    """
    MVP policy: choose the highest-confidence detection and create one step.
    """

    primary_detection = select_primary_detection(detections)
    if primary_detection is None:
        return []

    step = detection_to_step(primary_detection, step_id=1)
    if step is None:
        return []

    return [step]


def build_sequence_from_raw_detections(raw_detections: list[dict]) -> list[dict]:
    # TODO: Call this from the camera/YOLO pipeline after image preprocessing
    # and inference produce raw detection dictionaries.
    filtered_detections = filter_detections(raw_detections)
    return build_sequence_from_detections(filtered_detections)


def main():
    # TODO: Replace this fake detection list with actual YOLO detections from
    # the Gazebo camera topic once the image subscriber and detector are ready.
    fake_detections = [
        {
            "label": "potted plant",
            "confidence": 0.91,
            "bbox": {"x1": 120, "y1": 80, "x2": 300, "y2": 260},
            "source": "yolo",
        },
        {
            "label": "dog",
            "confidence": 0.72,
            "bbox": {"x1": 20, "y1": 40, "x2": 140, "y2": 220},
            "source": "yolo",
        },
        {
            "label": "unknown object",
            "confidence": 0.99,
            "bbox": {"x1": 0, "y1": 0, "x2": 30, "y2": 30},
            "source": "yolo",
        },
        {
            "label": "bowl",
            "confidence": 0.31,
            "bbox": {"x1": 320, "y1": 100, "x2": 380, "y2": 160},
            "source": "yolo",
        },
    ]

    filtered_detections = filter_detections(fake_detections)
    sequence = build_sequence_from_detections(filtered_detections)

    print("[VISION] filtered detections:")
    for detection in filtered_detections:
        print(detection)

    print("[VISION] executor sequence:")
    for step in sequence:
        print(step)


if __name__ == "__main__":
    main()
