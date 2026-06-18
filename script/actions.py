#!/usr/bin/env python3

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING

try:
    from script.action_schema import ActionStatus
except ImportError:
    from action_schema import ActionStatus

if TYPE_CHECKING:
    try:
        from script.nav2_goal_sender import Nav2GoalSender
    except ImportError:
        from nav2_goal_sender import Nav2GoalSender


def navigation_result_to_action_status(result) -> ActionStatus:
    if getattr(result, "success", False):
        return ActionStatus.SUCCESS

    state = getattr(getattr(result, "state", None), "value", "")

    if state == "TIMEOUT":
        return ActionStatus.TIMEOUT
    if state == "REJECTED":
        return ActionStatus.REJECTED

    return ActionStatus.FAILED


def approach_action(
    node,
    object_name: str,
    timeout_sec: float = 60.0,
    goal_tolerance_m: float = 0.35,
    retry_count: int = 0,
):
    if hasattr(node, "navigate_to_object"):
        node.get_logger().info(
            f"[APPROACH] using Nav2 approach for {object_name}"
        )

        result = node.navigate_to_object(
            object_name=object_name,
            timeout_sec=timeout_sec,
            goal_tolerance_m=goal_tolerance_m,
        )

        return navigation_result_to_action_status(result)

    node.get_logger().warn(
        f"[APPROACH] Nav2 node unavailable; using direct odom fallback for {object_name}"
    )

    return direct_odom_approach_action(
        node=node,
        object_name=object_name,
        timeout_sec=timeout_sec,
        goal_tolerance_m=goal_tolerance_m,
    )
def wait_action(duration_sec: float = 3.0) -> ActionStatus:
    """
    지정된 시간 동안 대기하는 action
    """

    print(f"[WAIT] waiting for {duration_sec} sec")
    time.sleep(duration_sec)
    return ActionStatus.SUCCESS


def observe_action(
    object_name: str,
    duration_sec: float = 5.0,
) -> ActionStatus:
    """
    object를 관찰하는 action
    아직 Vision 미연동 상태이므로 placeholder로 구현
    """

    print(f"[OBSERVE] observing {object_name} for {duration_sec} sec")
    time.sleep(duration_sec)
    print(f"[OBSERVE] {object_name} observation finished")
    return ActionStatus.SUCCESS


