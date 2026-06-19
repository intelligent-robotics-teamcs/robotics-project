# 지능형 반려동물 케어 로봇

## 팀 정보

| 항목 | 내용 |
| --- | --- |
| 팀명 | Team컴공 |
| 팀원 | 이경선(2271107[@LeeKyoungSun](https://github.com/LeeKyoungSun)), 류다현(2376087[@rlyryu](https://github.com/rlyryu)) |
| 프로젝트 주제 | LLM + Vision을 활용한 상황 인지 기반 자율 반려동물 케어 로봇 시스템 |

## 프로젝트 설명

사용자가 자연어로 상황을 입력하면 LLM planner가 의도를 해석하고, YOLOv8 기반 vision node가 Gazebo 카메라 이미지에서 객체를 인식한 뒤, TurtleBot3가 필요한 대상 위치로 이동하거나 관찰, 대기, 보고 같은 action sequence를 수행하는 ROS 2 프로젝트입니다.

최종 구현은 map/Nav2 의존을 줄이고 `/odom` 기반 위치 추정과 `/cmd_vel` 직접 제어를 중심으로 구성했습니다. `approach` action은 Gazebo에서 발행되는 `/odom`으로 현재 로봇 위치와 방향을 읽고, `config/target.yaml`에 정의된 demo target zone까지 선속도와 각속도 명령을 publish하여 이동합니다. 따라서 별도의 map localization이나 Nav2 bringup 없이도 E2E demo를 실행할 수 있습니다.

전체 흐름은 다음과 같습니다.

```text
User request
  -> LLM sequence planner
  -> /vision/action_sequence
  -> sequence executor
  -> odom-based approach / observe / wait / feed / report
  -> /cmd_vel

Camera image
  -> YOLOv8 detector
  -> /vision/detections
  -> LLM planner and search action

Gazebo odometry
  -> /odom
  -> direct odom controller
```

## 역할 분담

프로젝트 제안서의 주차별 역할 분담을 기준으로 최종 구현에 맞춰 정리했습니다.

| 구분 | 담당 |
| --- | --- |
| 공통 | ROS 2, Gazebo, TurtleBot3 환경 구축, GitHub 저장소 세팅, action/object/target naming rule 정의, 테스트 시나리오 작성, demo 제작 및 발표 준비 |
| 이경선 | target 좌표 및 goal pose 구조 구현, 단일 action 함수 구현, Gazebo camera topic 처리 및 이미지 전처리, LLM prompt 설계 및 action sequence 생성 로직 구현 |
| 류다현 | 이동 결과 판정, timeout/retry 처리, 다중 target 테스트, sequence executor 및 action 상태 관리 구현, YOLO inference 연결, LLM JSON parsing 및 executor 입력 변환 |

## AI 사용 여부

AI를 사용했습니다.

| 구분 | 사용 내용 |
| --- | --- |
| Human work | 프로젝트 목표와 시나리오 설계, ROS/Gazebo 실행 환경 구성, object/action schema 결정, target 좌표 조정, 실제 시뮬레이션 실행 및 결과 확인, 최종 demo 흐름 판단 |
| AI-assisted work | ROS node 구현 중 반복적인 boilerplate 작성 보조, LLM output JSON parsing 로직 초안 작성, executor 상태 관리 로직 점검, 디버깅 로그 분석, 오류 원인 추적, 테스트 케이스 구성 보조, README 및 문서 정리 |

AI는 구현을 자동으로 대체하기보다, 디버깅과 로그 분석, 반복적인 코드 작성, edge case 점검처럼 시간이 많이 드는 작업을 줄이는 보조 도구로 사용했습니다. 최종 구조 결정과 시뮬레이션 검증은 팀원이 직접 수행했습니다.

## 주요 기능

- 자연어 요청을 predefined action sequence로 변환
  - OpenAI API 사용 가능
  - `OPENAI_API_KEY`가 없으면 deterministic fallback planner 사용
- YOLOv8 기반 카메라 객체 인식
  - 입력: `/camera/image_raw`
  - 출력: `/vision/raw_detections`, `/vision/detections`, `/vision/yolo_debug`
- odom 기반 직접 주행
  - 현재 위치: `/odom`
  - 제어 명령: `/cmd_vel`
  - 목표 좌표: `config/target.yaml`
- action sequence 실행
  - 지원 action: `approach`, `search`, `observe`, `feed`, `follow`, `wait`, `report`
  - action별 success, fail, timeout 상태 관리
- Gazebo sanity world
  - TurtleBot3 Waffle Pi
  - camera, lidar, odom plugin
  - dog, cat, bed, chair, vase, apple 테스트 모델 포함

## 기술 스택

- ROS 2 Humble
- Gazebo Classic
- TurtleBot3 Waffle Pi
- Python / rclpy
- OpenCV / cv_bridge
- Ultralytics YOLOv8
- OpenAI Responses API
- YAML 기반 object, action, target 설정

## 디렉토리 구조

```text
.
├── config/
│   ├── action.yaml
│   ├── mapping.yaml
│   ├── navigation_policy.yaml
│   ├── object.yaml
│   ├── rules.yaml
│   └── target.yaml
├── docs/
├── images/
├── launch/
│   ├── yolo_sanity_check.launch.py
│   └── yolo_nav_e2e.launch.py
├── models/
├── script/
│   ├── actions.py
│   ├── action_schema.py
│   ├── camera_image_processor.py
│   ├── sequence_executor.py
│   ├── target_resolver.py
│   ├── vision_schema.py
│   ├── vision_sequence_executor.py
│   ├── yolo_detector.py
│   ├── llm/
│   └── sanity_checks/
├── worlds/
│   └── world_yolo_sanity_check
├── package.xml
├── setup.py
├── fastdds_no_shm.xml
└── yolov8n.pt
```

## 실행 방법

WSL2 + Ubuntu 22.04 + ROS 2 Humble 환경을 기준으로 합니다.

### 1. 의존성 설치

```bash
sudo apt update
sudo apt install -y \
  ros-humble-gazebo-ros-pkgs \
  ros-humble-turtlebot3 \
  ros-humble-turtlebot3-gazebo \
  ros-humble-turtlebot3-description \
  ros-humble-cv-bridge \
  python3-pip

pip3 install ultralytics openai python-dotenv PyYAML
```

OpenAI API를 사용할 경우:

```bash
export OPENAI_API_KEY=<your_api_key>
export OPENAI_MODEL=gpt-4.1-mini
```

### 2. 빌드

```bash
cd ~/ros2_clean_ws
colcon build --symlink-install
source install/setup.bash
```

### 3. 공통 환경 변수

```bash
export TURTLEBOT3_MODEL=waffle_pi
export ROS_DOMAIN_ID=0
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ROS_LOCALHOST_ONLY=0
export ROS_DISABLE_LOANED_MESSAGES=1
export FASTRTPS_DEFAULT_PROFILES_FILE=$PWD/fastdds_no_shm.xml
```

### 4. Gazebo world 실행

터미널 1:

```bash
source /opt/ros/humble/setup.bash
source install/setup.bash

ros2 launch pet_robot_pkg yolo_sanity_check.launch.py
```

### 5. Vision + LLM + odom executor 실행

터미널 2:

```bash
source /opt/ros/humble/setup.bash
source install/setup.bash

ros2 launch pet_robot_pkg yolo_nav_e2e.launch.py \
  camera_topic:=/camera/image_raw \
  model_path:=yolov8n.pt \
  confidence_threshold:=0.25 \
  enable_display:=false \
  require_user_request:=true
```

### 6. 사용자 요청 입력

터미널 3:

```bash
source /opt/ros/humble/setup.bash
source install/setup.bash

ros2 run pet_robot_pkg agent_console
```

예시 입력:

```text
user: 사과를 찾고 확인해줘
user: 강아지가 배고픈지 봐줘. 밥도 줘
user: 꽃병에는 가까이 가지 말고 관찰만 해줘
```

topic으로 직접 요청할 수도 있습니다.

```bash
ros2 topic pub --once /llm/user_request std_msgs/msg/String \
  "{data: '{\"text\":\"사과를 찾고 확인해줘\"}'}"
```

## 단독 실행 및 테스트

미리 정의된 sequence 실행:

```bash
ros2 run pet_robot_pkg sequence_executor feeding
ros2 run pet_robot_pkg sequence_executor static_multi_target
ros2 run pet_robot_pkg sequence_executor vase_safety
```

YOLO 이미지 sanity check:

```bash
ros2 run pet_robot_pkg run_yolo_inference -- --image images/apple.jpg
```

파이프라인 테스트:

```bash
python3 script/sanity_checks/test_pipeline.py
python3 script/llm/test_llm_sequence_generator.py
```

## 주요 Topic

| Topic | Type | 설명 |
| --- | --- | --- |
| `/camera/image_raw` | `sensor_msgs/msg/Image` | Gazebo camera image |
| `/vision/raw_detections` | `std_msgs/msg/String` | YOLO 원본 detection JSON |
| `/vision/detections` | `std_msgs/msg/String` | 필터링된 detection JSON |
| `/vision/yolo_debug` | `std_msgs/msg/String` | YOLO/frame debug 정보 |
| `/llm/user_request` | `std_msgs/msg/String` | 사용자 자연어 요청 |
| `/llm/agent_response` | `std_msgs/msg/String` | planner 응답 및 실행 흐름 |
| `/vision/action_sequence` | `std_msgs/msg/String` | 실행할 action sequence JSON |
| `/vision/execution_status` | `std_msgs/msg/String` | executor 시작/종료 상태 |
| `/cmd_vel` | `geometry_msgs/msg/Twist` | odom 기반 직접 제어 속도 명령 |
| `/odom` | `nav_msgs/msg/Odometry` | Gazebo odometry |
| `/scan` | `sensor_msgs/msg/LaserScan` | Gazebo lidar |

## Target 설정

`config/target.yaml`의 `*_zone`은 객체 중심 좌표가 아니라 로봇이 충돌 없이 접근할 수 있는 approach point입니다. odom 기반 approach는 이 좌표를 목표점으로 사용하고, `/odom` 기준 현재 위치와의 거리 및 heading error를 계산해 `/cmd_vel`을 publish합니다.

현재 정적 target:

- `apple -> apple_zone`
- `bed -> bed_zone`
- `chair -> chair_zone`
- `cat -> cat_zone`
- `vase -> vase_zone`
- `safe_observe -> safe_observe_zone`

`dog`, `person` 같은 동적 target은 vision detection 결과를 중심으로 관찰하거나 search action에서 사용합니다.

## 참고 자료

**Package & Documentation**
- LLM 기반 ROS2 control framework: https://github.com/Auromix/ROS-LLM/tree/ros2-humble
- EdgeYOLO + ROS2 package: https://github.com/fateshelled/EdgeYOLO-ROS
- Vav2 documentation: https://docs.nav2.org/
- E2E pick & place manipulation package (optional): https://github.com/ros-industrial/easy_manipulation_deployment
- LLM API-ROS2 interface extension: https://github.com/fujitatomoya/ros2ai


**실제 프로젝트 reference**
- ROS2 Humble + Gazebo Fortress + Nav2 example: https://github.com/art-e-fact/navigation2_ignition_gazebo_example
- ROS2 기반 LLM + YOLO → turtlebot control project: https://storyofkwan.tistory.com/category/ROS2%20%ED%94%84%EB%A1%9C%EC%A0%9D%ED%8A%B8/LLM%2BROS2%2BGAZEBO%20Control
- How to Use YOLOv8 with ROS2: https://www.youtube.com/watch?v=XqibXP4lwgA
- Home robot simulation tutorial: https://blog.kaia.ai/gazebo-3d-simulation-tutorial/

- 노션 팀스페이스: https://www.notion.so/48ba56ed4d1c8263bb00815b41e31c97?source=copy_link
  - 작업 과정, 디버깅 기록 등 포함 

## YouTube 링크

https://www.youtube.com/watch?v=5xdgA-GXf4c

## GitHub 링크

https://github.com/intelligent-robotics-teamcs/robotics-project
