#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
import threading

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from std_msgs.msg import String


if hasattr(sys.stdin, "reconfigure"):
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


EMPTY_MESSAGE = "agent: \ub0b4\uc6a9\uc744 \uc785\ub825\ud574 \uc8fc\uc138\uc694."
FLOW_LABEL = "\uc2e4\ud589 \ud750\ub984"
OBJECT_DISPLAY_NAMES = {
    "dog": "\uac15\uc544\uc9c0",
    "cat": "\uace0\uc591\uc774",
    "person": "\uc0ac\ub78c",
    "ball": "\uacf5",
    "apple": "\uc0ac\uacfc",
    "bed": "\uce68\ub300",
    "chair": "\uc758\uc790",
    "vase": "\uaf43\ubcd1",
}
STATUS_TEXT = {
    "FAILED": "\uc911\ub2e8\ub410\uc2b5\ub2c8\ub2e4",
    "TIMEOUT": "\uc2dc\uac04 \ucd08\uacfc\ub85c \uc911\ub2e8\ub410\uc2b5\ub2c8\ub2e4",
    "REJECTED": "\uac70\ubd80\ub418\uc5b4 \uc911\ub2e8\ub410\uc2b5\ub2c8\ub2e4",
    "SKIPPED": "\uac74\ub108\ub6f0\uc5c8\uc2b5\ub2c8\ub2e4",
    "INVALID_ACTION": "\uc2e4\ud589\ud560 \uc218 \uc5c6\ub294 \ub3d9\uc791\uc774\ub77c \uc911\ub2e8\ub410\uc2b5\ub2c8\ub2e4",
    "INVALID_OBJECT": "\uc2e4\ud589\ud560 \uc218 \uc5c6\ub294 \ub300\uc0c1\uc774\ub77c \uc911\ub2e8\ub410\uc2b5\ub2c8\ub2e4",
    "NOT_ALLOWED": "\uc548\uc804 \uaddc\uce59\uc0c1 \uc911\ub2e8\ub410\uc2b5\ub2c8\ub2e4",
}


def parse_bool(value) -> bool:
    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}

    return bool(value)


def display_object_name(object_name: str | None) -> str:
    if not object_name:
        return "\ub300\uae30"

    return OBJECT_DISPLAY_NAMES.get(object_name, str(object_name))


def format_duration(duration) -> str:
    try:
        seconds = float(duration)
    except (TypeError, ValueError):
        return "\uc7a0\uc2dc"

    if seconds.is_integer():
        return f"{int(seconds)}\ucd08"

    return f"{seconds:.1f}\ucd08"


def describe_step(step: dict) -> str:
    action = step.get("action")
    object_name = step.get("object")
    params = step.get("params") if isinstance(step.get("params"), dict) else {}
    target = display_object_name(object_name)

    if action == "approach":
        return f"{target}\uc73c\ub85c \uc774\ub3d9"

    if action == "observe":
        return f"{target} \uad00\ucc30"

    if action == "search":
        return f"{target} \ucc3e\uae30"

    if action == "feed":
        item = display_object_name(params.get("item") or "apple")
        return f"{item}\ub85c {target} \uae09\uc2dd"

    if action == "wait":
        return f"{format_duration(params.get('duration_sec'))} \ub300\uae30"

    if action == "report":
        return "\uacb0\uacfc \ubcf4\uace0"

    if action == "follow":
        return f"{target} \ucd94\uc885"

    return str(action or "\uc791\uc5c5")


def describe_sequence(sequence) -> str:
    if not isinstance(sequence, list):
        return ""

    descriptions = [
        describe_step(step)
        for step in sequence
        if isinstance(step, dict)
    ]
    descriptions = [
        description
        for description in descriptions
        if description
    ]

    return " -> ".join(
        f"{index}. {description}"
        for index, description in enumerate(descriptions, start=1)
    )


def describe_action_progress(step: dict, attempt=None, max_attempts=None) -> str:
    action = step.get("action")
    object_name = step.get("object")
    params = step.get("params") if isinstance(step.get("params"), dict) else {}
    target = display_object_name(object_name)

    if action == "search":
        text = f"{target}를 찾는 중입니다."
    elif action == "approach":
        text = f"{target}으로 이동합니다."
    elif action == "observe":
        text = f"{target} 관찰을 시작합니다."
    elif action == "feed":
        item = display_object_name(params.get("item") or "apple")
        text = f"{item}로 {target}에게 급식합니다."
    elif action == "follow":
        text = f"{target} 추종을 시작합니다."
    elif action == "wait":
        text = f"{format_duration(params.get('duration_sec'))} 대기합니다."
    elif action == "report":
        text = "결과를 보고합니다."
    else:
        text = f"{describe_step(step)}을 수행합니다."

    try:
        attempt_value = int(attempt)
        max_attempts_value = int(max_attempts)
    except (TypeError, ValueError):
        return text

    if max_attempts_value > 1:
        text = f"{text} ({attempt_value}/{max_attempts_value})"

    return text


def describe_action_result(step: dict, status: str) -> str:
    action = step.get("action")
    object_name = step.get("object")
    target = display_object_name(object_name)

    if status != "SUCCESS":
        status_text = STATUS_TEXT.get(status, "완료하지 못했습니다")
        return f"{describe_step(step)}이 {status_text}."

    if action == "approach":
        return f"{target} 접근 위치에 도착했습니다."

    if action == "search":
        return f"{target}를 찾았습니다."

    if action == "observe":
        return f"{target} 확인을 마쳤습니다."

    if action == "approach":
        return f"{target} 위치에 도착했습니다."

    if action == "feed":
        return f"{target} 급식을 완료했습니다."

    if action == "follow":
        return f"{target} 추종을 완료했습니다."

    return ""


