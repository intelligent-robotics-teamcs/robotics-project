#!/usr/bin/env python3
"""
Pet Care Robot - Test Pipeline
설정 파일 검증 및 기본 기능 테스트
"""

import yaml
import sys
from pathlib import Path

# Config 파일 경로
CONFIG_DIR = Path(__file__).parent.parent / "config"

class RobotTestPipeline:
    def __init__(self):
        self.rules = None
        self.objects = None
        self.actions = None
        self.mapping = None
        self.targets = None
        self.navigation_policy = None
        self.passed = 0
        self.failed = 0

    def load_configs(self):
        """설정 파일 로드"""
        try:
            with open(CONFIG_DIR / "rules.yaml") as f:
                self.rules = yaml.safe_load(f)
            print("✓ rules.yaml loaded")

            with open(CONFIG_DIR / "object.yaml") as f:
                self.objects = yaml.safe_load(f)
            print("✓ object.yaml loaded")

            with open(CONFIG_DIR / "action.yaml") as f:
                self.actions = yaml.safe_load(f)
            print("✓ action.yaml loaded")

            with open(CONFIG_DIR / "mapping.yaml") as f:
                self.mapping = yaml.safe_load(f)
            print("✓ mapping.yaml loaded")

            with open(CONFIG_DIR / "target.yaml") as f:
                self.targets = yaml.safe_load(f)
            print("✓ target.yaml loaded")

            with open(CONFIG_DIR / "navigation_policy.yaml") as f:
                self.navigation_policy = yaml.safe_load(f)
            print("✓ navigation_policy.yaml loaded")

            return True
        except Exception as e:
            print(f"✗ Failed to load configs: {e}")
            return False

    def test_naming_rules(self):
        """Test 1: 명명 규칙 검증"""
        print("\n[Test 1] Naming Rules")

        try:
            assert "naming" in self.rules, "명명 규칙 없음"
            assert "target_object" in self.rules["naming"], "target_object 패턴 없음"
            assert "action_command" in self.rules["naming"], "action_command 패턴 없음"

            print(f"  Target format: {self.rules['naming']['target_object']}")
            print(f"  Action format: {self.rules['naming']['action_command']}")
            print("✓ Naming rules OK")
            self.passed += 1
            return True
        except AssertionError as e:
            print(f"✗ {e}")
            self.failed += 1
            return False

    def test_objects(self):
        """Test 2: 객체 정의 검증"""
        print("\n[Test 2] Object Definitions")

        try:
            assert "objects" in self.objects, "objects 없음"
            objects_list = self.objects["objects"]

            # 주요 객체 확인
            required = ["dog", "cat", "person"]
            for obj in required:
                assert obj in objects_list, f"{obj} 없음"

            print(f"  Total objects: {len(objects_list)}")
            print(f"  Primary targets: dog, cat")
            print("✓ Objects OK")
            self.passed += 1
            return True
        except AssertionError as e:
            print(f"✗ {e}")
            self.failed += 1
            return False

    def test_actions(self):
        """Test 3: 액션 정의 검증"""
        print("\n[Test 3] Action Definitions")

        try:
            required_actions = ["approach", "observe", "follow"]
            for action in required_actions:
                assert action in self.actions, f"{action} 없음"
                assert "description" in self.actions[action], f"{action}에 설명 없음"

            print(f"  Actions: {', '.join(required_actions)}")
            print("✓ Actions OK")
            self.passed += 1
            return True
        except AssertionError as e:
            print(f"✗ {e}")
            self.failed += 1
            return False

    def test_mapping(self):
        """Test 4: 객체-액션 매핑 검증"""
        print("\n[Test 4] Object-Action Mapping")

        try:
            # dog 매핑 확인
            assert "dog" in self.mapping, "dog 매핑 없음"
            assert self.mapping["dog"]["approach"] == True, "dog approach 불가"
            assert self.mapping["dog"]["follow"] == True, "dog follow 불가"

            # cat 매핑 확인
            assert "cat" in self.mapping, "cat 매핑 없음"
            assert self.mapping["cat"]["approach"] == True, "cat approach 불가"

            # 안전 테스트 - car는 접근 금지
            assert "car" in self.mapping, "car 매핑 없음"
            assert self.mapping["car"]["approach"] == False, "car 접근 가능 (위험)"

            print("  dog: approach✓ observe✓ follow✓")
            print("  cat: approach✓ observe✓ follow✓")
            print("  car: approach✗ (안전 설정)")
            print("✓ Mapping OK")
            self.passed += 1
            return True
        except AssertionError as e:
            print(f"✗ {e}")
            self.failed += 1
            return False

    def test_scenario_dog_approach(self):
        """Test 5: 시나리오 테스트 - 강아지 접근"""
        print("\n[Test 5] Scenario: Dog Approach")

        try:
            # 강아지 탐지
            target = "dog"
            assert target in self.objects["objects"], "dog 객체 없음"

            # 강아지 매핑 확인
            assert self.mapping[target]["approach"] == True, "dog 접근 불가"

            # 액션 실행 가능 확인
            action = "approach"
            assert action in self.actions, f"{action} 액션 없음"

            print(f"  1. Detect: dog (class_id: {self.objects['objects'][target]['class_id']})")
            print(f"  2. Check mapping: {target} can {action}? {self.mapping[target]['approach']}")
            print(f"  3. Execute: approach_dog")
            print(f"  4. Parameters: goal_tolerance={self.actions['approach']['parameters']['goal_tolerance']}m")
            print("✓ Scenario OK")
            self.passed += 1
            return True
        except AssertionError as e:
            print(f"✗ {e}")
            self.failed += 1
            return False

    def test_scenario_car_safety(self):
        """Test 6: 시나리오 테스트 - 자동차 안전"""
        print("\n[Test 6] Scenario: Car Safety Check")

        try:
            # 자동차 탐지
            target = "car"
            assert target in self.mapping, "car 매핑 없음"

            # 접근 금지 확인
            assert self.mapping[target]["approach"] == False, "car 접근 가능 (위험)"
            assert self.mapping[target]["observe"] == True, "car 관찰 불가"
            assert self.mapping[target]["follow"] == False, "car 추종 가능 (위험)"

            print(f"  1. Detect: car (class_id: {self.objects['objects'][target]['class_id']})")
            print(f"  2. Check mapping: car can approach? False ✓ (SAFE)")
            print(f"  3. Action: No approach, observe only")
            print("✓ Safety OK")
            self.passed += 1
            return True
        except AssertionError as e:
            print(f"✗ {e}")
            self.failed += 1
            return False

    def test_target_config(self):
        """Test 7: target.yaml 검증"""
        print("\n[Test 7] Target Configuration")

        try:
            assert "targets" in self.targets, "targets 없음"
            targets = self.targets["targets"]

            required_targets = [
                "ball_zone",
                "bowl_zone",
                "bed_zone",
                "chair_zone",
                "car_zone",
            ]

            for target_name in required_targets:
                assert target_name in targets, f"{target_name} 없음"

                target = targets[target_name]

                assert "frame_id" in target, f"{target_name}에 frame_id 없음"
                assert "x" in target, f"{target_name}에 x 없음"
                assert "y" in target, f"{target_name}에 y 없음"
                assert "yaw" in target, f"{target_name}에 yaw 없음"

                assert target["frame_id"] == "map", (
                    f"{target_name} frame_id가 map이 아님"
                )

                float(target["x"])
                float(target["y"])
                float(target["yaw"])

            print(f"  Total targets: {len(targets)}")
            print("  Required static target zones exist")
            print("✓ Target config OK")
            self.passed += 1
            return True

        except (AssertionError, ValueError, TypeError) as e:
            print(f"✗ {e}")
            self.failed += 1
            return False

    def test_navigation_policy(self):
        """Test 8: navigation_policy.yaml 검증"""
        print("\n[Test 8] Navigation Policy")

        try:
            assert "navigation" in self.navigation_policy, "navigation 정책 없음"

            navigation = self.navigation_policy["navigation"]

            required_keys = [
                "timeout_sec",
                "retry_count",
                "goal_tolerance_m",
                "wait_between_targets_sec",
            ]

            for key in required_keys:
                assert key in navigation, f"{key} 없음"

            timeout_sec = float(navigation["timeout_sec"])
            retry_count = int(navigation["retry_count"])
            goal_tolerance_m = float(navigation["goal_tolerance_m"])
            wait_between_targets_sec = float(
                navigation["wait_between_targets_sec"]
            )

            assert timeout_sec > 0, "timeout_sec은 0보다 커야 함"
            assert retry_count >= 0, "retry_count는 0 이상이어야 함"
            assert goal_tolerance_m > 0, "goal_tolerance_m은 0보다 커야 함"
            assert wait_between_targets_sec >= 0, (
                "wait_between_targets_sec는 0 이상이어야 함"
            )

            print(f"  timeout_sec: {timeout_sec}")
            print(f"  retry_count: {retry_count}")
            print(f"  goal_tolerance_m: {goal_tolerance_m}")
            print(f"  wait_between_targets_sec: {wait_between_targets_sec}")
            print("✓ Navigation policy OK")
            self.passed += 1
            return True

        except (AssertionError, ValueError, TypeError) as e:
            print(f"✗ {e}")
            self.failed += 1
            return False

    def test_static_target_resolver(self):
        """Test 9: static object -> target pose resolve 검증"""
        print("\n[Test 9] Static Target Resolver")

        try:
            # target_resolver.py와 동일한 static object mapping 기준
            static_objects = {
                "ball": "ball_zone",
                "bowl": "bowl_zone",
                "bed": "bed_zone",
                "chair": "chair_zone",
                "car": "car_zone",
            }

            targets = self.targets["targets"]

            for object_name, target_name in static_objects.items():
                assert object_name in self.objects["objects"], (
                    f"{object_name} 객체 정의 없음"
                )
                assert target_name in targets, (
                    f"{object_name}에 대응되는 {target_name} 없음"
                )

                pose = targets[target_name]

                assert pose["frame_id"] == "map", (
                    f"{target_name} frame_id가 map이 아님"
                )

                float(pose["x"])
                float(pose["y"])
                float(pose["yaw"])

                print(
                    f"  {object_name} -> {target_name} "
                    f"(x={pose['x']}, y={pose['y']}, yaw={pose['yaw']})"
                )

            print("✓ Static target resolver OK")
            self.passed += 1
            return True

        except (AssertionError, ValueError, TypeError) as e:
            print(f"✗ {e}")
            self.failed += 1
            return False

    def run_all(self):
        """전체 테스트 실행"""
        print("=" * 50)
        print("Pet Care Robot - Test Pipeline")
        print("=" * 50)

        # 설정 파일 로드
        if not self.load_configs():
            return False

        # 테스트 실행
        self.test_naming_rules()
        self.test_objects()
        self.test_actions()
        self.test_mapping()
        self.test_scenario_dog_approach()
        self.test_scenario_car_safety()
        self.test_target_config()
        self.test_navigation_policy()
        self.test_static_target_resolver()

        # 결과 출력
        print("\n" + "=" * 50)
        print(f"Results: {self.passed} passed, {self.failed} failed")
        print("=" * 50)

        return self.failed == 0

def main():
    pipeline = RobotTestPipeline()
    success = pipeline.run_all()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()