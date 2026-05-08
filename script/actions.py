#!/usr/bin/env python3

from __future__ import annotations

import time
from typing import TYPE_CHECKING

try:
    from script.action_schema import ActionStatus
except ImportError:
    from action_schema import ActionStatus

if TYPE_CHECKING:
    try:
        from script.nav2_goal_sender import Nav2GoalSender
    except ImportError:
        from nav2_goal_sender import Nav2GoalSender


def approach_action(
    node: Nav2GoalSender,
    object_name: str,
    timeout_sec: float = 60.0,
    goal_tolerance_m: float = 0.25,
) -> ActionStatus:
    """
    target object 위치로 한 번 이동하는 action.
    retry는 sequence_executor에서 담당
    """

    node.get_logger().info(f"[APPROACH] start approach to {object_name}")

    result = node.navigate_to_object(
        object_name=object_name,
        timeout_sec=timeout_sec,
        goal_tolerance_m=goal_tolerance_m,
    )

    if result.success:
        node.get_logger().info(f"[APPROACH] {object_name} SUCCESS")
        return ActionStatus.SUCCESS

    node.get_logger().warn(
        f"[APPROACH] {object_name} failed: {result.state.value}"
    )

    if result.state.value == "TIMEOUT":
        return ActionStatus.TIMEOUT

    if result.state.value == "REJECTED":
        return ActionStatus.REJECTED

    return ActionStatus.FAILED


def wait_action(duration_sec: float = 3.0) -> ActionStatus:
    """
    지정된 시간 동안 대기하는 action
    """

    print(f"[WAIT] waiting for {duration_sec} sec")
    time.sleep(duration_sec)
    return ActionStatus.SUCCESS


def observe_action(
    object_name: str,
    duration_sec: float = 5.0,
) -> ActionStatus:
    """
    object를 관찰하는 action
    아직 Vision 미연동 상태이므로 placeholder로 구현
    """

    print(f"[OBSERVE] observing {object_name} for {duration_sec} sec")
    time.sleep(duration_sec)
    print(f"[OBSERVE] {object_name} observation finished")
    return ActionStatus.SUCCESS


def follow_action(
    object_name: str,
    duration_sec: float = 10.0,
    safe_distance_m: float = 1.0,
) -> ActionStatus:
    """
    object를 따라가는 action
    Vision 연동 전까지는 실제 구현하지 않고 SKIPPED 반환
    """

    print(
        f"[FOLLOW] follow {object_name} for {duration_sec} sec "
        f"with safe distance {safe_distance_m} m"
    )
    print("[FOLLOW] not implemented yet. skipped.")
    return ActionStatus.SKIPPED


def report_action(message: str = "sequence completed") -> ActionStatus:
    """
    현재 상태나 결과 메시지를 출력하는 action
    """

    print(f"[REPORT] {message}")
    return ActionStatus.SUCCESS