def limit_text(text: str, max_chars: int) -> str:
    text = (text or "").strip()
    if max_chars <= 0 or len(text) <= max_chars:
        return text

    return text[: max_chars - 1].rstrip() + "\u2026"


class AgentConsole(Node):
    def __init__(self):
        super().__init__("agent_console")

        self.declare_parameter("user_request_topic", "/llm/user_request")
        self.declare_parameter("agent_response_topic", "/llm/agent_response")
        self.declare_parameter("execution_status_topic", "/vision/execution_status")
        self.declare_parameter("show_auto_responses", False)
        self.declare_parameter("max_agent_response_chars", 180)

        self.show_auto_responses = parse_bool(
            self.get_parameter("show_auto_responses").value
        )
        self.max_agent_response_chars = int(
            self.get_parameter("max_agent_response_chars").value
        )

        self.user_request_pub = self.create_publisher(
            String,
            str(self.get_parameter("user_request_topic").value),
            10,
        )
        self.agent_response_sub = self.create_subscription(
            String,
            str(self.get_parameter("agent_response_topic").value),
            self.agent_response_callback,
            10,
        )
        self.execution_status_sub = self.create_subscription(
            String,
            str(self.get_parameter("execution_status_topic").value),
            self.execution_status_callback,
            10,
        )

        self.input_thread = threading.Thread(
            target=self.input_loop,
            daemon=True,
        )
        self.input_thread.start()

    def input_loop(self):
        while rclpy.ok():
            try:
                user_text = input("user: ").strip()
            except UnicodeDecodeError:
                print(
                    "agent: \uc785\ub825 \uc778\ucf54\ub529\uc744 \uc77d\uc9c0 \ubabb\ud588\uc2b5\ub2c8\ub2e4. \ub2e4\uc2dc \uc785\ub825\ud574 \uc8fc\uc138\uc694.",
                    flush=True,
                )
                continue
            except EOFError:
                return
            except KeyboardInterrupt:
                rclpy.shutdown()
                return

            if not user_text:
                print(EMPTY_MESSAGE, flush=True)
                continue

            msg = String()
            msg.data = json.dumps({"text": user_text}, ensure_ascii=False)
            self.user_request_pub.publish(msg)

    def agent_response_callback(self, msg: String):
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError:
            print(f"agent: {msg.data}", flush=True)
            return

        if not isinstance(payload, dict):
            return

        if not payload.get("from_user") and not self.show_auto_responses:
            return

        comment = limit_text(
            str(payload.get("comment") or ""),
            self.max_agent_response_chars,
        )
        if comment:
            print(f"agent: {comment}", flush=True)

        flow = str(payload.get("flow") or "").strip()
        if flow:
            print(f"agent: {FLOW_LABEL}: {flow}", flush=True)

    def execution_status_callback(self, msg: String):
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError:
            return

        if not isinstance(payload, dict):
            return

        event = str(payload.get("event") or "")
        status = str(payload.get("status") or "")
        sequence = payload.get("sequence")
        message = str(payload.get("message") or "").strip()

        if event == "step_started":
            step = payload.get("step")
            if not isinstance(step, dict):
                step = {
                    "action": payload.get("action"),
                    "object": payload.get("object_name"),
                    "params": {},
                }
            print(
                f"agent: {describe_action_progress(step, payload.get('attempt'), payload.get('max_attempts'))}",
                flush=True,
            )
            return

        if event == "object_found":
            return

        if event == "step_finished":
            step = payload.get("step")
            if not isinstance(step, dict):
                step = {
                    "action": payload.get("action"),
                    "object": payload.get("object_name"),
                    "params": {},
                }
            result_text = describe_action_result(step, status)
            if result_text:
                print(f"agent: {result_text}", flush=True)
            return

        if event == "started":
            flow = describe_sequence(sequence)
            if flow:
                print(
                    f"agent: \uc54c\ub824\ub4dc\ub9b0 \uc2e4\ud589 \ud750\ub984\uc744 \uc2dc\uc791\ud588\uc2b5\ub2c8\ub2e4: {flow}",
                    flush=True,
                )
            else:
                print("agent: \uc2e4\ud589\uc744 \uc2dc\uc791\ud588\uc2b5\ub2c8\ub2e4.", flush=True)
            return

        if event == "finished" and status == "SUCCESS":
            print(
                "agent: \uc54c\ub824\ub4dc\ub9b0 \uc2e4\ud589 \ud750\ub984\uc744 \uc644\ub8cc\ud588\uc2b5\ub2c8\ub2e4.",
                flush=True,
            )
            return

        if event == "finished":
            status_text = STATUS_TEXT.get(status, "\uc911\ub2e8\ub410\uc2b5\ub2c8\ub2e4")
            suffix = f" \uc0ac\uc720: {message}" if message else ""
            print(
                f"agent: \uc54c\ub824\ub4dc\ub9b0 \uc2e4\ud589 \ud750\ub984\uc774 {status_text}.{suffix}",
                flush=True,
            )
            return

        if status in STATUS_TEXT:
            suffix = f" \uc0ac\uc720: {message}" if message else ""
            print(
                f"agent: \uc2e4\ud589 \uc900\ube44 \uc911 {STATUS_TEXT[status]}.{suffix}",
                flush=True,
            )


def main(args=None):
    rclpy.init(args=args)
    node = AgentConsole()

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