def face_target_action(
    node,
    object_name: str,
    timeout_sec: float = 8.0,
    yaw_tolerance_rad: float = 0.12,
    max_angular_speed: float = 0.45,
    cmd_vel_topic: str = "/cmd_vel",
    base_frame: str = "base_footprint",
) -> ActionStatus:
    import math

    import rclpy
    from geometry_msgs.msg import Twist
    from nav_msgs.msg import Odometry

    def normalize_angle(angle: float) -> float:
        while angle > math.pi:
            angle -= 2.0 * math.pi
        while angle < -math.pi:
            angle += 2.0 * math.pi
        return angle

    def yaw_from_quaternion(q) -> float:
        siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        return math.atan2(siny_cosp, cosy_cosp)

    def clamp(value: float, min_value: float, max_value: float) -> float:
        return max(min_value, min(max_value, value))

    try:
        center = node.resolver.get_object_center(object_name)
    except Exception as e:
        node.get_logger().info(
            f"[FACE_TARGET] no object center for {object_name}: {e}"
        )
        return ActionStatus.SKIPPED

    frame_id = str(center.get("frame_id", "map"))
    target_x = float(center["x"])
    target_y = float(center["y"])

    current = {
        "ready": False,
        "x": 0.0,
        "y": 0.0,
        "yaw": 0.0,
    }

    def odom_callback(msg: Odometry):
        current["x"] = msg.pose.pose.position.x
        current["y"] = msg.pose.pose.position.y
        current["yaw"] = yaw_from_quaternion(msg.pose.pose.orientation)
        current["ready"] = True

    cmd_pub = node.create_publisher(Twist, cmd_vel_topic, 10)
    odom_sub = node.create_subscription(Odometry, "/odom", odom_callback, 10)

    tf_buffer = None
    tf_listener = None
    try:
        from rclpy.time import Time
        from tf2_ros import Buffer, TransformListener

        tf_buffer = Buffer()
        tf_listener = TransformListener(tf_buffer, node)
        tf_time = Time()
    except Exception as e:
        node.get_logger().warn(
            f"[FACE_TARGET] TF unavailable, falling back to /odom: {e}"
        )
        tf_time = None

    def read_pose():
        if tf_buffer is not None:
            try:
                transform = tf_buffer.lookup_transform(
                    frame_id,
                    base_frame,
                    tf_time,
                )
                translation = transform.transform.translation
                rotation = transform.transform.rotation
                return (
                    float(translation.x),
                    float(translation.y),
                    yaw_from_quaternion(rotation),
                )
            except Exception:
                pass

        if current["ready"]:
            return current["x"], current["y"], current["yaw"]

        return None

    def publish_stop():
        cmd_pub.publish(Twist())

    node.get_logger().info(
        f"[FACE_TARGET] rotating to face {object_name} center "
        f"at ({target_x:.2f}, {target_y:.2f}) in {frame_id}"
    )

    deadline = time.monotonic() + max(timeout_sec, 0.1)
    last_log_time = 0.0

    try:
        while rclpy.ok() and time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.05)

            pose = read_pose()
            if pose is None:
                continue

            current_x, current_y, current_yaw = pose
            target_yaw = math.atan2(target_y - current_y, target_x - current_x)
            yaw_error = normalize_angle(target_yaw - current_yaw)

            if abs(yaw_error) <= yaw_tolerance_rad:
                publish_stop()
                node.get_logger().info(
                    f"[FACE_TARGET] {object_name} aligned "
                    f"yaw_error={yaw_error:.2f}"
                )
                return ActionStatus.SUCCESS

            cmd = Twist()
            cmd.angular.z = clamp(
                1.2 * yaw_error,
                -abs(max_angular_speed),
                abs(max_angular_speed),
            )
            cmd_pub.publish(cmd)

            now = time.monotonic()
            if now - last_log_time >= 0.5:
                node.get_logger().info(
                    f"[FACE_TARGET] current=({current_x:.2f}, {current_y:.2f}, yaw={current_yaw:.2f}) "
                    f"target_yaw={target_yaw:.2f} yaw_error={yaw_error:.2f}"
                )
                last_log_time = now

            time.sleep(0.05)

        publish_stop()
        node.get_logger().warn(f"[FACE_TARGET] {object_name} alignment timed out")
        return ActionStatus.TIMEOUT

    finally:
        publish_stop()
        node.destroy_subscription(odom_sub)
        node.destroy_publisher(cmd_pub)


DETECTION_LABEL_ALIAS = {
    "dog": "dog",
    "puppy": "dog",
    "cat": "cat",
    "person": "person",
    "sports_ball": "ball",
    "sports ball": "ball",
    "ball": "ball",
    "apple": "apple",
    "bowl": "apple",
    "cup": "apple",
    "dish": "apple",
    "plate": "apple",
    "bed": "bed",
    "couch": "bed",
    "sofa": "bed",
    "chair": "chair",
    "vase": "vase",
    "plant": "vase",
    "potted_plant": "vase",
    "airplane": "vase",
}


def normalize_detection_label(label) -> str:
    normalized = str(label or "").strip().lower()
    normalized = normalized.replace("-", "_").replace(" ", "_")
    return DETECTION_LABEL_ALIAS.get(normalized, normalized)


def detection_matches_target(detection: dict, object_name: str) -> bool:
    label = normalize_detection_label(detection.get("label"))
    target = normalize_detection_label(object_name)

    return bool(label) and label == target
def extract_detection_list(data: str) -> list[dict]:
    try:
        payload = json.loads(data)
    except json.JSONDecodeError:
        return []

    if isinstance(payload, dict):
        detections = (
            payload.get("detections")
            or payload.get("filtered_detections")
            or payload.get("objects")
            or []
        )
    elif isinstance(payload, list):
        detections = payload
    else:
        detections = []

    return [
        detection
        for detection in detections
        if isinstance(detection, dict)
    ]


