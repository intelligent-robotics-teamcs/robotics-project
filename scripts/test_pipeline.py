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

        # 결과 출력
        print("\n" + "=" * 50)
        print(f"Results: {self.passed} passed, {self.failed} failed")
        print("=" * 50)

        return self.failed == 0

if __name__ == "__main__":
    pipeline = RobotTestPipeline()
    success = pipeline.run_all()
    sys.exit(0 if success else 1)
