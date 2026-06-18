#!/usr/bin/env python3

from __future__ import annotations

import math
import time
from dataclasses import dataclass

import rclpy
from gazebo_msgs.msg import EntityState
from gazebo_msgs.srv import SetEntityState
from geometry_msgs.msg import Pose
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node


@dataclass
class MovingTarget:
    entity_name: str
    waypoints: list[tuple[float, float]]
    speed_mps: float
    index: int = 0
    x: float = 0.0
    y: float = 0.0
    yaw: float = 0.0
    pending: object | None = None

    def __post_init__(self):
        self.x, self.y = self.waypoints[0]


class MovingPetTargets(Node):
    def __init__(self):
        super().__init__("moving_pet_targets")

        self.declare_parameter("dog_entity", "sanity_dog_v1")
        self.declare_parameter("cat_entity", "sanity_cat")
        self.declare_parameter("speed_mps", 0.06)
        self.declare_parameter("cat_speed_mps", 0.05)
        self.declare_parameter("update_rate_hz", 10.0)
        self.declare_parameter("start_delay_sec", 5.0)
        self.declare_parameter("set_entity_state_service", "/set_entity_state")

        speed_mps = max(0.01, float(self.get_parameter("speed_mps").value))
        cat_speed_mps = max(
            0.01,
            float(self.get_parameter("cat_speed_mps").value),
        )
        update_rate_hz = max(
            1.0,
            float(self.get_parameter("update_rate_hz").value),
        )

        self.start_time = (
            time.monotonic()
            + max(0.0, float(self.get_parameter("start_delay_sec").value))
        )
        self.last_update_time = time.monotonic()
        self.last_service_log_time = 0.0
        self.service_ready_logged = False

        self.targets = [
            MovingTarget(
                entity_name=str(self.get_parameter("dog_entity").value),
                speed_mps=speed_mps,
                waypoints=[
                    (2.00, 0.90),
                    (1.70, 0.70),
                    (1.55, 1.00),
                    (1.90, 1.20),
                ],
            ),
            MovingTarget(
                entity_name=str(self.get_parameter("cat_entity").value),
                speed_mps=cat_speed_mps,
                waypoints=[
                    (1.80, -1.35),
                    (1.45, -1.15),
                    (1.65, -0.95),
                    (2.00, -1.15),
                ],
            ),
        ]

        self.service_name = str(
            self.get_parameter("set_entity_state_service").value
        )
        self.client = self.create_client(SetEntityState, self.service_name)
        self.timer = self.create_timer(1.0 / update_rate_hz, self.tick)

        self.get_logger().info(
            f"[MOVING_PETS] waiting for {self.service_name}; "
            f"dog={speed_mps:.2f} m/s, cat={cat_speed_mps:.2f} m/s"
        )

    def tick(self):
        now = time.monotonic()
        dt = max(0.0, now - self.last_update_time)
        self.last_update_time = now

        if now < self.start_time:
            return

        if not self.client.service_is_ready():
            self.client.wait_for_service(timeout_sec=0.0)
            if now - self.last_service_log_time >= 2.0:
                self.get_logger().warn(
                    f"[MOVING_PETS] {self.service_name} is not available yet. "
                    "Check that libgazebo_ros_state.so is loaded in the world."
                )
                self.last_service_log_time = now
            return

        if not self.service_ready_logged:
            self.get_logger().info(
                f"[MOVING_PETS] connected to {self.service_name}; moving targets"
            )
            self.service_ready_logged = True

        for target in self.targets:
            if target.pending is not None:
                if not target.pending.done():
                    continue

                try:
                    result = target.pending.result()
                    if not result.success:
                        self.get_logger().warn(
                            f"[MOVING_PETS] failed to move {target.entity_name}: "
                            f"{result.status_message}"
                        )
                except Exception as exc:
                    self.get_logger().warn(
                        f"[MOVING_PETS] service call failed for "
                        f"{target.entity_name}: {exc}"
                    )

                target.pending = None

            self.advance_target(target, dt)
            request = SetEntityState.Request()
            request.state = self.build_entity_state(target)
            target.pending = self.client.call_async(request)

    def advance_target(self, target: MovingTarget, dt: float):
        remaining_step = target.speed_mps * dt

        while remaining_step > 0.0:
            next_index = (target.index + 1) % len(target.waypoints)
            next_x, next_y = target.waypoints[next_index]
            dx = next_x - target.x
            dy = next_y - target.y
            distance = math.hypot(dx, dy)

            if distance <= 1e-6:
                target.index = next_index
                continue

            target.yaw = math.atan2(dy, dx)

            if remaining_step < distance:
                ratio = remaining_step / distance
                target.x += dx * ratio
                target.y += dy * ratio
                break

            target.x = next_x
            target.y = next_y
            target.index = next_index
            remaining_step -= distance

    def build_entity_state(self, target: MovingTarget) -> EntityState:
        state = EntityState()
        state.name = target.entity_name
        state.reference_frame = "world"
        state.pose = Pose()
        state.pose.position.x = target.x
        state.pose.position.y = target.y
        state.pose.position.z = 0.0
        state.pose.orientation.z = math.sin(target.yaw / 2.0)
        state.pose.orientation.w = math.cos(target.yaw / 2.0)
        return state


def main(args=None):
    rclpy.init(args=args)
    node = MovingPetTargets()

    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
