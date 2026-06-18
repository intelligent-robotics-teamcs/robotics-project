#!/usr/bin/env python3

from __future__ import annotations

import json
import os
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

try:
    from script.action_schema import ActionStatus, validate_step
except ImportError:
    try:
        from action_schema import ActionStatus, validate_step
    except ImportError:
        ActionStatus = None
        validate_step = None

if load_dotenv is not None:
    load_dotenv()


ALLOWED_OBJECTS = [
    "dog",
    "cat",
    "apple",
    "ball",
    "bed",
    "chair",
    "vase",
]

KNOWN_WORLD_OBJECTS = [
    "dog",
    "cat",
    "apple",
    "ball",
    "bed",
    "chair",
    "vase",
]

ALLOWED_ACTIONS = [
    "approach",
    "observe",
    "search",
    "feed",
    "follow",
    "wait",
    "report",
]

ACTION_CAPABILITIES = {
    "approach": "Navigate to a known reachable target location.",
    "search": (
        "Look for a target with vision by rotating and visiting patrol points. "
        "Use this before observing a target that may not currently be visible."
    ),
    "observe": "Inspect or confirm the target once it is visible or reached.",
    "feed": "Give a prepared food item to a pet target.",
    "follow": "Track a moving pet or person using vision feedback.",
    "wait": "Pause for a specified duration.",
    "report": "Tell the user the result or final status.",
}

APPROACH_PARAMS = {
    "timeout_sec": 60.0,
    "goal_tolerance_m": 0.25,
    "retry_count": 2,
}

OBSERVE_PARAMS = {
    "duration_sec": 5.0,
}

SEARCH_PARAMS = {
    "timeout_sec": 45.0,
    "duration_sec": 4.0,
    "retry_count": 0,
}

WAIT_PARAMS = {
    "duration_sec": 2.0,
}

FOLLOW_PARAMS = {
    "duration_sec": 10.0,
    "safe_distance_m": 1.0,
}

REPORT_MESSAGES = {
    "feeding": "feeding scenario completed",
    "play": "play scenario completed",
    "pet_monitoring": "pet monitoring completed",
    "vase_safety": (
        "vase is observe-only target. approach blocked for safety"
    ),
    "bed_check": "bed check completed",
    "chair_check": "chair check completed",
    "apple_check": "apple check completed",
    "ball_check": "ball check completed",
    "follow": "follow completed",
    "no_valid_target": "no valid target detected",
}

FEED_PARAMS = {
    "item": "apple",
}

LABEL_ALIAS = {
    "dog": "dog",
    "puppy": "dog",
    "강아지": "dog",
    "개": "dog",
    "cat": "cat",
    "고양이": "cat",
    "apple": "apple",
    "cup": "apple",
    "dish": "apple",
    "plate": "apple",
    "그릇": "apple",
    "밥그릇": "apple",
    "ball": "ball",
    "sports ball": "ball",
    "sports_ball": "ball",
    "공": "ball",
    "bed": "bed",
    "couch": "bed",
    "sofa": "bed",
    "침대": "bed",
    "chair": "chair",
    "의자": "chair",
    "vase": "vase",
    "plant": "vase",
    "airplane": "vase",
    "화분": "vase",
}

ACTION_ALIAS = {
    "approach": "approach",
    "move": "approach",
    "go": "approach",
    "navigate": "approach",
    "접근": "approach",
    "이동": "approach",
    "가까이": "approach",
    "observe": "observe",
    "watch": "observe",
    "check": "observe",
    "inspect": "observe",
    "관찰": "observe",
    "확인": "observe",
    "살펴": "observe",
    "search": "search",
    "find": "search",
    "look for": "search",
    "찾": "search",
    "어디": "search",
    "feed": "feed",
    "give food": "feed",
    "밥": "feed",
    "먹": "feed",
    "wait": "wait",
    "기다": "wait",
    "대기": "wait",
    "report": "report",
    "보고": "report",
    "알려": "report",
}

APPROACH_OBJECTS = {
    "dog",
    "cat",
    "apple",
    "ball",
    "bed",
    "chair",
}


# target.yaml에 고정 좌표가 있어서
# YOLO label 확인 후 해당 zone으로 이동 가능한 object
STATIC_APPROACH_OBJECTS = {
    "apple",
    "ball",
    "bed",
    "chair",
    "cat",
}

