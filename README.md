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