def search_action(
    node: Nav2GoalSender,
    object_name: str,
    timeout_sec: float = 120.0,
    scan_duration_sec: float = 8.0,
    angular_speed: float = 0.35,
    detection_topic: str = "/vision/detections",
    cmd_vel_topic: str = "/cmd_vel",
    patrol_objects: list[str] | None = None,
    navigation_timeout_sec: float = 45.0,
    goal_tolerance_m: float = 0.35,
) -> ActionStatus:
    """
    Search for an object using live detections.

    The action rotates in place while watching the detection topic. If patrol
    objects are provided, it moves through those known locations and scans at
    each stop until the target is detected or the timeout expires.
    """

    import rclpy
    from geometry_msgs.msg import Twist
    from std_msgs.msg import String

    found = {
        "value": False,
    }

    def detection_callback(msg):
        for detection in extract_detection_list(msg.data):
            if detection_matches_target(detection, object_name):
                found["value"] = True
                return

    publisher = node.create_publisher(Twist, cmd_vel_topic, 10)
    subscription = node.create_subscription(
        String,
        detection_topic,
        detection_callback,
        10,
    )

    deadline = time.monotonic() + max(timeout_sec, 0.0)
    scan_duration_sec = max(scan_duration_sec, 0.2)
    patrol_objects = list(patrol_objects or [])

    def stop_robot():
        publisher.publish(Twist())

    def spin_scan(duration_sec: float) -> bool:
        scan_deadline = min(time.monotonic() + duration_sec, deadline)

        while (
            rclpy.ok()
            and not found["value"]
            and time.monotonic() < scan_deadline
        ):
            command = Twist()
            command.angular.z = angular_speed
            publisher.publish(command)
            rclpy.spin_once(node, timeout_sec=0.1)

        stop_robot()
        return found["value"]

    try:
        print(f"[SEARCH] searching for {object_name}")

        if spin_scan(scan_duration_sec):
            print(f"[SEARCH] {object_name} detected")
            return ActionStatus.SUCCESS

        for patrol_object in patrol_objects:
            if found["value"] or time.monotonic() >= deadline:
                break

            if hasattr(node, "navigate_to_object"):
                remaining_sec = deadline - time.monotonic()
                nav_timeout_sec = min(max(navigation_timeout_sec, 0.1), remaining_sec)

                print(f"[SEARCH] moving to scan point: {patrol_object}")
                result = node.navigate_to_object(
                    object_name=patrol_object,
                    timeout_sec=nav_timeout_sec,
                    goal_tolerance_m=goal_tolerance_m,
                )

                if found["value"]:
                    print(f"[SEARCH] {object_name} detected")
                    return ActionStatus.SUCCESS

                if not result.success:
                    print(
                        f"[SEARCH] scan point {patrol_object} navigation failed: "
                        f"{result.state.value}"
                    )

            if spin_scan(scan_duration_sec):
                print(f"[SEARCH] {object_name} detected")
                return ActionStatus.SUCCESS

        print(f"[SEARCH] {object_name} not detected before timeout")
        return ActionStatus.TIMEOUT

    finally:
        stop_robot()
        node.destroy_subscription(subscription)
        node.destroy_publisher(publisher)


