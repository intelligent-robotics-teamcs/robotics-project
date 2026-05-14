#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from script.vision_schema import filter_detections
    from script.vision_to_executor import build_sequence_from_detections
    from script.yolo_detector import YoloDetectionConfig, YoloDetector
except ImportError:
    from vision_schema import filter_detections
    from vision_to_executor import build_sequence_from_detections
    from yolo_detector import YoloDetectionConfig, YoloDetector


def run_single_inference(args) -> int:
    detector = YoloDetector(
        YoloDetectionConfig(
            model_path=args.model,
            confidence_threshold=args.conf,
            image_size=args.imgsz,
            device=args.device,
        )
    )

    raw_detections = detector.detect(args.image)
    filtered_detections = filter_detections(raw_detections)
    sequence = build_sequence_from_detections(filtered_detections)

    payload = {
        "source": args.image,
        "raw_detections": raw_detections,
        "filtered_detections": filtered_detections,
        "action_sequence": sequence,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def run_camera_inference(args) -> int:
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("opencv-python is required for camera inference") from exc

    detector = YoloDetector(
        YoloDetectionConfig(
            model_path=args.model,
            confidence_threshold=args.conf,
            image_size=args.imgsz,
            device=args.device,
        )
    )

    capture = cv2.VideoCapture(args.camera)
    if not capture.isOpened():
        raise RuntimeError(f"Failed to open camera index {args.camera}")

    try:
        frame_index = 0
        while True:
            ok, frame = capture.read()
            if not ok:
                raise RuntimeError("Failed to read camera frame")

            frame_index += 1
            if frame_index % args.every != 0:
                continue

            raw_detections = detector.detect(frame)
            filtered_detections = filter_detections(raw_detections)
            sequence = build_sequence_from_detections(filtered_detections)

            print(
                json.dumps(
                    {
                        "frame": frame_index,
                        "raw_detections": raw_detections,
                        "filtered_detections": filtered_detections,
                        "action_sequence": sequence,
                    },
                    ensure_ascii=False,
                )
            )

            if args.once:
                break
    finally:
        capture.release()

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run real Ultralytics YOLO inference and print project detections."
    )
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--image", help="Path to an image file")
    source_group.add_argument("--camera", type=int, help="Camera index, usually 0")

    parser.add_argument("--model", default="yolov8n.pt", help="YOLO model path")
    parser.add_argument("--conf", type=float, default=0.5, help="Confidence threshold")
    parser.add_argument("--imgsz", type=int, default=640, help="YOLO image size")
    parser.add_argument("--device", default=None, help="Device such as cpu, 0, cuda:0")
    parser.add_argument(
        "--every",
        type=int,
        default=1,
        help="Run camera inference every N frames",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one camera inference and exit",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.every = max(1, args.every)

    if args.image:
        image_path = Path(args.image)
        if not image_path.exists():
            parser.error(f"image does not exist: {image_path}")
        args.image = str(image_path)
        return run_single_inference(args)

    return run_camera_inference(args)


if __name__ == "__main__":
    raise SystemExit(main())
