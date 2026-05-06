#!/usr/bin/env python3

import math
import sys
import time
from dataclasses import dataclass
from enum import Enum

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient

from nav2_msgs.action import NavigateToPose
from geometry_msgs.msg import PoseStamped
from action_msgs.msg import GoalStatus

try:
    from script.target_resolver import TargetResolver
except ImportError:
    from target_resolver import TargetResolver


class NavigationState(Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    REJECTED = "REJECTED"
    SERVER_UNAVAILABLE = "SERVER_UNAVAILABLE"
    RESOLVE_FAILED = "RESOLVE_FAILED"


@dataclass
class NavigationResult:
    state: NavigationState
    object_name: str
    target_name: str | None = None
    status_code: int | None = None
    min_distance_remaining: float | None = None
    message: str = ""

    @property
    def success(self) -> bool:
        return self.state == NavigationState.SUCCESS


class Nav2GoalSender(Node):
    """
    Single-goal navigation executor.

    Responsibility:
    - object name -> pose
    - send NavigateToPose goal
    - track feedback distance
    - judge success/failure
    - handle timeout
    """

    def __init__(self):
        super().__init__("nav2_goal_sender")

        self._action_client = ActionClient(
            self,
            NavigateToPose,
            "navigate_to_pose"
        )

        self.resolver = TargetResolver()

        self._latest_distance_remaining = None
        self._min_distance_remaining = None

        self._last_feedback_log_time = 0.0

    def yaw_to_quaternion(self, yaw: float):
        """
        Convert yaw angle to quaternion.
        TurtleBot3 navigation mainly uses z/w orientation.
        """
        qz = math.sin(yaw / 2.0)
        qw = math.cos(yaw / 2.0)
        return qz, qw

    def create_pose_stamped(self, pose_dict: dict) -> PoseStamped:
        """
        Convert target.yaml pose dict to ROS2 PoseStamped.
        """
        pose_msg = PoseStamped()

        pose_msg.header.frame_id = pose_dict["frame_id"]
        pose_msg.header.stamp = self.get_clock().now().to_msg()

        pose_msg.pose.position.x = float(pose_dict["x"])
        pose_msg.pose.position.y = float(pose_dict["y"])
        pose_msg.pose.position.z = 0.0

        qz, qw = self.yaw_to_quaternion(float(pose_dict["yaw"]))

        pose_msg.pose.orientation.x = 0.0
        pose_msg.pose.orientation.y = 0.0
        pose_msg.pose.orientation.z = qz
        pose_msg.pose.orientation.w = qw

        return pose_msg

    def feedback_callback(self, feedback_msg):
        """
        Track Nav2 feedback.

        distance_remaining:
        - smaller value means the robot is closer to the goal.
        - used for logging and arrival judgment.
        """
        feedback = feedback_msg.feedback
        distance = float(feedback.distance_remaining)

        self._latest_distance_remaining = distance

        if self._min_distance_remaining is None:
            self._min_distance_remaining = distance
        else:
            self._min_distance_remaining = min(
                self._min_distance_remaining,
                distance
            )

        current_time = self.get_clock().now().nanoseconds / 1e9
        if current_time - self._last_feedback_log_time >= 1.0:  # Log every second
            self.get_logger().info(
                f"Distance remaining: {distance:.2f} m"
            )
            self._last_feedback_log_time = current_time

    def _reset_feedback_state(self):
        self._latest_distance_remaining = None
        self._min_distance_remaining = None

    def _judge_result(
        self,
        object_name: str,
        target_name: str,
        status_code: int,
        goal_tolerance_m: float
    ) -> NavigationResult:
        """
        Convert Nav2 action status into project-level result.

        Nav2 status 4 means STATUS_SUCCEEDED.
        distance_remaining is additionally used as a sanity check.
        """
        min_distance = self._min_distance_remaining

        if status_code == GoalStatus.STATUS_SUCCEEDED:
            if min_distance is None:
                return NavigationResult(
                    state=NavigationState.SUCCESS,
                    object_name=object_name,
                    target_name=target_name,
                    status_code=status_code,
                    min_distance_remaining=min_distance,
                    message="Nav2 reported success."
                )

            if min_distance <= goal_tolerance_m:
                return NavigationResult(
                    state=NavigationState.SUCCESS,
                    object_name=object_name,
                    target_name=target_name,
                    status_code=status_code,
                    min_distance_remaining=min_distance,
                    message=(
                        f"Arrived within tolerance "
                        f"({min_distance:.2f} m <= {goal_tolerance_m:.2f} m)."
                    )
                )

            return NavigationResult(
                state=NavigationState.SUCCESS,
                object_name=object_name,
                target_name=target_name,
                status_code=status_code,
                min_distance_remaining=min_distance,
                message=(
                    "Nav2 reported success, but feedback distance did not "
                    "go below tolerance. Treating as success because final "
                    "action status is succeeded."
                )
            )

        return NavigationResult(
            state=NavigationState.FAILED,
            object_name=object_name,
            target_name=target_name,
            status_code=status_code,
            min_distance_remaining=min_distance,
            message=f"Nav2 finished with non-success status: {status_code}"
        )

    def navigate_to_object(
        self,
        object_name: str,
        timeout_sec: float = 60.0,
        goal_tolerance_m: float = 0.25
    ) -> NavigationResult:
        """
        Blocking single-object navigation.

        This function is intentionally blocking because multi-target navigation
        needs a clear result before moving to the next target.
        """
        self._reset_feedback_state()

        self.get_logger().info(
            f"Resolving target for object: {object_name}"
        )

        try:
            resolved = self.resolver.get_pose(object_name)
        except Exception as e:
            self.get_logger().error(f"Failed to resolve target: {e}")

            return NavigationResult(
                state=NavigationState.RESOLVE_FAILED,
                object_name=object_name,
                message=str(e)
            )

        pose_dict = resolved["pose"]
        target_name = resolved["target"]

        self.get_logger().info(
            f"Resolved object '{object_name}' to target '{target_name}'"
        )

        goal_msg = NavigateToPose.Goal()
        goal_msg.pose = self.create_pose_stamped(pose_dict)

        self.get_logger().info("Waiting for Nav2 action server...")

        if not self._action_client.wait_for_server(timeout_sec=10.0):
            self.get_logger().error("Nav2 action server not available.")

            return NavigationResult(
                state=NavigationState.SERVER_UNAVAILABLE,
                object_name=object_name,
                target_name=target_name,
                message="Nav2 action server not available."
            )

        self.get_logger().info(
            f"Sending goal: "
            f"x={pose_dict['x']}, "
            f"y={pose_dict['y']}, "
            f"yaw={pose_dict['yaw']}"
        )

        send_goal_future = self._action_client.send_goal_async(
            goal_msg,
            feedback_callback=self.feedback_callback
        )

        start_time = time.monotonic()

        while not send_goal_future.done():
            rclpy.spin_once(self, timeout_sec=0.1)

            if time.monotonic() - start_time > timeout_sec:
                return NavigationResult(
                    state=NavigationState.TIMEOUT,
                    object_name=object_name,
                    target_name=target_name,
                    min_distance_remaining=self._min_distance_remaining,
                    message="Timed out while waiting for goal response."
                )

        goal_handle = send_goal_future.result()

        if not goal_handle.accepted:
            self.get_logger().error("Goal rejected by Nav2.")

            return NavigationResult(
                state=NavigationState.REJECTED,
                object_name=object_name,
                target_name=target_name,
                min_distance_remaining=self._min_distance_remaining,
                message="Goal rejected by Nav2."
            )

        self.get_logger().info("Goal accepted by Nav2.")

        result_future = goal_handle.get_result_async()

        # Arrival judgement is based on both action status and feedback distance
        arrival_start_time = None
        arrival_hold_sec = 0.5

        while not result_future.done():
            rclpy.spin_once(self, timeout_sec=0.1)

            # Feedback-based arrival judgement
            if (
                self._latest_distance_remaining is not None
                and self._latest_distance_remaining <= goal_tolerance_m
            ):
                if arrival_start_time is None:
                    arrival_start_time = time.monotonic()

                if time.monotonic() - arrival_start_time >= arrival_hold_sec:
                    self.get_logger().info(
                        f"[SUCCESS] {object_name} -> {target_name}: "
                        f"Arrived by feedback distance "
                        f"({self._latest_distance_remaining:.2f} m <= "
                        f"{goal_tolerance_m:.2f} m)."
                    )

                    cancel_future = goal_handle.cancel_goal_async()

                    while not cancel_future.done():
                        rclpy.spin_once(self, timeout_sec=0.1)

                    return NavigationResult(
                        state=NavigationState.SUCCESS,
                        object_name=object_name,
                        target_name=target_name,
                        min_distance_remaining=self._min_distance_remaining,
                        message=(
                            f"Arrived by feedback distance "
                            f"({self._latest_distance_remaining:.2f} m <= "
                            f"{goal_tolerance_m:.2f} m)."
                        )
                    )
            else:
                arrival_start_time = None

            if time.monotonic() - start_time > timeout_sec:
                self.get_logger().warn(
                    f"Navigation timeout after {timeout_sec:.1f} sec. "
                    "Canceling goal..."
                )

                cancel_future = goal_handle.cancel_goal_async()

                while not cancel_future.done():
                    rclpy.spin_once(self, timeout_sec=0.1)

                return NavigationResult(
                    state=NavigationState.TIMEOUT,
                    object_name=object_name,
                    target_name=target_name,
                    min_distance_remaining=self._min_distance_remaining,
                    message=f"Navigation timed out after {timeout_sec:.1f} sec."
                )

        wrapped_result = result_future.result()
        status_code = wrapped_result.status

        result = self._judge_result(
            object_name=object_name,
            target_name=target_name,
            status_code=status_code,
            goal_tolerance_m=goal_tolerance_m
        )

        if result.success:
            self.get_logger().info(
                f"[SUCCESS] {object_name} -> {target_name}: {result.message}"
            )
        else:
            self.get_logger().warn(
                f"[FAILED] {object_name} -> {target_name}: {result.message}"
            )

        return result


def main(args=None):
    rclpy.init(args=args)

    if len(sys.argv) < 2:
        print("Usage: ros2 run pet_robot_pkg nav2_goal_sender <object_name>")
        print("Example: ros2 run pet_robot_pkg nav2_goal_sender bowl")
        rclpy.shutdown()
        return

    object_name = sys.argv[1]

    node = Nav2GoalSender()

    result = node.navigate_to_object(
        object_name=object_name,
        timeout_sec=60.0,
        goal_tolerance_m=0.25
    )

    print(result)

    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()