def follow_action(
    node,
    object_name: str,
    duration_sec: float = 10.0,
    safe_distance_m: float = 1.0,
    detection_topic: str = "/vision/detections",
    cmd_vel_topic: str = "/cmd_vel",
    image_width_px: float = 640.0,
    desired_bbox_height_px: float = 190.0,
    max_linear_speed: float = 0.25,
    max_angular_speed: float = 0.45,
    target_lost_timeout_sec: float = 3.0,
) -> ActionStatus:
    """
    object를 따라가는 action
    Vision 연동 전까지는 실제 구현하지 않고 SKIPPED 반환
    """

    import rclpy
    from geometry_msgs.msg import Twist
    from std_msgs.msg import String

    latest = {
        "detection": None,
        "time": None,
        "last_error": 0.0,
        "seen": False,
    }

    def clamp(value: float, min_value: float, max_value: float) -> float:
        return max(min_value, min(max_value, value))

    def select_detection(detections: list[dict]) -> dict | None:
        matches = [
            detection
            for detection in detections
            if detection_matches_target(detection, object_name)
        ]

        if not matches:
            return None

        return max(
            matches,
            key=lambda detection: float(detection.get("confidence", 0.0)),
        )

    def bbox_height(detection: dict) -> float:
        bbox = detection.get("bbox") or {}

        try:
            return max(1.0, float(bbox["y2"]) - float(bbox["y1"]))
        except (KeyError, TypeError, ValueError):
            return 0.0

    def center_x(detection: dict) -> float | None:
        center = detection.get("center") or {}
        if "x" in center:
            try:
                return float(center["x"])
            except (TypeError, ValueError):
                pass

        bbox = detection.get("bbox") or {}
        try:
            return (float(bbox["x1"]) + float(bbox["x2"])) / 2.0
        except (KeyError, TypeError, ValueError):
            return None

    def detection_callback(msg):
        detection = select_detection(extract_detection_list(msg.data))
        if detection is None:
            return

        x = center_x(detection)
        if x is None:
            return

        latest["detection"] = detection
        latest["time"] = time.monotonic()
        latest["last_error"] = (
            (image_width_px / 2.0) - x
        ) / max(image_width_px / 2.0, 1.0)
        latest["seen"] = True

    publisher = node.create_publisher(Twist, cmd_vel_topic, 10)
    subscription = node.create_subscription(
        String,
        detection_topic,
        detection_callback,
        10,
    )

    duration_sec = max(duration_sec, 0.0)
    target_lost_timeout_sec = max(target_lost_timeout_sec, 0.1)
    desired_bbox_height_px = max(desired_bbox_height_px, 20.0)
    max_linear_speed = abs(max_linear_speed)
    max_angular_speed = abs(max_angular_speed)
    center_deadband = 0.08
    distance_deadband = 0.18
    deadline = time.monotonic() + duration_sec

    def publish_stop():
        publisher.publish(Twist())

    node.get_logger().info(
        f"[FOLLOW] tracking {object_name} for {duration_sec:.1f}s "
        f"using {detection_topic}; safe_distance={safe_distance_m:.2f}m"
    )

    try:
        last_log_time = 0.0

        while rclpy.ok() and time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.05)
            now = time.monotonic()
            command = Twist()

            detection = latest["detection"]
            last_seen_time = latest["time"]

            if detection is None or last_seen_time is None:
                command.angular.z = 0.18
                publisher.publish(command)
                time.sleep(0.05)
                continue

            lost_for = now - last_seen_time
            if lost_for > target_lost_timeout_sec:
                publish_stop()
                node.get_logger().warn(
                    f"[FOLLOW] lost {object_name} for {lost_for:.1f}s"
                )
                return ActionStatus.TIMEOUT

            if lost_for > 0.5:
                command.angular.z = clamp(
                    0.25 * latest["last_error"],
                    -0.25,
                    0.25,
                )
                publisher.publish(command)
                time.sleep(0.05)
                continue

            x_error = float(latest["last_error"])
            height = bbox_height(detection)
            height_error = (
                desired_bbox_height_px - height
            ) / desired_bbox_height_px

            if abs(x_error) > center_deadband:
                command.angular.z = clamp(
                    0.9 * x_error,
                    -max_angular_speed,
                    max_angular_speed,
                )

            if abs(x_error) < 0.35 and abs(height_error) > distance_deadband:
                command.linear.x = clamp(
                    0.20 * height_error,
                    -0.08,
                    max_linear_speed,
                )

            publisher.publish(command)

            if now - last_log_time >= 0.5:
                node.get_logger().info(
                    f"[FOLLOW] {object_name} x_error={x_error:.2f} "
                    f"bbox_h={height:.1f} cmd=({command.linear.x:.2f}, "
                    f"{command.angular.z:.2f})"
                )
                last_log_time = now

            time.sleep(0.05)

        publish_stop()

        if latest["seen"]:
            node.get_logger().info(f"[FOLLOW] {object_name} follow complete")
            return ActionStatus.SUCCESS

        node.get_logger().warn(f"[FOLLOW] {object_name} was not detected")
        return ActionStatus.TIMEOUT

    finally:
        publish_stop()
        node.destroy_subscription(subscription)
        node.destroy_publisher(publisher)


def feed_action(
    object_name: str,
    item: str = "apple",
) -> ActionStatus:
    """
    Feed a pet target with the prepared food item.
    """

    print(f"[FEED] feeding {object_name} with {item}")
    return ActionStatus.SUCCESS


def report_action(message: str = "sequence completed") -> ActionStatus:
    """
    현재 상태나 결과 메시지를 출력하는 action
    """

    print(f"[REPORT] {message}")
    return ActionStatus.SUCCESS

