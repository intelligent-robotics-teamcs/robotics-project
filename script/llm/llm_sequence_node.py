#!/usr/bin/env python3

import json
import threading
import time
from collections import Counter

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

try:
    from .llm_sequence_generator import (
        call_llm_api,
        normalize_label,
    )
except ImportError:
    from llm_sequence_generator import (
        call_llm_api,
        normalize_label,
    )


OBJECT_DISPLAY_NAMES = {
    "dog": "강아지",
    "cat": "고양이",
    "person": "사람",
    "ball": "공",
    "apple": "사과",
    "bed": "침대",
    "chair": "의자",
    "vase": "꽃병",
}


def display_object_name(object_name):
    if not object_name:
        return "대상"

    return OBJECT_DISPLAY_NAMES.get(object_name, str(object_name))


def format_duration(duration):
    if duration is None:
        return "잠시"

    try:
        seconds = float(duration)
    except (TypeError, ValueError):
        return "잠시"

    if seconds.is_integer():
        return f"{int(seconds)}초"

    return f"{seconds:.1f}초"


def describe_sequence_step(step):
    if not isinstance(step, dict):
        return ""

    action = step.get("action")
    object_name = step.get("object")
    params = step.get("params")
    params = params if isinstance(params, dict) else {}
    target = display_object_name(object_name)

    if action == "approach":
        return f"{target} 방향으로 이동"

    if action == "observe":
        return f"{target} 관찰"

    if action == "search":
        return f"{target} 찾기"

    if action == "feed":
        item = display_object_name(params.get("item") or "apple")
        return f"{item}로 {target} 급식"

    if action == "wait":
        return f"{format_duration(params.get('duration_sec'))} 대기"

    if action == "report":
        return "결과 보고"

    return str(action or "작업")


def build_agent_response(sequence, comment: str = ""):
    comment = (comment or "").strip()
    steps = [
        step
        for step in sequence or []
        if isinstance(step, dict)
    ]
    flow_steps = [
        describe_sequence_step(step)
        for step in steps
    ]
    flow_steps = [
        description
        for description in flow_steps
        if description
    ]

    approach_step = next(
        (step for step in steps if step.get("action") == "approach"),
        None,
    )
    observe_step = next(
        (step for step in steps if step.get("action") == "observe"),
        None,
    )
    feed_step = next(
        (step for step in steps if step.get("action") == "feed"),
        None,
    )
    has_report = any(step.get("action") == "report" for step in steps)

    if not comment and feed_step:
        feed_params = feed_step.get("params")
        feed_params = feed_params if isinstance(feed_params, dict) else {}
        item = display_object_name(feed_params.get("item") or "apple")
        pet = display_object_name(feed_step.get("object"))
        comment = f"{item}를 확인한 뒤 {pet}에게 급식하겠습니다."
    elif not comment and approach_step and observe_step and has_report:
        comment = (
            f"{display_object_name(approach_step.get('object'))} 방향으로 이동한 뒤 "
            f"{display_object_name(observe_step.get('object'))} 관찰을 진행하고 "
            "결과를 보고하겠습니다."
        )
    elif not comment and approach_step and has_report:
        comment = (
            f"{display_object_name(approach_step.get('object'))} 방향으로 이동한 뒤 "
            "결과를 보고하겠습니다."
        )
    elif not comment and observe_step and has_report:
        comment = (
            f"{display_object_name(observe_step.get('object'))} 관찰 후 "
            "결과를 보고하겠습니다."
        )
    elif not comment and approach_step:
        comment = (
            f"{display_object_name(approach_step.get('object'))} 방향으로 이동하겠습니다."
        )
    elif not comment and observe_step:
        comment = (
            f"{display_object_name(observe_step.get('object'))} 관찰을 진행하겠습니다."
        )
    elif not comment and flow_steps:
        comment = "요청을 바탕으로 실행 흐름을 진행하겠습니다."
    elif not comment:
        comment = "실행 가능한 계획을 찾지 못해 잠시 대기하겠습니다."

    flow = " -> ".join(
        f"{index}. {description}"
        for index, description in enumerate(flow_steps, start=1)
    )
    if not flow:
        flow = "실행 계획 없음"

    return comment, flow


