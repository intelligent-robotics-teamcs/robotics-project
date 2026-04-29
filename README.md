# Intelligent Robotics Project

아래 내용을 README.md에 그대로 붙여넣으면 돼.

# Intelligent Robotics Project
LLM + Vision 기반 자율 반려동물 케어 로봇 프로젝트입니다.
사용자의 자연어 입력을 LLM이 해석하고, YOLOv8 기반 객체 인식 결과와 결합하여 TurtleBot3가 적절한 행동을 수행하도록 하는 것을 목표로 합니다.
## Project Goal
사용자가 명시적인 명령을 내리지 않아도, 상황 설명을 기반으로 로봇이 필요한 행동을 판단합니다.

예시: '나 오늘 야근이라 강아지 밥 줄 사람이 없어'

예상 동작:

1. dog 또는 bowl 탐지
2. bowl 위치로 접근
3. dog 위치 확인
4. dog 상태 관찰

System Pipeline

User Input
→ LLM
→ Action Sequence
→ Executor
→ YOLOv8 Detection
→ Nav2 Navigation
→ TurtleBot3 / Gazebo

Repository Structure

Configuration Files

config/object.yaml

YOLO/COCO 기반으로 사용할 객체를 정의합니다.

예시 객체:

dog, cat, person, ball, chair, bed, bowl, car

각 객체는 COCO class ID, category, priority, description 정보를 가집니다.

config/action.yaml

로봇이 수행할 수 있는 action을 정의합니다.

현재 action:

approach: 객체 위치로 이동
observe: 객체 방향으로 회전 및 관찰
follow: 객체를 일정 거리로 추종

config/mapping.yaml

객체별로 가능한 action을 정의합니다.

예시:

dog → approach, observe, follow 가능
car → observe만 가능, approach/follow 금지

config/rules.yaml

target과 action command의 naming rule을 정의합니다.

예시:

target_object = dog
action_command = approach_dog

Test Script

test_pipeline.py는 config 파일들이 올바르게 연결되는지 확인하는 테스트 코드입니다.

실행:  python scripts/test_pipeline.py

테스트 내용:

객체 정의 확인
action 정의 확인
object-action mapping 확인
안전 규칙 확인

ROS Workspace

ROS 관련 코드는 추후 아래 구조로 관리합니다.

ros/
└── ros2_ws/
    └── src/
        └── pet_robot_pkg/

Ubuntu 환경에서 ROS2 패키지를 생성하고, Nav2, TurtleBot3, Gazebo, YOLOv8 연동을 진행할 예정입니다.

Current Status

* GitHub repository setup
* Basic project structure
* Object/action configuration
* Naming rule definition
* Initial system design document
* ROS2 workspace setup
* TurtleBot3 simulation setup
* Nav2 navigation test
* YOLOv8 integration
* LLM action sequence generation

Team 컴공

* 이경선
* 류다현

