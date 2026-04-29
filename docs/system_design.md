## Overview

자율 반려동물 케어 로봇의 기본 구성

## Architecture
```
Camera → YOLOv8 Detection → COCO Class → Action Execution
                              ↓
                         Object Mapping
                              ↓
                    Nav2 Navigation Stack
```

## Configuration Files

### 1. rules.yaml
- **Object naming**: `dog`, `cat`, `person`
- **Action naming**: `approach_dog`, `follow_cat`, etc.
- **COCO Class ID**: 클래스 번호 매핑

### 2. object.yaml
추적할 객체 8가지:
- **dog** (class 16) - 주요 타겟 
- **cat** (class 15) - 주요 타겟 
- **person** (class 0) - 소유자 추종
- **ball** (class 32) - 놀이용
- **chair** (class 56) - 장애물
- **bed** (class 59) - 위치 추적
- **bowl** (class 45) - 밥그릇 위치
- **car** (class 2) - 위험 (접근 금지)

### 3. action.yaml
3가지 액션:

#### approach
- **목표**: 객체 위치로 이동
- **시간**: ~10초
- **오차범위**: ±0.5m

#### observe
- **목표**: 제자리에서 대상 방향으로 회전
- **시간**: 1-5초
- **각도오차**: ±5도

#### follow
- **목표**: 움직이는 대상 추종
- **거리**: 1.0m 유지
- **속도**: 0.8 m/s

### 4. mapping.yaml
각 객체별 가능한 액션:

| 객체 | approach | observe | follow | 비고 |
|------|----------|---------|--------|------|
| dog | ✓ | ✓ | ✓ | 주요 타겟 |
| cat | ✓ | ✓ | ✓ | 주요 타겟 |
| person | ✓ | ✓ | ✓ | 소유자 |
| ball | ✓ | ✓ | ✓ | 장난감 |
| chair | ✓ | ✓ | ✗ | 정적 |
| bed | ✓ | ✓ | ✗ | 정적 |
| bowl | ✓ | ✓ | ✗ | 정적 |
| car | ✗ | ✓ | ✗ | 위험 |

## Usage Example

### 시나리오: 강아지 발견 후 접근

```
1. 입력: 카메라 영상
2. 탐지: YOLOv8 → "Class 16 detected (dog)"
3. 인식: COCO mapping → "dog"
4. 매핑 확인: mapping.yaml → approach=true, observe=true, follow=true
5. 실행: approach_dog 명령 전송
6. 네비게이션: Nav2로 dog 위치로 이동
7. 완료: 0.5m 거리 내에 도달
```

### 시나리오: 자동차 감지

```
1. 탐지: "Class 2 detected (car)"
2. 매핑 확인: mapping.yaml → approach=false (금지)
3. 결과: 경고 메시지, 접근 안함
```

## Implementation Status

- [x] Configuration files defined
- [ ] YOLOv8 ROS integration
- [ ] Nav2 setup
- [ ] Action server implementation
- [ ] Testing & validation

## Next Steps

1. **Setup**: ROS 2 + Nav2 + YOLOv8 환경 구축
2. **Integration**: Config 파일 로드 및 ROS parameter 설정
3. **Testing**: Dog detection 및 approach 테스트
4. **Validation**: Follow action 테스트

## File Structure

```
config/
  ├── rules.yaml       (명명 규칙)
  ├── object.yaml      (객체 정의)
  ├── action.yaml      (액션 정의)
  └── mapping.yaml     (객체-액션 매핑)

docs/
  └── system_design.md (이 문서)
```

---

**Created**: 2026-04-29  
**Version**: 1.0 (Minimal)