def build_dynamic_user_text(labels):
    label_set = set(labels)

    if "vase" in label_set:
        return "꽃병은 접근하지 말고 관찰한 뒤 결과를 보고해줘"

    if "apple" in label_set and "dog" in label_set:
        return "강아지 급식 시나리오를 수행해줘"

    if "ball" in label_set and "dog" in label_set:
        return "강아지 놀이 시나리오를 수행해줘"

    if {"apple", "bed", "chair"}.issubset(label_set):
        return "사과, 침대, 의자를 순서대로 확인해줘"

    if "dog" in label_set:
        return "강아지 상태를 관찰하고 결과를 보고해줘"

    if "cat" in label_set:
        return "고양이 상태를 관찰하고 결과를 보고해줘"

    if "bed" in label_set:
        return "침대 쪽을 확인하고 결과를 보고해줘"

    if "chair" in label_set:
        return "의자 쪽을 확인하고 결과를 보고해줘"

    return "유효한 target이 보이지 않으면 잠시 기다린 뒤 결과를 보고해줘"


def parse_user_request(data: str) -> str:
    text = data.strip()
    if not text:
        return ""

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return text

    if isinstance(payload, dict):
        value = payload.get("text") or payload.get("request") or payload.get("user_text")
        return str(value).strip() if value else ""

    if isinstance(payload, str):
        return payload.strip()

    return ""


