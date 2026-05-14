#!/usr/bin/env python3

import json
import os

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import String
from cv_bridge import CvBridge
import cv2

try:
    from script.vision_schema import filter_detections
    from script.vision_to_executor import build_sequence_from_detections
    from script.yolo_detector import YoloDetectionConfig, YoloDetector
except ImportError:
    from vision_schema import filter_detections
    from vision_to_executor import build_sequence_from_detections
    from yolo_detector import YoloDetectionConfig, YoloDetector


class CameraImageProcessor(Node):
    def __init__(self):
        super().__init__("camera_image_processor")

        self.declare_parameter("camera_topic", "/camera/image_raw")
        self.declare_parameter("model_path", "yolov8n.pt")
        self.declare_parameter("confidence_threshold", 0.5)
        self.declare_parameter("image_size", 640)
        self.declare_parameter("device", "")
        self.declare_parameter("enable_display", True)
        self.declare_parameter("run_every_n_frames", 1)
        self.declare_parameter("yolo_verbose", False)
        self.declare_parameter("debug_frame_dir", "")
        self.declare_parameter("debug_frame_interval", 30)
        self.declare_parameter("raw_detection_topic", "/vision/raw_detections")
        self.declare_parameter("detection_topic", "/vision/detections")
        self.declare_parameter("sequence_topic", "/vision/action_sequence")
        self.declare_parameter("yolo_debug_topic", "/vision/yolo_debug")

        self.bridge = CvBridge()
        self.latest_frame = None
        self.frame_count = 0
        self.detector_error_logged = False
        self.last_yolo_debug = {}

        self.image_size = int(self.get_parameter("image_size").value)
        self.enable_display = bool(self.get_parameter("enable_display").value)
        self.run_every_n_frames = max(
            1,
            int(self.get_parameter("run_every_n_frames").value),
        )
        self.debug_frame_dir = str(self.get_parameter("debug_frame_dir").value)
        self.debug_frame_interval = max(
            1,
            int(self.get_parameter("debug_frame_interval").value),
        )
        camera_topic = str(self.get_parameter("camera_topic").value)

        self.raw_detection_publisher = self.create_publisher(
            String,
            str(self.get_parameter("raw_detection_topic").value),
            10,
        )
        self.detection_publisher = self.create_publisher(
            String,
            str(self.get_parameter("detection_topic").value),
            10,
        )
        self.sequence_publisher = self.create_publisher(
            String,
            str(self.get_parameter("sequence_topic").value),
            10,
        )
        self.yolo_debug_publisher = self.create_publisher(
            String,
            str(self.get_parameter("yolo_debug_topic").value),
            10,
        )

        self.subscription = self.create_subscription(
            Image,
            camera_topic,
            self.image_callback,
            10,
        )

        self.detector = self.create_detector()

        self.get_logger().info(f"[CAMERA] subscribed to {camera_topic}")

    def create_detector(self):
        device = str(self.get_parameter("device").value).strip() or None
        config = YoloDetectionConfig(
            model_path=str(self.get_parameter("model_path").value),
            confidence_threshold=float(
                self.get_parameter("confidence_threshold").value
            ),
            image_size=self.image_size,
            device=device,
            verbose=bool(self.get_parameter("yolo_verbose").value),
        )

        try:
            detector = YoloDetector(config)
        except RuntimeError as exc:
            self.get_logger().error(f"[YOLO] detector disabled: {exc}")
            return None

        self.get_logger().info(
            "[YOLO] detector loaded: "
            f"model={config.model_path}, "
            f"conf={config.confidence_threshold}, "
            f"imgsz={config.image_size}, "
            f"device={config.device or 'auto'}"
        )
        return detector

    def image_callback(self, msg):
        try:
            frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        except Exception as e:
            self.get_logger().error(f"[CAMERA] cv_bridge error: {e}")
            return

        processed_frame = self.preprocess_frame(frame)
        self.latest_frame = processed_frame
        self.frame_count += 1

        raw_detections = []
        filtered_detections = []
        sequence = []

        if self.should_run_detection():
            raw_detections = self.run_detection(processed_frame)
            filtered_detections = filter_detections(raw_detections)
            sequence = build_sequence_from_detections(filtered_detections)
            yolo_debug = self.build_yolo_debug(processed_frame, raw_detections)
            self.publish_detection_messages(
                raw_detections,
                filtered_detections,
                sequence,
                yolo_debug,
            )
            self.save_debug_frame_if_needed(processed_frame, raw_detections)

        display_frame = processed_frame
        if raw_detections:
            display_frame = self.draw_detections(processed_frame, raw_detections)

        self.get_logger().info(
            "[CAMERA] frame received: "
            f"shape={processed_frame.shape}, "
            f"raw_detections={len(raw_detections)}, "
            f"filtered_detections={len(filtered_detections)}, "
            f"sequence_steps={len(sequence)}"
        )

        if self.enable_display:
            cv2.imshow("camera_image_processor", display_frame)
            cv2.waitKey(1)

    def preprocess_frame(self, frame):
        resized_frame = cv2.resize(frame, (self.image_size, self.image_size))
        return resized_frame

    def should_run_detection(self):
        return self.frame_count % self.run_every_n_frames == 0

    def run_detection(self, frame):
        if self.detector is None:
            if not self.detector_error_logged:
                self.get_logger().error("[YOLO] detector is not available")
                self.detector_error_logged = True
            return []

        try:
            detections = self.detector.detect(frame)
            self.last_yolo_debug = getattr(self.detector, "last_debug_info", {})
            return detections
        except Exception as exc:
            self.get_logger().error(f"[YOLO] inference error: {exc}")
            self.last_yolo_debug = {"error": str(exc)}
            return []

    def build_yolo_debug(self, frame, raw_detections):
        return {
            "frame_count": self.frame_count,
            "frame_shape": list(frame.shape),
            "frame_min": int(frame.min()),
            "frame_max": int(frame.max()),
            "frame_mean": float(frame.mean()),
            "raw_detection_count": len(raw_detections),
            "yolo": self.last_yolo_debug,
        }

    def publish_detection_messages(
        self,
        raw_detections,
        filtered_detections,
        sequence,
        yolo_debug,
    ):
        self.raw_detection_publisher.publish(
            String(data=json.dumps(raw_detections, ensure_ascii=False))
        )
        self.detection_publisher.publish(
            String(data=json.dumps(filtered_detections, ensure_ascii=False))
        )
        self.sequence_publisher.publish(
            String(data=json.dumps(sequence, ensure_ascii=False))
        )
        self.yolo_debug_publisher.publish(
            String(data=json.dumps(yolo_debug, ensure_ascii=False))
        )

    def save_debug_frame_if_needed(self, frame, raw_detections):
        if not self.debug_frame_dir:
            return

        if self.frame_count % self.debug_frame_interval != 0:
            return

        os.makedirs(self.debug_frame_dir, exist_ok=True)
        base_path = os.path.join(
            self.debug_frame_dir,
            f"frame_{self.frame_count:06d}",
        )
        cv2.imwrite(f"{base_path}_input.jpg", frame)

        annotated = self.draw_detections(frame, raw_detections)
        cv2.imwrite(f"{base_path}_annotated.jpg", annotated)

    def draw_detections(self, frame, detections):
        annotated = frame.copy()

        for detection in detections:
            bbox = detection.get("bbox") or {}
            try:
                x1 = int(bbox["x1"])
                y1 = int(bbox["y1"])
                x2 = int(bbox["x2"])
                y2 = int(bbox["y2"])
            except (KeyError, TypeError, ValueError):
                continue

            label = detection.get("label", "unknown")
            confidence = float(detection.get("confidence", 0.0))
            text = f"{label} {confidence:.2f}"

            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(
                annotated,
                text,
                (x1, max(y1 - 8, 16)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                1,
                cv2.LINE_AA,
            )

        return annotated


def main(args=None):
    rclpy.init(args=args)

    node = CameraImageProcessor()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass

    cv2.destroyAllWindows()
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
