#!/usr/bin/env python3

try:
    from script.vision_schema import filter_detections
    from script.vision_to_executor import build_sequence_from_detections
    from script.yolo_detector import parse_ultralytics_result
except ImportError:
    from vision_schema import filter_detections
    from vision_to_executor import build_sequence_from_detections
    from yolo_detector import parse_ultralytics_result


class FakeTensor:
    def __init__(self, values):
        self.values = values

    def detach(self):
        return self

    def cpu(self):
        return self

    def tolist(self):
        return self.values


class FakeBoxes:
    xyxy = FakeTensor([[10, 20, 110, 220], [200, 100, 260, 160]])
    conf = FakeTensor([0.91, 0.84])
    cls = FakeTensor([16, 32])


class FakeResult:
    names = {
        16: "dog",
        32: "sports ball",
    }
    boxes = FakeBoxes()


def test_parse_ultralytics_result_to_project_sequence():
    raw_detections = parse_ultralytics_result(FakeResult())
    filtered_detections = filter_detections(raw_detections)
    sequence = build_sequence_from_detections(filtered_detections)

    assert raw_detections[0]["label"] == "dog"
    assert raw_detections[0]["class_id"] == 16
    assert raw_detections[0]["bbox"]["x1"] == 10.0
    assert filtered_detections[0]["label"] == "dog"
    assert sequence == [
        {
            "step_id": 1,
            "action": "observe",
            "object": "dog",
            "params": {"duration_sec": 5.0},
        }
    ]


if __name__ == "__main__":
    test_parse_ultralytics_result_to_project_sequence()
    print("test_parse_ultralytics_result_to_project_sequence OK")
