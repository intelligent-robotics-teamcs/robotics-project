#!/usr/bin/env python3

from __future__ import annotations

import json
import threading
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

try:
    from script.action_schema import ActionStatus
    from script.sequence_executor import SequenceExecutor
except ImportError:
    from action_schema import ActionStatus
    from sequence_executor import SequenceExecutor


class VisionSequenceExecutorNode(Node):
    """
    Bridge vision output to the blocking sequence executor.

    camera_image_processor publishes JSON action steps. This node subscribes,
    deduplicates repeated frames, and executes one sequence at a time.
    """

    def __init__(self):
        super().__init__("vision_sequence_executor")

        self.declare_parameter("action_sequence_topic", "/vision/action_sequence")
        self.declare_parameter("execution_status_topic", "/vision/execution_status")
        self.declare_parameter("execute_once", True)
        self.declare_parameter("deduplicate_sequences", True)
        self.declare_parameter("cooldown_sec", 5.0)
        self.declare_parameter("ignore_empty_sequences", True)

        self.execute_once = self.get_bool_parameter("execute_once")
        self.deduplicate_sequences = self.get_bool_parameter(
            "deduplicate_sequences"
        )
        self.cooldown_sec = max(float(self.get_parameter("cooldown_sec").value), 0.0)
        self.ignore_empty_sequences = self.get_bool_parameter(
            "ignore_empty_sequences"
        )

        self._is_executing = False
        self._has_executed = False
        self._last_sequence_key = None
        self._last_execution_time = 0.0
        self._lock = threading.Lock()

        action_sequence_topic = str(self.get_parameter("action_sequence_topic").value)
        execution_status_topic = str(
            self.get_parameter("execution_status_topic").value
        )

        self.status_publisher = self.create_publisher(
            String,
            execution_status_topic,
            10,
        )
        self.subscription = self.create_subscription(
            String,
            action_sequence_topic,
            self.sequence_callback,
            10,
        )

        self.get_logger().info(
            "[VISION_EXECUTOR] subscribed to "
            f"{action_sequence_topic}; status_topic={execution_status_topic}"
        )

    def get_bool_parameter(self, name):
        value = self.get_parameter(name).value

        if isinstance(value, bool):
            return value

        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}

        return bool(value)

    def sequence_callback(self, msg: String):
        try:
            sequence = json.loads(msg.data)
        except json.JSONDecodeError as exc:
            self.publish_status(
                "invalid_json",
                [],
                ActionStatus.FAILED.value,
                message=str(exc),
            )
            return

        if not isinstance(sequence, list):
            self.publish_status(
                "invalid_sequence",
                [],
                ActionStatus.FAILED.value,
                message="action sequence payload must be a list",
            )
            return

        if self.ignore_empty_sequences and not sequence:
            return

        sequence_key = json.dumps(sequence, sort_keys=True)
        now = time.monotonic()

        with self._lock:
            if self._is_executing:
                self.get_logger().info("[VISION_EXECUTOR] already executing; skipped")
                return

            if self.execute_once and self._has_executed:
                return

            if (
                self.deduplicate_sequences
                and sequence_key == self._last_sequence_key
                and now - self._last_execution_time < self.cooldown_sec
            ):
                return

            self._is_executing = True
            self._last_sequence_key = sequence_key
            self._last_execution_time = now

        worker = threading.Thread(
            target=self.execute_sequence_worker,
            args=(sequence,),
            daemon=True,
        )
        worker.start()

    def execute_sequence_worker(self, sequence: list[dict]):
        sequence_name = f"vision_{int(time.time())}"
        self.publish_status("started", sequence, ActionStatus.RUNNING.value)

        self.get_logger().info(
            "[VISION_EXECUTOR] executing sequence: "
            f"steps={len(sequence)} name={sequence_name}"
        )

        executor = SequenceExecutor(shutdown_rclpy=False)

        try:
            final_status = executor.execute_sequence(
                sequence,
                sequence_name=sequence_name,
            )
        except Exception as exc:
            self.get_logger().error(f"[VISION_EXECUTOR] execution error: {exc}")
            self.publish_status(
                "error",
                sequence,
                ActionStatus.FAILED.value,
                message=str(exc),
            )
            final_status = ActionStatus.FAILED
        else:
            self.publish_status("finished", sequence, final_status.value)
        finally:
            with self._lock:
                self._is_executing = False
                self._has_executed = True

    def publish_status(
        self,
        event: str,
        sequence: list,
        status: str,
        message: str = "",
    ):
        payload = {
            "event": event,
            "status": status,
            "step_count": len(sequence),
            "sequence": sequence,
            "message": message,
        }
        self.status_publisher.publish(
            String(data=json.dumps(payload, ensure_ascii=False))
        )


def main(args=None):
    rclpy.init(args=args)
    node = VisionSequenceExecutorNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