OBSERVE_OBJECTS = {
    "dog",
    "cat",
    "vase",
}
PLANNER_CONTRACT = """
You are a ROS2 pet-care robot action planner.

Your job:
- Understand the user's natural-language request.
- Infer the situation intent freely.
- Choose suitable objects and actions.
- Generate a multi-step action sequence that can be executed by the robot.

You are NOT selecting from fixed scenario templates.
You may create a new sequence for each user request.
However, every step must obey the executable action schema below.

Available objects:
- dog: pet target. Can be observed or followed.
- cat: pet target. Can be approached or observed.
- apple: food target. Can be approached.
- ball: toy target. Can be approached.
- bed: static location. Can be approached or observed.
- chair: static object. Can be approached or observed.
- vase: fragile object. Must NOT be approached. Observe only.

Available actions:
1. approach
   Purpose: move near the target object/location.
   Allowed objects: apple, ball, bed, chair, cat.
   Do NOT use approach for vase.
   Params:
   {
     "timeout_sec": 60.0,
     "goal_tolerance_m": 0.25,
     "retry_count": 2
   }

2. observe
   Purpose: look at or monitor the target.
   Allowed objects: dog, cat, apple, ball, bed, chair, vase.
   Params:
   {
     "duration_sec": 5.0
   }

3. wait
   Purpose: pause before the next action.
   Object must be null.
   Params:
   {
     "duration_sec": 2.0
   }

4. report
   Purpose: report the result to the user.
   Object must be null.
   Params:
   {
     "message": "<short English or Korean status message>"
   }

5. search
   Purpose: search for an object if the user explicitly asks to find/search it or if the object is not currently detected.
   Allowed objects: dog, cat, apple, ball, bed, chair, vase.
   Params:
   {
     "timeout_sec": 45.0,
     "duration_sec": 4.0,
     "retry_count": 0
   }

6. follow
   Purpose: keep a moving pet/person centered in the camera and follow slowly.
   Allowed objects: dog, cat, person.
   Params:
   {
     "duration_sec": 10.0,
     "safe_distance_m": 1.0
   }

Planning rules:
- Generate 1 to 5 steps.
- Always end with report.
- Do not invent unsupported actions.
- Do not invent unsupported objects.
- Do not output comments outside JSON.
- If the user asks for feeding, food, hunger, or meal care, include approach apple and observe dog.
- If the user asks for play or entertainment, include approach ball and observe dog.
- If the user asks to check or monitor a fragile object like vase, use observe vase and report. Never approach vase.
- If the user asks to follow or track a pet/person, search it first, then follow it, then report.
- If the user asks to check a specific static object, approach it first, then optionally observe it, then report.
- If the user explicitly asks to find/search something, use search before follow-up actions.
- If the user mentions multiple objects, create a sequence that visits or observes them in the user's requested order.
- Detected labels are auxiliary context only. If the user explicitly asks for an object, prioritize the user's request over detected labels.
"""


