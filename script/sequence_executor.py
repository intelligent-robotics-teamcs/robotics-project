#!/usr/bin/env python3

import sys
from dataclasses import dataclass

try:
    from script import actions
    from script.action_schema import ActionStatus, validate_step
    from script.test_scenarios import SCENARIOS
except ImportError:
    import actions
    from action_schema import ActionStatus, validate_step
    from test_scenarios import SCENARIOS


RETRYABLE_STATUSES = {
    ActionStatus.FAILED,
    ActionStatus.TIMEOUT,
    ActionStatus.REJECTED,
}

NON_EXECUTABLE_STATUSES = {
    ActionStatus.INVALID_ACTION,
    ActionStatus.INVALID_OBJECT,
    ActionStatus.NOT_ALLOWED,
}


@dataclass
class StepResult:
    step_id: int | None
    action: str | None
    object_name: str | None
    status: ActionStatus
    attempts: int


class SequenceExecutor:
    """
    Scenario-level executor.

    Action functions stay small and return one ActionStatus. Retry, stop, and
    summary policy belongs here so individual actions do not manage sequence
    state.
    """

    def __init__(self):
        self._nav_node = None
        self._rclpy = None
        self.results: list[StepResult] = []

    def execute_scenario(self, scenario_name: str) -> ActionStatus:
        if scenario_name not in SCENARIOS:
            print(f"[ERROR] Unknown scenario: {scenario_name}")
            print(f"Available scenarios: {', '.join(sorted(SCENARIOS.keys()))}")
            return ActionStatus.INVALID_ACTION

        sequence = SCENARIOS[scenario_name]
        return self.execute_sequence(sequence, sequence_name=scenario_name)

    def execute_sequence(
        self,
        sequence: list[dict],
        sequence_name: str = "custom",
    ) -> ActionStatus:
        # TODO: Use this entry point from the future vision pipeline after
        # detections are converted into executor-compatible action steps.
        self.results = []

        print(f"[SEQUENCE] Start sequence: {sequence_name}")

        final_status = ActionStatus.SUCCESS

        try:
            for step in sequence:
                status = self.execute_step_with_retry(step)

                if status != ActionStatus.SUCCESS:
                    final_status = status
                    break
        finally:
            self.shutdown()
            self.print_summary(sequence_name, final_status)

        return final_status

    def execute_step_with_retry(self, step: dict) -> ActionStatus:
        retry_count = int(step.get("params", {}).get("retry_count", 0))
        max_attempts = retry_count + 1

        last_status = ActionStatus.FAILED

        for attempt in range(1, max_attempts + 1):
            print(
                "[STEP] "
                f"id={step.get('step_id')} "
                f"action={step.get('action')} "
                f"object={step.get('object')} "
                f"attempt={attempt}/{max_attempts}"
            )

            last_status = self.execute_step(step)

            if last_status == ActionStatus.SUCCESS:
                break

            if last_status in NON_EXECUTABLE_STATUSES:
                break

            if last_status not in RETRYABLE_STATUSES:
                break

        self.results.append(
            StepResult(
                step_id=step.get("step_id"),
                action=step.get("action"),
                object_name=step.get("object"),
                status=last_status,
                attempts=attempt,
            )
        )

        return last_status

    def execute_step(self, step: dict) -> ActionStatus:
        validation_status = validate_step(step)

        if validation_status != ActionStatus.SUCCESS:
            print(f"[VALIDATION] {validation_status.value}")
            return validation_status

        action = step["action"]

        if action == "approach":
            return self.execute_approach(step)
        if action == "wait":
            return self.execute_wait(step)
        if action == "observe":
            return self.execute_observe(step)
        if action == "report":
            return self.execute_report(step)
        if action == "follow":
            return self.execute_follow(step)

        return ActionStatus.INVALID_ACTION

    def execute_approach(self, step: dict) -> ActionStatus:
        params = step.get("params", {})
        nav_node = self._get_nav_node()

        return actions.approach_action(
            node=nav_node,
            object_name=step["object"],
            timeout_sec=float(params.get("timeout_sec", 60.0)),
            goal_tolerance_m=float(params.get("goal_tolerance_m", 0.25)),
        )

    def execute_wait(self, step: dict) -> ActionStatus:
        duration_sec = float(step.get("params", {}).get("duration_sec", 0.0))
        return actions.wait_action(duration_sec=max(duration_sec, 0.0))

    def execute_observe(self, step: dict) -> ActionStatus:
        duration_sec = float(step.get("params", {}).get("duration_sec", 0.0))
        object_name = step.get("object")
        return actions.observe_action(
            object_name=object_name,
            duration_sec=max(duration_sec, 0.0),
        )

    def execute_report(self, step: dict) -> ActionStatus:
        message = step.get("params", {}).get("message", "")
        return actions.report_action(message=message)

    def execute_follow(self, step: dict) -> ActionStatus:
        params = step.get("params", {})
        object_name = step.get("object")
        return actions.follow_action(
            object_name=object_name,
            duration_sec=max(float(params.get("duration_sec", 10.0)), 0.0),
            safe_distance_m=float(params.get("safe_distance_m", 1.0)),
        )

    def _get_nav_node(self):
        if self._nav_node is None:
            import rclpy

            try:
                from script.nav2_goal_sender import Nav2GoalSender
            except ImportError:
                from nav2_goal_sender import Nav2GoalSender

            if not rclpy.ok():
                rclpy.init(args=None)

            self._rclpy = rclpy
            self._nav_node = Nav2GoalSender()

        return self._nav_node

    def shutdown(self):
        if self._nav_node is not None:
            self._nav_node.destroy_node()
            self._nav_node = None

        if self._rclpy is not None and self._rclpy.ok():
            self._rclpy.shutdown()

        self._rclpy = None

    def print_summary(self, scenario_name: str, final_status: ActionStatus):
        print("")
        print(f"[SUMMARY] sequence={scenario_name} final_status={final_status.value}")

        for result in self.results:
            print(
                "[SUMMARY] "
                f"step_id={result.step_id} "
                f"action={result.action} "
                f"object={result.object_name} "
                f"status={result.status.value} "
                f"attempts={result.attempts}"
            )


def main(args=None):
    argv = list(sys.argv if args is None else args)

    if len(argv) < 2:
        print("Usage: ros2 run pet_robot_pkg sequence_executor <scenario_name>")
        print(f"Available scenarios: {', '.join(sorted(SCENARIOS.keys()))}")
        return

    scenario_name = argv[1]
    executor = SequenceExecutor()
    status = executor.execute_scenario(scenario_name)

    if status == ActionStatus.SUCCESS:
        return

    raise SystemExit(1)


if __name__ == "__main__":
    main()
