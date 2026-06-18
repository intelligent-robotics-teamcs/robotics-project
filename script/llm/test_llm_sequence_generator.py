#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path

try:
    from script.llm.llm_sequence_generator import (
        build_prompt,
        coerce_action_sequence,
        smart_plan_sequence,
    )
except ImportError:
    from llm_sequence_generator import (
        build_prompt,
        coerce_action_sequence,
        smart_plan_sequence,
    )


def load_cases() -> list[dict]:
    case_file = Path(__file__).with_name("test_cases.json")
    return json.loads(case_file.read_text(encoding="utf-8"))


def without_search_steps(sequence: list[dict]) -> list[dict]:
    return [
        {
            **step,
            "step_id": index,
        }
        for index, step in enumerate(
            [
                step
                for step in sequence
                if step.get("action") != "search"
            ],
            start=1,
        )
    ]


def test_smart_planner_cases():
    for case in load_cases():
        actual = smart_plan_sequence(
            case["user_text"],
            case["detected_labels"],
        )
        assert without_search_steps(actual) == case["expected_sequence"], case["scenario"]


def test_coerce_blocks_vase_approach():
    actual = coerce_action_sequence(
        {
            "sequence": [
                {
                    "step_id": 99,
                    "action": "approach",
                    "object": "vase",
                    "params": {
                        "timeout_sec": 10.0,
                        "goal_tolerance_m": 0.1,
                        "retry_count": 0,
                    },
                }
            ]
        },
        user_text="꽃병으로 가까이 가줘",
        detected_labels=["vase"],
    )

    assert without_search_steps(actual) == load_cases()[2]["expected_sequence"]


def test_coerce_fills_executor_params_and_step_ids():
    actual = coerce_action_sequence(
        {
            "sequence": [
                {
                    "step_id": 7,
                    "action": "navigate",
                    "object": "chair",
                    "params": {},
                },
                {
                    "step_id": 8,
                    "action": "report",
                    "object": "chair",
                    "params": {"message": "done"},
                },
            ]
        },
        user_text="의자 쪽을 확인해줘",
        detected_labels=["chair"],
    )

    assert actual == [
        {
            "step_id": 1,
            "action": "approach",
            "object": "chair",
            "params": {
                "timeout_sec": 60.0,
                "goal_tolerance_m": 0.25,
                "retry_count": 2,
            },
        },
        {
            "step_id": 2,
            "action": "observe",
            "object": "chair",
            "params": {
                "duration_sec": 5.0,
            },
        },
        {
            "step_id": 3,
            "action": "report",
            "object": None,
            "params": {
                "message": "done",
            },
        },
    ]


def test_coerce_preserves_llm_multi_step_plan():
    actual = coerce_action_sequence(
        {
            "sequence": [
                {
                    "step_id": 10,
                    "action": "approach",
                    "object": "bed",
                    "params": {"retry_count": 1},
                },
                {
                    "step_id": 20,
                    "action": "wait",
                    "object": None,
                    "params": {"duration_sec": 3.0},
                },
                {
                    "step_id": 30,
                    "action": "observe",
                    "object": "dog",
                    "params": {},
                },
                {
                    "step_id": 40,
                    "action": "report",
                    "object": None,
                    "params": {"message": "custom plan completed"},
                },
            ]
        },
        user_text="check the bed, wait, then observe the dog",
        detected_labels=["bed", "dog"],
    )

    assert actual == [
        {
            "step_id": 1,
            "action": "approach",
            "object": "bed",
            "params": {
                "timeout_sec": 60.0,
                "goal_tolerance_m": 0.25,
                "retry_count": 1,
            },
        },
        {
            "step_id": 2,
            "action": "wait",
            "object": None,
            "params": {
                "duration_sec": 3.0,
            },
        },
        {
            "step_id": 3,
            "action": "observe",
            "object": "dog",
            "params": {
                "duration_sec": 5.0,
            },
        },
        {
            "step_id": 4,
            "action": "report",
            "object": None,
            "params": {
                "message": "custom plan completed",
            },
        },
    ]


