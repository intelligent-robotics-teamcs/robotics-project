#!/usr/bin/env python3

import math
import sys

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient

from nav2_msgs.action import NavigateToPose
from geometry_msgs.msg import PoseStamped

from target_resolver import TargetResolver


class Nav2GoalSender(Node):
    def __init__(self):
        super().__init__("nav2_goal_sender")

        self._action_client = ActionClient(
            self,
            NavigateToPose,
            "navigate_to_pose"
        )

        self.resolver = TargetResolver()

    def yaw_to_quaternion(self, yaw):
        """
        Convert yaw angle to quaternion.
        TurtleBot3 navigation mostly uses yaw only.
        """
        qz = math.sin(yaw / 2.0)
        qw = math.cos(yaw / 2.0)

        return qz, qw

    def create_pose_stamped(self, pose_dict):
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

    def send_goal_to_object(self, object_name):
        """
        object name -> target pose -> Nav2 goal
        """

        self.get_logger().info(f"Resolving target for object: {object_name}")

        try:
            result = self.resolver.get_pose(object_name)
        except Exception as e:
            self.get_logger().error(f"Failed to resolve target: {e}")
            return

        pose_dict = result["pose"]
        target_name = result["target"]

        self.get_logger().info(
            f"Resolved object '{object_name}' to target '{target_name}'"
        )

        goal_msg = NavigateToPose.Goal()
        goal_msg.pose = self.create_pose_stamped(pose_dict)

        self.get_logger().info("Waiting for Nav2 action server...")

        if not self._action_client.wait_for_server(timeout_sec=10.0):
            self.get_logger().error("Nav2 action server not available.")
            return

        self.get_logger().info(
            f"Sending goal: x={pose_dict['x']}, y={pose_dict['y']}, yaw={pose_dict['yaw']}"
        )

        send_goal_future = self._action_client.send_goal_async(
            goal_msg,
            feedback_callback=self.feedback_callback
        )

        send_goal_future.add_done_callback(self.goal_response_callback)

    def goal_response_callback(self, future):
        goal_handle = future.result()

        if not goal_handle.accepted:
            self.get_logger().error("Goal rejected by Nav2.")
            return

        self.get_logger().info("Goal accepted by Nav2.")

        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self.result_callback)

    def feedback_callback(self, feedback_msg):
        feedback = feedback_msg.feedback

        distance = feedback.distance_remaining

        self.get_logger().info(
            f"Distance remaining: {distance:.2f} m"
        )

    def result_callback(self, future):
        result = future.result().result
        status = future.result().status

        if status == 4:
            self.get_logger().info("Navigation succeeded.")
        else:
            self.get_logger().warn(f"Navigation finished with status: {status}")

        rclpy.shutdown()


def main(args=None):
    rclpy.init(args=args)

    if len(sys.argv) < 2:
        print("Usage: ros2 run pet_robot_pkg nav2_goal_sender <object_name>")
        print("Example: ros2 run pet_robot_pkg nav2_goal_sender bowl")
        return

    object_name = sys.argv[1]

    node = Nav2GoalSender()
    node.send_goal_to_object(object_name)

    rclpy.spin(node)


if __name__ == "__main__":
    main()