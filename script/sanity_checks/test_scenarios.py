FEEDING_SCENARIO = [
    {
        "step_id": 1,
        "action": "approach",
        "object": "apple",
        "params": {
            "timeout_sec": 60.0,
            "goal_tolerance_m": 0.25,
            "retry_count": 2,
        },
    },
    {
        "step_id": 2,
        "action": "wait",
        "object": None,
        "params": {
            "duration_sec": 2.0,
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
            "message": "feeding scenario completed",
        },
    },
]


PLAY_SCENARIO = [
    {
        "step_id": 1,
        "action": "approach",
        "object": "ball",
        "params": {
            "timeout_sec": 60.0,
            "goal_tolerance_m": 0.25,
            "retry_count": 2,
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
        "action": "report",
        "object": None,
        "params": {
            "message": "play scenario completed",
        },
    },
]


VASE_SAFETY_SCENARIO = [
    {
        "step_id": 1,
        "action": "observe",
        "object": "vase",
        "params": {
            "duration_sec": 5.0,
        },
    },
    {
        "step_id": 2,
        "action": "report",
        "object": None,
        "params": {
            "message": (
                "vase is observe-only target. "
                "approach blocked for safety"
            ),
        },
    },
]


STATIC_MULTI_TARGET_SCENARIO = [
    {
        "step_id": 1,
        "action": "approach",
        "object": "apple",
        "params": {
            "timeout_sec": 60.0,
            "goal_tolerance_m": 0.25,
            "retry_count": 2,
        },
    },
    {
        "step_id": 2,
        "action": "approach",
        "object": "bed",
        "params": {
            "timeout_sec": 60.0,
            "goal_tolerance_m": 0.25,
            "retry_count": 2,
        },
    },
    {
        "step_id": 3,
        "action": "approach",
        "object": "chair",
        "params": {
            "timeout_sec": 60.0,
            "goal_tolerance_m": 0.25,
            "retry_count": 2,
        },
    },
    {
        "step_id": 4,
        "action": "observe",
        "object": "chair",
        "params": {
            "duration_sec": 5.0,
        },
    },
]


CHAIR_CHECK_SCENARIO = [
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
            "message": "chair check completed",
        },
    },
]


INVALID_VASE_APPROACH_SCENARIO = [
    {
        "step_id": 1,
        "action": "approach",
        "object": "vase",
        "params": {
            "timeout_sec": 60.0,
            "goal_tolerance_m": 0.25,
            "retry_count": 2,
        },
    }
]


SCENARIOS = {
    "feeding": FEEDING_SCENARIO,
    "play": PLAY_SCENARIO,
    "vase_safety": VASE_SAFETY_SCENARIO,
    "static_multi_target": STATIC_MULTI_TARGET_SCENARIO,
    "chair_check": CHAIR_CHECK_SCENARIO,
    "invalid_vase_approach": INVALID_VASE_APPROACH_SCENARIO,
}