ACTION_SEQUENCE_SCHEMA = {
    "type": "object",
    "properties": {
        "comment": {
            "type": "string",
        },
        "sequence": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "step_id": {"type": "integer"},
                    "action": {
                        "type": "string",
                        "enum": ALLOWED_ACTIONS,
                    },
                    "object": {
                        "anyOf": [
                            {
                                "type": "string",
                                "enum": ALLOWED_OBJECTS,
                            },
                            {"type": "null"},
                        ]
                    },
                    "params": {
                        "type": "object",
                        "properties": {
                            "timeout_sec": {
                                "anyOf": [
                                    {"type": "number"},
                                    {"type": "null"},
                                ]
                            },
                            "goal_tolerance_m": {
                                "anyOf": [
                                    {"type": "number"},
                                    {"type": "null"},
                                ]
                            },
                            "retry_count": {
                                "anyOf": [
                                    {"type": "integer"},
                                    {"type": "null"},
                                ]
                            },
                            "duration_sec": {
                                "anyOf": [
                                    {"type": "number"},
                                    {"type": "null"},
                                ]
                            },
                            "safe_distance_m": {
                                "anyOf": [
                                    {"type": "number"},
                                    {"type": "null"},
                                ]
                            },
                            "message": {
                                "anyOf": [
                                    {"type": "string"},
                                    {"type": "null"},
                                ]
                            },
                            "item": {
                                "anyOf": [
                                    {"type": "string"},
                                    {"type": "null"},
                                ]
                            },
                        },
                        "required": [
                            "timeout_sec",
                            "goal_tolerance_m",
                            "retry_count",
                            "duration_sec",
                            "safe_distance_m",
                            "message",
                            "item",
                        ],
                        "additionalProperties": False,
                    },
                },
                "required": [
                    "step_id",
                    "action",
                    "object",
                    "params",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["comment", "sequence"],
    "additionalProperties": False,
}


def normalize_label(label: str | None) -> str | None:
    if label is None:
        return None

    normalized = str(label).lower().strip().replace("-", " ")
    normalized = normalized.replace("_", " ")

    if normalized.replace(" ", "_") in ALLOWED_OBJECTS:
        return normalized.replace(" ", "_")

    return LABEL_ALIAS.get(normalized)


def normalize_labels(labels: list[str] | tuple[str, ...] | None) -> list[str]:
    normalized = []

    for label in labels or []:
        object_name = normalize_label(label)
        if object_name and object_name not in normalized:
            normalized.append(object_name)

    return normalized


def normalize_action(action: str | None) -> str | None:
    if action is None:
        return None

    normalized = str(action).lower().strip()

    if normalized in ALLOWED_ACTIONS:
        return normalized

    for keyword, mapped_action in ACTION_ALIAS.items():
        if keyword in normalized:
            return mapped_action

    return None


def make_step(
    step_id: int,
    action: str,
    object_name: str | None = None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "step_id": step_id,
        "action": action,
        "object": object_name,
        "params": dict(params or {}),
    }


def approach_step(step_id: int, object_name: str) -> dict[str, Any]:
    return make_step(step_id, "approach", object_name, APPROACH_PARAMS)


def observe_step(step_id: int, object_name: str) -> dict[str, Any]:
    return make_step(step_id, "observe", object_name, OBSERVE_PARAMS)


def search_step(step_id: int, object_name: str) -> dict[str, Any]:
    return make_step(step_id, "search", object_name, SEARCH_PARAMS)


def feed_step(step_id: int, object_name: str, item: str = "apple") -> dict[str, Any]:
    return make_step(step_id, "feed", object_name, {"item": item})


def follow_step(step_id: int, object_name: str) -> dict[str, Any]:
    return make_step(step_id, "follow", object_name, FOLLOW_PARAMS)


def wait_step(step_id: int) -> dict[str, Any]:
    return make_step(step_id, "wait", None, WAIT_PARAMS)


def report_step(step_id: int, message: str) -> dict[str, Any]:
    return make_step(step_id, "report", None, {"message": message})


def feeding_sequence(pet_object: str = "dog", search_food: bool = False) -> list[dict[str, Any]]:
    sequence = []

    if search_food:
        sequence.append(search_step(len(sequence) + 1, "apple"))

    sequence.extend(
        [
            approach_step(len(sequence) + 1, "apple"),
            search_step(len(sequence) + 2, pet_object),
            feed_step(len(sequence) + 3, pet_object),
            report_step(len(sequence) + 4, REPORT_MESSAGES["feeding"]),
        ]
    )
    return sequence


def static_checks_then_feeding_sequence(
    static_objects: list[str],
    pet_object: str = "dog",
) -> list[dict[str, Any]]:
    sequence = []
    seen_static_objects = set()

    for object_name in static_objects:
        if object_name in seen_static_objects:
            continue
        seen_static_objects.add(object_name)
        sequence.append(approach_step(len(sequence) + 1, object_name))
        sequence.append(observe_step(len(sequence) + 1, object_name))

    sequence.append(approach_step(len(sequence) + 1, "apple"))
    sequence.append(search_step(len(sequence) + 1, pet_object))
    sequence.append(feed_step(len(sequence) + 1, pet_object))
    sequence.append(report_step(len(sequence) + 1, REPORT_MESSAGES["feeding"]))
    return sequence


def play_sequence() -> list[dict[str, Any]]:
    return [
        search_step(1, "ball"),
        approach_step(2, "ball"),
        search_step(3, "dog"),
        observe_step(4, "dog"),
        report_step(5, REPORT_MESSAGES["play"]),
    ]


def vase_safety_sequence() -> list[dict[str, Any]]:
    return [
        search_step(1, "vase"),
        observe_step(2, "vase"),
        report_step(3, REPORT_MESSAGES["vase_safety"]),
    ]


def static_multi_target_sequence() -> list[dict[str, Any]]:
    return multi_object_check_sequence(["apple", "bed", "chair"])


def pet_monitoring_sequence(object_name: str) -> list[dict[str, Any]]:
    return [
        search_step(1, object_name),
        observe_step(2, object_name),
        report_step(3, REPORT_MESSAGES["pet_monitoring"]),
    ]


def follow_sequence(object_name: str) -> list[dict[str, Any]]:
    return [
        search_step(1, object_name),
        follow_step(2, object_name),
        report_step(3, REPORT_MESSAGES["follow"]),
    ]


def multi_pet_monitoring_sequence(object_names: list[str]) -> list[dict[str, Any]]:
    sequence = []
    for object_name in object_names:
        sequence.append(search_step(len(sequence) + 1, object_name))
        sequence.append(observe_step(len(sequence) + 1, object_name))

    sequence.append(
        report_step(len(sequence) + 1, REPORT_MESSAGES["pet_monitoring"])
    )
    return sequence


def object_check_sequence(object_name: str) -> list[dict[str, Any]]:
    message_key = f"{object_name}_check"

    # YOLO로 먼저 object label을 확인한 뒤,
    # target.yaml에 정의된 해당 object zone으로 이동
    if object_name in STATIC_APPROACH_OBJECTS:
        return [
            approach_step(1, object_name),
            observe_step(2, object_name),
            report_step(
                3,
                REPORT_MESSAGES.get(
                    message_key,
                    f"{object_name} check completed",
                ),
            ),
        ]

    # dog/person처럼 고정 좌표가 없는 객체는 이동하지 않고 관찰/보고만 수행
    return [
        search_step(1, object_name),
        observe_step(2, object_name),
        report_step(
            3,
            REPORT_MESSAGES.get(
                message_key,
                f"{object_name} check completed",
            ),
        ),
    ]

def no_valid_target_sequence() -> list[dict[str, Any]]:
    return [
        wait_step(1),
        report_step(2, REPORT_MESSAGES["no_valid_target"]),
    ]


def has_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def search_requested(text: str) -> bool:
    return has_any(
        text,
        ["찾", "어디", "where", "find", "search", "look for", "locate"],
    )


OBJECT_REQUEST_KEYWORDS = [
    ("dog", ["dog", "puppy", "강아지", "개"]),
    ("cat", ["cat", "고양이"]),
    (
        "apple",
        [
            "apple",
            "사과",
            "밥",
            "급식",
            "먹이",
            "먹을",
            "배고",
            "food",
            "meal",
            "feed",
            "rice",
        ],
    ),
    ("ball", ["ball", "공", "장난감", "toy", "play"]),
    ("bed", ["bed", "침대"]),
    ("chair", ["chair", "의자"]),
    ("vase", ["vase", "화분", "plant", "potted"]),
]


def requested_objects_from_text(user_text: str) -> list[str]:
    text = (user_text or "").lower()
    requested = []

    for object_name, keywords in OBJECT_REQUEST_KEYWORDS:
        if object_name not in KNOWN_WORLD_OBJECTS:
            continue

        match_positions = [
            text.find(keyword)
            for keyword in keywords
            if keyword in text
        ]
        if match_positions:
            requested.append((min(match_positions), object_name))

    return [
        object_name
        for _, object_name in sorted(requested)
    ]


def sequence_object_names(sequence: list[dict[str, Any]]) -> set[str]:
    return {
        step["object"]
        for step in sequence
        if isinstance(step, dict)
        and step.get("action") in {"approach", "observe", "search", "follow"}
        and step.get("object")
    }


def multi_object_check_sequence(object_names: list[str]) -> list[dict[str, Any]]:
    sequence = []

    for object_name in object_names:
        if object_name in STATIC_APPROACH_OBJECTS:
            sequence.append(approach_step(len(sequence) + 1, object_name))
            sequence.append(observe_step(len(sequence) + 1, object_name))
        else:
            sequence.append(search_step(len(sequence) + 1, object_name))
            sequence.append(observe_step(len(sequence) + 1, object_name))

    sequence.append(
        report_step(
            len(sequence) + 1,
            "multi object check completed",
        )
    )

    return sequence


def smart_plan_sequence(
    user_text: str,
    detected_labels: list[str] | None,
) -> list[dict[str, Any]]:
    """
    Deterministic planner used as a local fallback and as a guardrail around
    LLM output. It maps requests to the predefined executor action vocabulary.
    """

    text = (user_text or "").lower()
    labels = set(normalize_labels(detected_labels))
    requested_objects = requested_objects_from_text(text)

    if "vase" in requested_objects:
        return vase_safety_sequence()

    if has_any(text, ["follow", "track", "따라", "쫓아", "추적"]):
        for candidate in ["dog", "cat", "person"]:
            if candidate in requested_objects:
                return follow_sequence(candidate)
        if "dog" in labels:
            return follow_sequence("dog")
        if "cat" in labels:
            return follow_sequence("cat")
        return follow_sequence("dog")

    if has_any(
        text,
        ["밥", "급식", "먹이", "먹을", "food", "meal", "feed", "rice", "배고"],
    ):
        pet_object = "cat" if "cat" in requested_objects else "dog"
        requested_static_targets = [
            object_name
            for object_name in requested_objects
            if object_name in {"bed", "chair", "ball"}
        ]
        if requested_static_targets:
            return static_checks_then_feeding_sequence(
                requested_static_targets,
                pet_object=pet_object,
            )
        return feeding_sequence(
            pet_object=pet_object,
            search_food=True,
        )

    if has_any(text, ["놀이", "놀아", "장난감", "공", "toy", "ball", "play", "심심"]):
        return play_sequence()

    requested_pets = [
        object_name
        for object_name in requested_objects
        if object_name in {"dog", "cat"}
    ]
    if len(requested_pets) > 1:
        return multi_pet_monitoring_sequence(requested_pets)

    requested_static_targets = [
        object_name
        for object_name in requested_objects
        if object_name in {"apple", "bed", "chair", "ball"}
    ]
    if len(requested_static_targets) > 1:
        return multi_object_check_sequence(requested_static_targets)

    multi_text = all(keyword in text for keyword in ["그릇", "침대", "의자"])
    if multi_text:
        return static_multi_target_sequence()

    static_target_keywords = [
        ("bed", ["침대", "bed"]),
        ("chair", ["의자", "chair"]),
        ("apple", ["사과", "apple", "그릇", "밥그릇"]),
        ("ball", ["공", "ball"]),
    ]

    for object_name, keywords in static_target_keywords:
        if has_any(text, keywords):
            return object_check_sequence(object_name)

    monitoring_requested = has_any(
        text,
        ["상태", "condition", "monitor", "관찰", "확인", "살펴", "체크"],
    )

    if has_any(text, ["강아지", "dog"]) and not labels.intersection(
        {"bed", "chair", "apple", "ball"}
    ):
        return pet_monitoring_sequence("dog")

    if has_any(text, ["고양이", "cat"]) and not labels.intersection(
        {"bed", "chair", "apple", "ball"}
    ):
        return pet_monitoring_sequence("cat")

    if "dog" in requested_objects:
        return pet_monitoring_sequence("dog")

    if "cat" in requested_objects:
        return pet_monitoring_sequence("cat")

    if "vase" in labels:
        return vase_safety_sequence()

    multi_labels = {"apple", "bed", "chair"}.issubset(labels)
    if multi_labels:
        return static_multi_target_sequence()

    if "dog" in labels and monitoring_requested:
        return pet_monitoring_sequence("dog")

    if "cat" in labels and monitoring_requested:
        return pet_monitoring_sequence("cat")

    for object_name, _ in static_target_keywords:
        if object_name in labels:
            return object_check_sequence(object_name)

    if "dog" in labels:
        return pet_monitoring_sequence("dog")

    if "cat" in labels:
        return pet_monitoring_sequence("cat")

    return no_valid_target_sequence()


def param_value(params: dict[str, Any], key: str, default: Any) -> Any:
    value = params.get(key)
    return default if value is None else value


def compact_params(action: str, params: dict[str, Any] | None) -> dict[str, Any]:
    params = params or {}

    if action == "approach":
        return {
            "timeout_sec": float(
                param_value(params, "timeout_sec", APPROACH_PARAMS["timeout_sec"])
            ),
            "goal_tolerance_m": float(
                param_value(
                    params,
                    "goal_tolerance_m",
                    APPROACH_PARAMS["goal_tolerance_m"],
                )
            ),
            "retry_count": int(
                param_value(params, "retry_count", APPROACH_PARAMS["retry_count"])
            ),
        }

    if action == "observe":
        return {
            "duration_sec": float(
                param_value(params, "duration_sec", OBSERVE_PARAMS["duration_sec"])
            ),
        }

    if action == "search":
        return {
            "timeout_sec": float(
                param_value(params, "timeout_sec", SEARCH_PARAMS["timeout_sec"])
            ),
            "duration_sec": float(
                param_value(params, "duration_sec", SEARCH_PARAMS["duration_sec"])
            ),
            "retry_count": int(
                param_value(params, "retry_count", SEARCH_PARAMS["retry_count"])
            ),
        }

    if action == "wait":
        return {
            "duration_sec": float(
                param_value(params, "duration_sec", WAIT_PARAMS["duration_sec"])
            ),
        }

    if action == "feed":
        return {
            "item": str(param_value(params, "item", FEED_PARAMS["item"])),
        }

    if action == "follow":
        return {
            "duration_sec": float(
                param_value(params, "duration_sec", FOLLOW_PARAMS["duration_sec"])
            ),
            "safe_distance_m": float(
                param_value(
                    params,
                    "safe_distance_m",
                    FOLLOW_PARAMS["safe_distance_m"],
                )
            ),
        }

    if action == "report":
        message = params.get("message") or "sequence completed"
        return {
            "message": str(message),
        }

    return {}


def is_valid_step(step: dict[str, Any]) -> bool:
    if validate_step is None or ActionStatus is None:
        action = step.get("action")
        object_name = step.get("object")

        if action not in ALLOWED_ACTIONS:
            return False

        if action in {"wait", "report"}:
            return object_name is None

        if action == "approach":
            return object_name in APPROACH_OBJECTS

        if action == "observe":
            return object_name in OBSERVE_OBJECTS

        if action == "feed":
            return object_name in {"dog", "cat"}

        if action == "search":
            return object_name in ALLOWED_OBJECTS

        if action == "follow":
            return object_name in {"dog", "cat", "person"}

        return False

    return validate_step(step) == ActionStatus.SUCCESS

def ensure_search_before_static_approach(
    sequence: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    expanded: list[dict[str, Any]] = []
    searched_objects: set[str] = set()

    for step in sequence:
        action = step.get("action")
        object_name = step.get("object")

        if (
            action == "approach"
            and object_name in STATIC_APPROACH_OBJECTS
            and object_name not in searched_objects
        ):
            expanded.append(
                search_step(
                    len(expanded) + 1,
                    object_name,
                )
            )
            searched_objects.add(object_name)

        expanded.append(
            {
                **step,
                "step_id": len(expanded) + 1,
            }
        )

        if action == "search" and object_name:
            searched_objects.add(object_name)

    return renumber_steps(expanded)


def ensure_chair_observe_after_approach(
    sequence: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    expanded: list[dict[str, Any]] = []

    for index, step in enumerate(sequence):
        expanded.append(step)

        if step.get("action") != "approach" or step.get("object") != "chair":
            continue

        next_step = sequence[index + 1] if index + 1 < len(sequence) else None
        if (
            isinstance(next_step, dict)
            and next_step.get("action") == "observe"
            and next_step.get("object") == "chair"
        ):
            continue

        expanded.append(observe_step(len(expanded) + 1, "chair"))

    return renumber_steps(expanded)


def renumber_steps(sequence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            **step,
            "step_id": index,
        }
        for index, step in enumerate(sequence, start=1)
    ]

def coerce_action_sequence(
    llm_output: dict[str, Any] | list[dict[str, Any]] | None,
    user_text: str = "",
    detected_labels: list[str] | None = None,
) -> list[dict[str, Any]]:
    if llm_output is None:
        return smart_plan_sequence(user_text, detected_labels)

    raw_sequence = llm_output.get("sequence", []) if isinstance(llm_output, dict) else llm_output

    if not isinstance(raw_sequence, list):
        return smart_plan_sequence(user_text, detected_labels)

    coerced: list[dict[str, Any]] = []

    for raw_step in raw_sequence:
        if not isinstance(raw_step, dict):
            continue

        action = normalize_action(raw_step.get("action"))
        object_name = normalize_label(raw_step.get("object"))
        params = raw_step.get("params")
        params = params if isinstance(params, dict) else {}

        if object_name == "vase" and action == "approach":
            return vase_safety_sequence()

        if action in {"wait", "report"}:
            object_name = None

        if action is None:
            if object_name == "vase":
                action = "observe"
            elif object_name in APPROACH_OBJECTS:
                action = "approach"
            elif object_name in ALLOWED_OBJECTS:
                action = "search"
            else:
                continue

        step = make_step(
            len(coerced) + 1,
            action,
            object_name,
            compact_params(action, params),
        )

        if is_valid_step(step):
            coerced.append(step)

    if not coerced:
        return smart_plan_sequence(user_text, detected_labels)

    requested_objects = set(requested_objects_from_text(user_text))
    planned_objects = sequence_object_names(coerced)
    if requested_objects and not requested_objects.issubset(planned_objects):
        return smart_plan_sequence(user_text, detected_labels)

    coerced = renumber_steps(coerced)
    coerced = ensure_chair_observe_after_approach(coerced)

    return renumber_steps(coerced)

def build_prompt(user_text: str, detected_labels: list[str]) -> str:
    normalized = normalize_labels(detected_labels)
    vase_safety_message = REPORT_MESSAGES["vase_safety"]

    return f"""
You are a ROS2 robot action planner for a pet-care robot.

Your role is to understand the Korean user request, infer the situation intent,
choose suitable objects and actions, and generate an executable action sequence.

Important:
- Do NOT simply classify the request into a fixed scenario.
- Do not only classify the request into a fixed scenario.
- You may freely build a scenario based on the user's request.
- You must decide the intermediate steps yourself.
- However, every step must obey the executable action/object rules below.
- The output will be executed directly by a ROS2 sequence executor.

Known world objects:
{KNOWN_WORLD_OBJECTS}

Allowed objects:
{ALLOWED_OBJECTS}

Allowed actions:
{ALLOWED_ACTIONS}

Action capabilities:
{json.dumps(ACTION_CAPABILITIES, ensure_ascii=False, indent=2)}

Detected objects after normalization:
{normalized}

User request:
{user_text}

Planning policy:
- Prefer the user's explicit request over automatic assumptions.
- Use detected objects only as visibility context.
- Do not choose a detected object as the task target when the user explicitly requested another known world object.
- Keep the sequence short, but include useful intermediate steps when needed.
- Always end with report.
- Use approach for reachable navigation targets when the robot should move near them.
- Use observe when the robot should check, monitor, inspect, or confirm the state of an object or pet.
- Use search only when the user explicitly asks to find/search/locate something, or when the task clearly depends on locating a pet first.
- Use follow when the user asks the robot to follow, track, or keep up with a moving pet/person.
- Use wait only when the user request implies a delay, pause, or waiting period.
- Use feed only when the user explicitly asks to feed the pet or the request clearly implies meal/food care.
- If the user requests multiple targets, preserve the requested order.
- If the user asks for an unsafe or impossible action, produce the safest executable alternative and explain it in report.

Object-specific rules:
- apple is treated as food.
- ball is treated as a toy.
- dog is the pet target. It can be searched, observed, fed, or followed.
- chair, bed, apple, ball, and cat are reachable targets.
- vase is fragile and observe-only.
- Never approach vase.
- If the user asks to approach vase, replace it with observe vase and report "{vase_safety_message}".
- object may be null only for wait and report.
- Do not invent objects outside the allowed object list.
- Do not invent actions outside the allowed action list.

Useful planning patterns:
- Feeding-like request:
  approach apple -> observe dog -> report
  If the request explicitly says to feed the dog, use feed dog after approaching apple.
- Play-like request:
  approach ball -> observe dog -> report
- Static object check:
  approach object -> observe object -> report
- Pet state check:
  search dog -> observe dog -> report
- Follow request:
  search dog -> follow dog -> report
- Vase safety check:
  observe vase -> report
- Multi-target request:
  follow the user's object order and use approach/observe as appropriate.

Examples of valid plans:
1. "강아지 밥 챙겨줘"
   approach apple -> observe dog -> report

2. "강아지한테 먹이 줘"
   approach apple -> feed dog -> observe dog -> report

3. "강아지가 심심해 보여. 공으로 놀아줘"
   approach ball -> observe dog -> report

4. "의자 확인해줘"
   approach chair -> observe chair -> report

5. "침대 보고 의자도 확인해줘"
   approach bed -> observe bed -> approach chair -> observe chair -> report

6. "강아지 어디 있는지 찾아서 상태 알려줘"
   search dog -> observe dog -> report

7. "꽃병으로 가까이 가줘"
   observe vase -> report

Output rules:
1. Return JSON only.
2. Do not wrap the JSON in markdown.
3. comment must be a short, natural Korean response.
4. Use only allowed objects and actions.
5. object may be null only for wait and report.
6. step_id must start from 1 and increase by 1.
7. approach params must include:
   timeout_sec=60.0, goal_tolerance_m=0.25, retry_count=2.
8. observe params must include:
   duration_sec=5.0.
9. search params must include:
   timeout_sec=45.0, duration_sec=4.0, retry_count=0.
10. wait params must include:
   duration_sec=2.0 unless the user requested a different duration.
11. feed params must include:
   item=apple unless requested otherwise.
12. follow params must include:
   duration_sec=10.0, safe_distance_m=1.0.
13. report params must include:
   message.
14. Include only params needed for that action. Do not add unused params with null.
15. If no executable plan can be made, return wait 2 seconds and report "no valid target detected".

Required JSON shape:
{{
  "comment": "short Korean comment",
  "sequence": [
    {{
      "step_id": 1,
      "action": "approach",
      "object": "apple",
      "params": {{
        "timeout_sec": 60.0,
        "goal_tolerance_m": 0.25,
        "retry_count": 2
      }}
    }},
    {{
      "step_id": 2,
      "action": "report",
      "object": null,
      "params": {{
        "message": "sequence completed"
      }}
    }}
  ]
}}
"""

ALLOWED_EXEC_OBJECTS = {"dog", "cat", "apple", "ball", "bed", "chair", "vase"}
ALLOWED_EXEC_ACTIONS = {"approach", "observe", "wait", "report", "search", "feed", "follow"}

APPROACH_OBJECTS = {"apple", "ball", "bed", "chair", "cat"}
OBSERVE_OBJECTS = {"dog", "cat", "apple", "ball", "bed", "chair", "vase"}
SEARCH_OBJECTS = {"dog", "cat", "apple", "ball", "bed", "chair", "vase"}
FEED_OBJECTS = {"dog"}
FOLLOW_OBJECTS = {"dog", "cat"}


def default_params_for_action(action: str) -> dict:
    if action == "approach":
        return {"timeout_sec": 60.0, "goal_tolerance_m": 0.25, "retry_count": 2}
    if action == "observe":
        return {"duration_sec": 5.0}
    if action == "search":
        return {"timeout_sec": 45.0, "duration_sec": 4.0, "retry_count": 0}
    if action == "wait":
        return {"duration_sec": 2.0}
    if action == "feed":
        return {"item": "apple"}
    if action == "follow":
        return {"duration_sec": 10.0, "safe_distance_m": 1.0}
    if action == "report":
        return {"message": "sequence completed"}
    return {}


def normalize_sequence_result(result: dict) -> dict:
    raw_sequence = result.get("sequence", [])
    normalized = []

    if not isinstance(raw_sequence, list):
        raw_sequence = []

    for step in raw_sequence:
        if not isinstance(step, dict):
            continue

        action = step.get("action")
        obj = step.get("object")

        if action not in ALLOWED_EXEC_ACTIONS:
            continue

        if obj is not None and obj not in ALLOWED_EXEC_OBJECTS:
            continue

        # Safety: vase must never be approached.
        if action == "approach" and obj == "vase":
            normalized.append({
                "step_id": len(normalized) + 1,
                "action": "observe",
                "object": "vase",
                "params": {"duration_sec": 5.0},
            })
            continue

        # Action-object validation.
        if action == "approach" and obj not in APPROACH_OBJECTS:
            continue

        if action == "observe" and obj not in OBSERVE_OBJECTS:
            continue

        if action == "search" and obj not in SEARCH_OBJECTS:
            continue

        if action == "feed" and obj not in FEED_OBJECTS:
            continue

        if action == "follow" and obj not in FOLLOW_OBJECTS:
            continue

        if action in {"wait", "report"}:
            obj = None

        params = default_params_for_action(action)
        raw_params = step.get("params", {})

        if isinstance(raw_params, dict):
            # Remove null values from LLM output.
            cleaned_params = {
                k: v for k, v in raw_params.items()
                if v is not None
            }
            params.update(cleaned_params)

        normalized.append({
            "step_id": len(normalized) + 1,
            "action": action,
            "object": obj,
            "params": params,
        })

    if not normalized:
        normalized.append({
            "step_id": 1,
            "action": "wait",
            "object": None,
            "params": {"duration_sec": 2.0},
        })
        normalized.append({
            "step_id": 2,
            "action": "report",
            "object": None,
            "params": {"message": "no valid target detected"},
        })

    if normalized[-1]["action"] != "report":
        normalized.append({
            "step_id": len(normalized) + 1,
            "action": "report",
            "object": None,
            "params": {"message": "sequence completed"},
        })

    return {
        "comment": result.get(
            "comment",
            "요청에 맞는 행동 시퀀스를 생성했습니다."
        ),
        "sequence": normalized,
    }

def parse_response_json(output_text: str) -> dict[str, Any]:
    output_text = output_text.strip()

    # 혹시 LLM이 ```json ... ``` 형태로 감싸서 주는 경우 제거
    if output_text.startswith("```"):
        output_text = output_text.strip("`")
        if output_text.startswith("json"):
            output_text = output_text[4:].strip()

    parsed = json.loads(output_text)

    if not isinstance(parsed, dict):
        raise ValueError("LLM output must be a JSON object")

    return normalize_sequence_result(parsed)


def call_llm_api(
    user_text: str,
    detected_labels: list[str],
    *,
    use_fallback: bool = True,
) -> dict[str, Any]:
    prompt = build_prompt(user_text, detected_labels)
    api_key = os.getenv("OPENAI_API_KEY")

    if OpenAI is None or not api_key:
        if not use_fallback:
            raise RuntimeError("OpenAI client or OPENAI_API_KEY is not available")
        return {
            "comment": "",
            "sequence": smart_plan_sequence(user_text, detected_labels),
            "planner": "fallback",
        }

    try:
        client = OpenAI(api_key=api_key)
        response = client.responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            input=prompt,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "action_sequence",
                    "schema": ACTION_SEQUENCE_SCHEMA,
                    "strict": True,
                }
            },
        )
        raw_result = parse_response_json(response.output_text)
        return {
            "comment": str(raw_result.get("comment") or ""),
            "sequence": coerce_action_sequence(
                raw_result,
                user_text=user_text,
                detected_labels=detected_labels,
            ),
            "planner": "openai",
        }

    except Exception as exc:
        if not use_fallback:
            raise
        return {
            "comment": "",
            "sequence": smart_plan_sequence(user_text, detected_labels),
            "planner": "fallback_after_error",
            "planner_error": str(exc),
        }


if __name__ == "__main__":
    result = call_llm_api("침대 확인해줘", ["bed"])

    print("===== ACTION SEQUENCE =====")
    print(json.dumps(result, indent=2, ensure_ascii=False))