def direct_odom_approach_action(
    node,
    object_name: str,
    timeout_sec: float = 60.0,
    goal_tolerance_m: float = 0.35,
):
    import math
    import os
    import time
    import yaml

    import rclpy
    from geometry_msgs.msg import Twist
    from nav_msgs.msg import Odometry

    try:
        from script.action_schema import ActionStatus
    except ImportError:
        from action_schema import ActionStatus

    def normalize_angle(angle: float) -> float:
        while angle > math.pi:
            angle -= 2.0 * math.pi
        while angle < -math.pi:
            angle += 2.0 * math.pi
        return angle

    def yaw_from_quaternion(q) -> float:
        siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        return math.atan2(siny_cosp, cosy_cosp)

    def clamp(value: float, min_value: float, max_value: float) -> float:
        return max(min_value, min(max_value, value))

    def load_target_from_yaml(obj_name: str):
        target_name = f"{obj_name}_zone"

        candidate_paths = [
            os.path.join(os.getcwd(), "config", "target.yaml"),
            os.path.expanduser("~/ros2_clean_ws/config/target.yaml"),
            os.path.expanduser("~/ros2_clean_ws/src/robotics-project/config/target.yaml"),
            os.path.expanduser("~/ros2_clean_ws/install/pet_robot_pkg/share/pet_robot_pkg/config/target.yaml"),
        ]

        for path in candidate_paths:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)

                target = data["targets"][target_name]
                return (
                    target_name,
                    float(target["x"]),
                    float(target["y"]),
                    float(target.get("yaw", 0.0)),
                    path,
                )

        raise FileNotFoundError(
            "target.yaml not found. Checked: " + ", ".join(candidate_paths)
        )

    try:
        target_name, target_x, target_y, _, target_path = load_target_from_yaml(object_name)
    except Exception as e:
        node.get_logger().error(f"[DIRECT_APPROACH] failed to load target: {e}")
        return ActionStatus.FAILED

    current = {
        "ready": False,
        "x": 0.0,
        "y": 0.0,
        "yaw": 0.0,
    }

    def odom_callback(msg: Odometry):
        current["x"] = msg.pose.pose.position.x
        current["y"] = msg.pose.pose.position.y
        current["yaw"] = yaw_from_quaternion(msg.pose.pose.orientation)
        current["ready"] = True

    cmd_pub = node.create_publisher(Twist, "/cmd_vel", 10)
    odom_sub = node.create_subscription(Odometry, "/odom", odom_callback, 10)

    def publish_stop():
        stop = Twist()
        cmd_pub.publish(stop)

    node.get_logger().info(
        f"[DIRECT_APPROACH] {object_name} -> {target_name}, "
        f"target=({target_x:.2f}, {target_y:.2f}), "
        f"tolerance={goal_tolerance_m:.2f}, yaml={target_path}"
    )

    deadline = time.monotonic() + timeout_sec

    try:
        # publisher/subscriber 연결 대기
        time.sleep(0.5)

        # odom 첫 수신 대기
        while rclpy.ok() and not current["ready"] and time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.1)

        if not current["ready"]:
            node.get_logger().error("[DIRECT_APPROACH] /odom not received")
            publish_stop()
            return ActionStatus.TIMEOUT

        last_log_time = 0.0

        while rclpy.ok() and time.monotonic() < deadline:
            dx = target_x - current["x"]
            dy = target_y - current["y"]
            distance = math.hypot(dx, dy)

            target_heading = math.atan2(dy, dx)
            yaw_error = normalize_angle(target_heading - current["yaw"])

            if distance <= goal_tolerance_m:
                publish_stop()
                node.get_logger().info(
                    f"[DIRECT_APPROACH] {object_name} SUCCESS "
                    f"distance={distance:.2f} <= {goal_tolerance_m:.2f}"
                )
                return ActionStatus.SUCCESS

            cmd = Twist()

            if abs(yaw_error) > 0.30:
                # 먼저 방향 맞추기
                cmd.linear.x = 0.0
                cmd.angular.z = clamp(1.2 * yaw_error, -0.45, 0.45)
            else:
                # 방향이 맞으면 전진
                cmd.linear.x = clamp(0.35 * distance, 0.08, 0.18)
                cmd.angular.z = clamp(0.8 * yaw_error, -0.25, 0.25)

            cmd_pub.publish(cmd)

            now = time.monotonic()
            if now - last_log_time >= 0.5:
                node.get_logger().info(
                    f"[DIRECT_APPROACH] current=({current['x']:.2f}, {current['y']:.2f}, yaw={current['yaw']:.2f}) "
                    f"target=({target_x:.2f}, {target_y:.2f}) "
                    f"heading={target_heading:.2f} yaw_error={yaw_error:.2f} "
                    f"dist={distance:.2f} cmd=({cmd.linear.x:.2f}, {cmd.angular.z:.2f})"
                )
                last_log_time = now

            rclpy.spin_once(node, timeout_sec=0.1)
            time.sleep(0.05)

        publish_stop()
        node.get_logger().warn(f"[DIRECT_APPROACH] {object_name} TIMEOUT")
        return ActionStatus.TIMEOUT

    finally:
        publish_stop()
        node.destroy_subscription(odom_sub)
        node.destroy_publisher(cmd_pub)
