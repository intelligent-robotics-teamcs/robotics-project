#!/usr/bin/env python3

from __future__ import annotations

import os
from pathlib import Path

os.environ["ROS_DOMAIN_ID"] = "0"
os.environ["RMW_IMPLEMENTATION"] = "rmw_fastrtps_cpp"
os.environ["ROS_LOCALHOST_ONLY"] = "0"
os.environ["ROS_DISABLE_LOANED_MESSAGES"] = "1"
default_fastdds_profile = Path(__file__).resolve().parents[1] / "fastdds_no_shm.xml"
if default_fastdds_profile.exists():
    os.environ.setdefault(
        "FASTRTPS_DEFAULT_PROFILES_FILE",
        str(default_fastdds_profile),
    )

import rclpy

import json
import re
import select
import signal
import subprocess
import tempfile
import time
from rclpy.node import Node
from std_msgs.msg import String

try:
    from script.action_schema import ActionStatus
except ImportError:
    from action_schema import ActionStatus


DEFAULT_WORKSPACE_PATH = str(Path(__file__).resolve().parents[1])
STEP_LINE_RE = re.compile(
    r"^\[STEP\]\s+"
    r"id=(?P<step_id>\S+)\s+"
    r"action=(?P<action>\S+)\s+"
    r"object=(?P<object>\S+)\s+"
    r"attempt=(?P<attempt>\d+)/(?P<max_attempts>\d+)"
)
SEARCH_FOUND_LINE_RE = re.compile(r"^\[SEARCH\]\s+(?P<object>\S+)\s+detected")


