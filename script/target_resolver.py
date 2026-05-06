import yaml
from pathlib import Path


class TargetResolver:
    """
    Resolve object -> navigation pose

    static object:
        predefined pose lookup

    dynamic object:
        perception module pose lookup
    """

    STATIC_OBJECTS = {
        "ball": "ball_zone",
        "bowl": "bowl_zone",
        "bed": "bed_zone",
        "chair": "chair_zone",
        "car": "car_zone",
    }

    DYNAMIC_OBJECTS = {
        "dog",
        "cat",
        "person",
    }

    def __init__(self, target_config="../config/target.yaml"):
        config_path = Path(__file__).resolve().parent / target_config

        with open(config_path, "r", encoding="utf-8") as f:
            self.targets = yaml.safe_load(f)["targets"]

    def get_pose(self, object_name):
        """
        Main resolver entry
        """

        # static object
        if object_name in self.STATIC_OBJECTS:
            return self._resolve_static(object_name)

        # dynamic object
        if object_name in self.DYNAMIC_OBJECTS:
            return self._resolve_dynamic(object_name)

        raise ValueError(f"Unknown object: {object_name}")

    def _resolve_static(self, object_name):
        """
        static object -> predefined pose
        """

        target_name = self.STATIC_OBJECTS[object_name]

        if target_name not in self.targets:
            raise ValueError(f"Undefined target: {target_name}")

        pose = self.targets[target_name]

        return {
            "type": "static",
            "object": object_name,
            "target": target_name,
            "pose": pose,
        }

    def _resolve_dynamic(self, object_name):
        """
        dynamic object -> live perception pose
        """

        # =====================================================
        # TODO:
        # perception module integration point
        #
        # expected pipeline:
        #
        # YOLO detect object
        # -> bbox center
        # -> depth estimation
        # -> robot frame coordinate
        # -> TF transform to map frame
        # -> current pose estimate
        #
        # expected return:
        # {
        #     "frame_id": "map",
        #     "x": ...,
        #     "y": ...,
        #     "yaw": ...
        # }
        # =====================================================

        live_pose = self._get_live_object_pose(object_name)

        return {
            "type": "dynamic",
            "object": object_name,
            "target": "live_detection",
            "pose": live_pose,
        }

    def _get_live_object_pose(self, object_name):
        """
        Placeholder for perception module
        """

        raise NotImplementedError(
            f"[TODO] perception module should provide live pose for '{object_name}'"
        )


if __name__ == "__main__":
    resolver = TargetResolver()

    test_objects = [
        "bowl",
        "bed",
        "chair",
        "car",
    ]

    for obj in test_objects:
        result = resolver.get_pose(obj)
        print(result)