class LLMSequenceNode(Node):
    def __init__(self):
        super().__init__("llm_sequence_node")

        self.declare_parameter("detection_topic", "/vision/detections")
        self.declare_parameter("user_request_topic", "/llm/user_request")
        self.declare_parameter("agent_response_topic", "/llm/agent_response")
        self.declare_parameter("action_sequence_topic", "/vision/action_sequence")
        self.declare_parameter("timer_period_sec", 5.0)
        self.declare_parameter("require_user_request", False)
        self.declare_parameter("interactive_input", False)

        self.detected_labels = []
        self.last_valid_labels = []
        self.last_sequence_key = None
        self.latest_user_request = ""
        self.user_request_id = 0
        self.consumed_user_request_id = 0
        self.request_lock = threading.Lock()
        self.require_user_request = self.get_bool_parameter("require_user_request")
        self.interactive_input_enabled = self.get_bool_parameter("interactive_input")

        self.label_history = []

        self.detection_sub = self.create_subscription(
            String,
            str(self.get_parameter("detection_topic").value),
            self.detection_callback,
            10,
        )

        self.user_request_sub = self.create_subscription(
            String,
            str(self.get_parameter("user_request_topic").value),
            self.user_request_callback,
            10,
        )

        self.sequence_pub = self.create_publisher(
            String,
            str(self.get_parameter("action_sequence_topic").value),
            10,
        )
        self.agent_response_pub = self.create_publisher(
            String,
            str(self.get_parameter("agent_response_topic").value),
            10,
        )

        timer_period_sec = max(
            0.5,
            float(self.get_parameter("timer_period_sec").value),
        )
        self.timer = self.create_timer(timer_period_sec, self.generate_sequence)

        self.get_logger().info(
            "LLM sequence node started. "
            f"user_request_topic={self.get_parameter('user_request_topic').value}, "
            f"agent_response_topic={self.get_parameter('agent_response_topic').value}"
        )

        if self.interactive_input_enabled:
            self.input_thread = threading.Thread(
                target=self.interactive_input_loop,
                daemon=True,
            )
            self.input_thread.start()

    def get_bool_parameter(self, name):
        value = self.get_parameter(name).value

        if isinstance(value, bool):
            return value

        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}

        return bool(value)

    def submit_user_request(self, user_request, source):
        user_request = (user_request or "").strip()
        if not user_request:
            return None

        with self.request_lock:
            self.latest_user_request = user_request
            self.user_request_id += 1
            request_id = self.user_request_id

        self.get_logger().info(
            f"User request received from {source}: {user_request}"
        )
        return request_id

    def wait_until_request_processed(self, request_id):
        deadline = time.monotonic() + 120.0

        while rclpy.ok() and time.monotonic() < deadline:
            with self.request_lock:
                if self.consumed_user_request_id >= request_id:
                    return

            time.sleep(0.2)

    def interactive_input_loop(self):
        while rclpy.ok():
            try:
                user_request = input("agent: 지금 어떤 상황이신가요?: ")
            except EOFError:
                self.get_logger().warn("Interactive input closed.")
                return
            except KeyboardInterrupt:
                return

            request_id = self.submit_user_request(user_request, "stdin")
            if request_id is None:
                print("agent: 내용을 입력해 주세요.", flush=True)
                continue

            self.wait_until_request_processed(request_id)

    def user_request_callback(self, msg):
        user_request = parse_user_request(msg.data)
        request_id = self.submit_user_request(user_request, "topic")
        if request_id is None:
            self.get_logger().warn("Ignored empty user request.")

    def detection_callback(self, msg):
        try:
            detections = json.loads(msg.data)

            if isinstance(detections, dict):
                detections = (
                    detections.get("detections")
                    or detections.get("filtered_detections")
                    or detections.get("objects")
                    or []
                )

            if not isinstance(detections, list):
                self.get_logger().warn(
                    "Detection payload must be a list or a dict containing detections."
                )
                return

            labels = []

            for det in detections:
                if not isinstance(det, dict) or "label" not in det:
                    continue

                normalized = normalize_label(det["label"])

                if normalized and normalized not in labels:
                    labels.append(normalized)

            if labels:
                self.last_valid_labels = labels
            else:
                labels = self.last_valid_labels

            self.label_history.extend(labels)

            if len(self.label_history) > 10:
                self.label_history.pop(0)

            counter = Counter(self.label_history)

            self.detected_labels = [
                label
                for label, count in counter.items()
                if count >= 3
            ]

            self.get_logger().info(f"Detected labels: {self.detected_labels}")

        except Exception as e:
            self.get_logger().error(f"Detection parse error: {e}")

    def select_user_text(self):
        with self.request_lock:
            if self.user_request_id > self.consumed_user_request_id:
                return self.latest_user_request, True, self.user_request_id

        if self.require_user_request:
            return "", False, None

        if self.detected_labels:
            return build_dynamic_user_text(self.detected_labels), False, None

        return "", False, None

    def generate_sequence(self):
        user_text, from_user, request_id = self.select_user_text()

        if not user_text:
            self.get_logger().info("No user request or valid labels yet. Skip LLM call.")
            return

        detected_labels = list(self.detected_labels)

        if from_user:
            sequence_key = (
                "user",
                request_id,
                tuple(sorted(detected_labels)),
            )
        else:
            sequence_key = (
                "auto",
                tuple(sorted(detected_labels)),
            )

        if sequence_key == self.last_sequence_key:
            return

        self.last_sequence_key = sequence_key

        try:
            result = call_llm_api(user_text, detected_labels)
            sequence = result.get("sequence", []) if isinstance(result, dict) else []
            planner = (
                result.get("planner", "unknown")
                if isinstance(result, dict)
                else "unknown"
            )
            self.get_logger().info(f"Planner source: {planner}")
            agent_comment, agent_flow = build_agent_response(
                sequence,
                str(result.get("comment") or "") if isinstance(result, dict) else "",
            )

            msg = String()
            msg.data = json.dumps(result, ensure_ascii=False)
            self.sequence_pub.publish(msg)

            agent_msg = String()
            agent_msg.data = json.dumps(
                {
                    "comment": agent_comment,
                    "flow": agent_flow,
                    "request": user_text,
                    "from_user": from_user,
                },
                ensure_ascii=False,
            )
            self.agent_response_pub.publish(agent_msg)

            if from_user and request_id is not None:
                with self.request_lock:
                    self.consumed_user_request_id = max(
                        self.consumed_user_request_id,
                        request_id,
                    )

            self.get_logger().info(f"User text: {user_text}")
            self.get_logger().info(f"Published action sequence: {msg.data}")

        except Exception as e:
            self.get_logger().error(f"LLM API error: {e}")


def main(args=None):
    rclpy.init(args=args)

    node = LLMSequenceNode()

    rclpy.spin(node)

    node.destroy_node()

    rclpy.shutdown()


if __name__ == "__main__":
    main()