class VisionSequenceExecutorNode(Node):
    def __init__(self):
        super().__init__("vision_sequence_executor")

        self.declare_parameter("action_sequence_topic", "/vision/action_sequence")
        self.declare_parameter("execution_status_topic", "/vision/execution_status")
        self.declare_parameter("execute_once", True)
        self.declare_parameter("deduplicate_sequences", True)
        self.declare_parameter("cooldown_sec", 5.0)
        self.declare_parameter("ignore_empty_sequences", True)
        self.declare_parameter("poll_period_sec", 0.2)
        self.declare_parameter("workspace_path", DEFAULT_WORKSPACE_PATH)

        self.execute_once = self.get_bool_parameter("execute_once")
        self.deduplicate_sequences = self.get_bool_parameter("deduplicate_sequences")
        self.cooldown_sec = max(float(self.get_parameter("cooldown_sec").value), 0.0)
        self.ignore_empty_sequences = self.get_bool_parameter("ignore_empty_sequences")
        self.workspace_path = str(self.get_parameter("workspace_path").value)

        poll_period_sec = max(
            float(self.get_parameter("poll_period_sec").value),
            0.05,
        )

        self._process = None
        self._sequence_file = None
        self._current_sequence = []
        self._has_executed = False
        self._last_sequence_key = None
        self._last_execution_time = 0.0

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

        self.poll_timer = self.create_timer(
            poll_period_sec,
            self.poll_process,
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

    def extract_sequence(self, payload):
        """
        Supports:
        1. {"sequence": [...]}
        2. {"steps": [...]}
        3. {"action_sequence": [...]}
        4. [...]
        """

        if isinstance(payload, dict):
            for key in ("sequence", "steps", "action_sequence"):
                sequence = payload.get(key)
                if isinstance(sequence, list):
                    return sequence
            return []

        if isinstance(payload, list):
            return payload

        return None

    def sequence_callback(self, msg: String):
        try:
            payload = json.loads(msg.data)

        except json.JSONDecodeError as exc:
            self.publish_status(
                "invalid_json",
                [],
                ActionStatus.FAILED.value,
                message=str(exc),
            )
            return

        sequence = self.extract_sequence(payload)

        if sequence is None:
            self.publish_status(
                "invalid_payload",
                [],
                ActionStatus.FAILED.value,
                message="payload must be dict with sequence key or list",
            )
            return

        if not isinstance(sequence, list):
            self.publish_status(
                "invalid_sequence",
                [],
                ActionStatus.FAILED.value,
                message="sequence must be list",
            )
            return

        if self.ignore_empty_sequences and not sequence:
            return

        sequence_key = json.dumps(sequence, sort_keys=True)
        now = time.monotonic()

        if self._process is not None:
            self.get_logger().info(
                "[VISION_EXECUTOR] already executing; skipped"
            )
            return

        if self.execute_once and self._has_executed:
            return

        if (
            self.deduplicate_sequences
            and sequence_key == self._last_sequence_key
            and now - self._last_execution_time < self.cooldown_sec
        ):
            return

        self.start_sequence_process(sequence, sequence_key, now)

    def start_sequence_process(self, sequence, sequence_key, now):

        sequence = self.clean_params(sequence)

        sequence_file = tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".json",
            prefix="vision_sequence_",
            delete=False,
        )

        with sequence_file:
            json.dump(sequence, sequence_file, ensure_ascii=False)

        command = (
            "source /opt/ros/humble/setup.bash && "
            f"source {self.workspace_path}/install/setup.bash && "
            f"python3 -u {self.workspace_path}/script/sequence_executor.py "
            f"--sequence-file {sequence_file.name} "
            f"--sequence-name vision_{int(time.time())}"
        )

        env = os.environ.copy()

        env["ROS_DOMAIN_ID"] = "0"
        env["RMW_IMPLEMENTATION"] = "rmw_fastrtps_cpp"

        env["FASTRTPS_DEFAULT_PROFILES_FILE"] = (
            f"{self.workspace_path}/fastdds_no_shm.xml"
        )

        env["ROS_LOCALHOST_ONLY"] = "0"
        env["ROS_DISABLE_LOANED_MESSAGES"] = "1"
        env["PYTHONUNBUFFERED"] = "1"

        self._process = subprocess.Popen(
            command,
            shell=True,
            executable="/bin/bash",
            env=env,
            start_new_session=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        self._sequence_file = sequence_file.name
        self._current_sequence = sequence
        self._last_sequence_key = sequence_key
        self._last_execution_time = now

        self.get_logger().info(
            "[VISION_EXECUTOR] started sequence process: "
            f"pid={self._process.pid} steps={len(sequence)}"
        )

        self.publish_status(
            "started",
            sequence,
            ActionStatus.RUNNING.value,
        )

    def poll_process(self):
        if self._process is None:
            return

        self.drain_process_output()

        return_code = self._process.poll()

        if return_code is None:
            return

        self.drain_process_output(force=True)

        sequence = self._current_sequence

        status = (
            ActionStatus.SUCCESS.value
            if return_code == 0
            else ActionStatus.FAILED.value
        )

        self.publish_status(
            "finished",
            sequence,
            status,
            message=f"sequence process exited with code {return_code}",
        )

        self.get_logger().info(
            "[VISION_EXECUTOR] sequence process finished: "
            f"pid={self._process.pid} return_code={return_code}"
        )

        if self._sequence_file:
            try:
                Path(self._sequence_file).unlink(missing_ok=True)

            except OSError as exc:
                self.get_logger().warn(
                    f"[VISION_EXECUTOR] failed to remove temp file: {exc}"
                )

        self._process = None
        self._sequence_file = None
        self._current_sequence = []
        self._has_executed = True

    def drain_process_output(self, force=False):
        if self._process is None or self._process.stdout is None:
            return

        while True:
            if not force:
                ready, _, _ = select.select(
                    [self._process.stdout],
                    [],
                    [],
                    0,
                )
                if not ready:
                    return

            line = self._process.stdout.readline()
            if not line:
                return

            line = line.rstrip()
            if line:
                self.handle_process_output_line(line)

            if force:
                continue

    def handle_process_output_line(self, line):
        self.get_logger().info(f"[SEQUENCE_OUT] {line}")

        step_match = STEP_LINE_RE.match(line)
        if step_match:
            step_id = self.parse_optional_int(step_match.group("step_id"))
            action = step_match.group("action")
            object_name = self.parse_optional_object(step_match.group("object"))
            step = self.find_current_step(step_id, action, object_name)

            self.publish_status(
                "step_started",
                self._current_sequence,
                ActionStatus.RUNNING.value,
                step=step,
                action=action,
                object_name=object_name,
                attempt=int(step_match.group("attempt")),
                max_attempts=int(step_match.group("max_attempts")),
            )
            return

        found_match = SEARCH_FOUND_LINE_RE.match(line)
        if found_match:
            object_name = self.parse_optional_object(found_match.group("object"))
            self.publish_status(
                "object_found",
                self._current_sequence,
                ActionStatus.SUCCESS.value,
                action="search",
                object_name=object_name,
            )

    def parse_optional_int(self, value):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def parse_optional_object(self, value):
        if value in {None, "None", "null"}:
            return None
        return value

    def find_current_step(self, step_id, action, object_name):
        for step in self._current_sequence:
            if not isinstance(step, dict):
                continue
            if step_id is not None and step.get("step_id") == step_id:
                return step

        for step in self._current_sequence:
            if not isinstance(step, dict):
                continue
            if step.get("action") == action and step.get("object") == object_name:
                return step

        return {
            "step_id": step_id,
            "action": action,
            "object": object_name,
            "params": {},
        }

    def publish_status(self, event, sequence, status, message="", **extra):
        payload = {
            "event": event,
            "status": status,
            "step_count": len(sequence),
            "sequence": sequence,
            "message": message,
        }
        payload.update(extra)

        self.status_publisher.publish(
            String(
                data=json.dumps(payload, ensure_ascii=False)
            )
        )

    def destroy_node(self):
        self.stop_sequence_process()

        super().destroy_node()

    def stop_sequence_process(self):
        if self._process is None or self._process.poll() is not None:
            return

        self.get_logger().info(
            f"[VISION_EXECUTOR] stopping sequence process: pid={self._process.pid}"
        )

        try:
            if hasattr(os, "killpg"):
                os.killpg(os.getpgid(self._process.pid), signal.SIGTERM)
            else:
                self._process.terminate()

            self._process.wait(timeout=3.0)

        except subprocess.TimeoutExpired:
            self.get_logger().warn(
                "[VISION_EXECUTOR] sequence process did not stop; killing"
            )
            if hasattr(os, "killpg"):
                os.killpg(os.getpgid(self._process.pid), signal.SIGKILL)
            else:
                self._process.kill()
            self._process.wait(timeout=3.0)

        except ProcessLookupError:
            pass

        finally:
            if self._sequence_file:
                try:
                    Path(self._sequence_file).unlink(missing_ok=True)
                except OSError as exc:
                    self.get_logger().warn(
                        f"[VISION_EXECUTOR] failed to remove temp file: {exc}"
                    )

            self._process = None
            self._sequence_file = None
            self._current_sequence = []
    
    def clean_params(self, sequence):
        cleaned_sequence = []

        for step in sequence:
            cleaned_step = dict(step)
            params = cleaned_step.get("params", {})

            if isinstance(params, dict):
                cleaned_step["params"] = {
                    key: value
                    for key, value in params.items()
                    if value is not None
                }

            cleaned_sequence.append(cleaned_step)

        return cleaned_sequence


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
