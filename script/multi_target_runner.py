#!/usr/bin/env python3

import argparse
import time
from pathlib import Path

import yaml
import rclpy

try:
    from script.nav2_goal_sender import Nav2GoalSender
except ImportError:
    from nav2_goal_sender import Nav2GoalSender


def load_navigation_policy():
    """
    Load navigation policy from config/navigation_policy.yaml.

    If the file does not exist, use safe default values.
    """
    default_policy = {
        "timeout_sec": 60.0,
        "retry_count": 2,
        "goal_tolerance_m": 0.25,
        "wait_between_targets_sec": 1.0,
    }

    current_file = Path(__file__).resolve()
    package_root = current_file.parent.parent
    config_path = package_root / "config" / "navigation_policy.yaml"

    if not config_path.exists():
        return default_policy

    with open(config_path, "r", encoding="utf-8") as f:
        loaded = yaml.safe_load(f)

    if loaded is None:
        return default_policy

    navigation_policy = loaded.get("navigation", {})

    return {
        "timeout_sec": float(
            navigation_policy.get(
                "timeout_sec",
                default_policy["timeout_sec"]
            )
        ),
        "retry_count": int(
            navigation_policy.get(
                "retry_count",
                default_policy["retry_count"]
            )
        ),
        "goal_tolerance_m": float(
            navigation_policy.get(
                "goal_tolerance_m",
                default_policy["goal_tolerance_m"]
            )
        ),
        "wait_between_targets_sec": float(
            navigation_policy.get(
                "wait_between_targets_sec",
                default_policy["wait_between_targets_sec"]
            )
        ),
    }


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run multi-target navigation sequence."
    )

    parser.add_argument(
        "objects",
        nargs="+",
        help="Object names to visit in order. Example: bowl bed chair"
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Timeout seconds for each target."
    )

    parser.add_argument(
        "--retry",
        type=int,
        default=None,
        help="Retry count for each target."
    )

    parser.add_argument(
        "--tolerance",
        type=float,
        default=None,
        help="Goal tolerance in meters."
    )

    parser.add_argument(
        "--continue-on-fail",
        action="store_true",
        help="Continue to next target even if current target fails."
    )

    return parser.parse_args()


def run_target_with_retry(
    node: Nav2GoalSender,
    object_name: str,
    timeout_sec: float,
    retry_count: int,
    goal_tolerance_m: float
):
    """
    Try to navigate to one target.

    attempt count:
    - first trial = attempt 1
    - retry_count=2 means total attempts = 3
    """
    total_attempts = retry_count + 1

    last_result = None

    for attempt in range(1, total_attempts + 1):
        node.get_logger().info(
            f"===== Target '{object_name}' attempt "
            f"{attempt}/{total_attempts} ====="
        )

        result = node.navigate_to_object(
            object_name=object_name,
            timeout_sec=timeout_sec,
            goal_tolerance_m=goal_tolerance_m
        )

        last_result = result

        if result.success:
            node.get_logger().info(
                f"Target '{object_name}' succeeded on attempt {attempt}."
            )
            return result

        node.get_logger().warn(
            f"Target '{object_name}' failed on attempt {attempt}: "
            f"{result.state.value} / {result.message}"
        )

        if attempt < total_attempts:
            node.get_logger().info(
                f"Retrying target '{object_name}'..."
            )
            time.sleep(1.0)

    return last_result


def main(args=None):
    parsed_args = parse_args()

    policy = load_navigation_policy()

    timeout_sec = (
        parsed_args.timeout
        if parsed_args.timeout is not None
        else policy["timeout_sec"]
    )

    retry_count = (
        parsed_args.retry
        if parsed_args.retry is not None
        else policy["retry_count"]
    )

    goal_tolerance_m = (
        parsed_args.tolerance
        if parsed_args.tolerance is not None
        else policy["goal_tolerance_m"]
    )

    wait_between_targets_sec = policy["wait_between_targets_sec"]

    rclpy.init(args=args)

    node = Nav2GoalSender()

    sequence_results = []

    try:
        node.get_logger().info("===== Multi-target navigation started =====")
        node.get_logger().info(f"Target sequence: {parsed_args.objects}")
        node.get_logger().info(
            f"Policy: timeout={timeout_sec}, "
            f"retry={retry_count}, "
            f"tolerance={goal_tolerance_m}"
        )

        for object_name in parsed_args.objects:
            result = run_target_with_retry(
                node=node,
                object_name=object_name,
                timeout_sec=timeout_sec,
                retry_count=retry_count,
                goal_tolerance_m=goal_tolerance_m
            )

            sequence_results.append(result)

            if not result.success:
                node.get_logger().error(
                    f"Target '{object_name}' finally failed."
                )

                if not parsed_args.continue_on_fail:
                    node.get_logger().error(
                        "Stopping sequence because current target failed."
                    )
                    break

            time.sleep(wait_between_targets_sec)

        node.get_logger().info("===== Multi-target navigation finished =====")

        print("\n===== Navigation Summary =====")
        for idx, result in enumerate(sequence_results, start=1):
            print(
                f"{idx}. {result.object_name} "
                f"-> {result.state.value} "
                f"/ target={result.target_name} "
                f"/ min_distance={result.min_distance_remaining} "
                f"/ message={result.message}"
            )

    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