def test_user_request_targets_override_visible_vase():
    actual = smart_plan_sequence(
        "강아지랑 고양이 어디 있는지 찾아봐",
        ["vase"],
    )

    assert actual == [
        {
            "step_id": 1,
            "action": "search",
            "object": "dog",
            "params": {
                "timeout_sec": 45.0,
                "duration_sec": 4.0,
                "retry_count": 0,
            },
        },
        {
            "step_id": 2,
            "action": "observe",
            "object": "dog",
            "params": {
                "duration_sec": 5.0,
            },
        },
        {
            "step_id": 3,
            "action": "search",
            "object": "cat",
            "params": {
                "timeout_sec": 45.0,
                "duration_sec": 4.0,
                "retry_count": 0,
            },
        },
        {
            "step_id": 4,
            "action": "observe",
            "object": "cat",
            "params": {
                "duration_sec": 5.0,
            },
        },
        {
            "step_id": 5,
            "action": "report",
            "object": None,
            "params": {
                "message": "pet monitoring completed",
            },
        },
    ]


def test_feeding_cat_searches_food_then_cat():
    actual = smart_plan_sequence(
        "먹을 거 찾아서 고양이 밥 줘",
        ["vase"],
    )

    assert [
        (step["action"], step["object"])
        for step in actual
    ] == [
        ("search", "apple"),
        ("approach", "apple"),
        ("search", "cat"),
        ("feed", "cat"),
        ("report", None),
    ]


def test_hungry_dog_uses_food_then_feed_action():
    actual = smart_plan_sequence(
        "먹을 거 없어? 강아지가 배고픈 것 같은데",
        [],
    )

    assert [
        (step["action"], step["object"])
        for step in actual
    ] == [
        ("search", "apple"),
        ("approach", "apple"),
        ("search", "dog"),
        ("feed", "dog"),
        ("report", None),
    ]
    assert actual[3]["params"] == {"item": "apple"}


def test_where_is_vase_searches_before_observe():
    actual = smart_plan_sequence(
        "Where's a vase?",
        [],
    )

    assert [
        (step["action"], step["object"])
        for step in actual
    ] == [
        ("search", "vase"),
        ("observe", "vase"),
        ("report", None),
    ]


def test_follow_request_uses_follow_action():
    actual = smart_plan_sequence(
        "강아지를 천천히 따라가",
        ["dog"],
    )

    assert [
        (step["action"], step["object"])
        for step in actual
    ] == [
        ("search", "dog"),
        ("follow", "dog"),
        ("report", None),
    ]
    assert actual[1]["params"] == {
        "duration_sec": 10.0,
        "safe_distance_m": 1.0,
    }


def test_coerce_rejects_detected_object_plan_when_user_requested_other_targets():
    actual = coerce_action_sequence(
        {
            "sequence": [
                {
                    "step_id": 1,
                    "action": "observe",
                    "object": "vase",
                    "params": {},
                },
                {
                    "step_id": 2,
                    "action": "report",
                    "object": None,
                    "params": {"message": "vase checked"},
                },
            ]
        },
        user_text="강아지랑 고양이 어디 있는지 찾아봐",
        detected_labels=["vase"],
    )

    assert [step["object"] for step in actual if step["action"] == "observe"] == [
        "dog",
        "cat",
    ]


def test_prompt_requests_intermediate_step_planning():
    prompt = build_prompt(
        "침대 확인하고 잠시 기다린 다음 강아지 상태 알려줘",
        ["bed", "dog"],
    )

    assert "Known world objects" in prompt
    assert "Action capabilities" in prompt
    assert "search" in prompt
    assert "feed" in prompt
    assert "comment must be a short, natural Korean response" in prompt
    assert "Use detected objects only as visibility context" in prompt
    assert "You must decide the intermediate steps yourself" in prompt
    assert "Do not only classify the" in prompt
    assert "If the user requests multiple targets, preserve the requested order" in prompt


def main():
    test_smart_planner_cases()
    test_coerce_blocks_vase_approach()
    test_coerce_fills_executor_params_and_step_ids()
    test_coerce_preserves_llm_multi_step_plan()
    test_user_request_targets_override_visible_vase()
    test_feeding_cat_searches_food_then_cat()
    test_hungry_dog_uses_food_then_feed_action()
    test_where_is_vase_searches_before_observe()
    test_follow_request_uses_follow_action()
    test_coerce_rejects_detected_object_plan_when_user_requested_other_targets()
    test_prompt_requests_intermediate_step_planning()
    print("LLM sequence generator tests passed")


if __name__ == "__main__":
    main()
