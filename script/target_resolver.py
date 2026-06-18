import yaml
from pathlib import Path

try:
    from ament_index_python.packages import get_package_share_directory
except ImportError:
    get_package_share_directory = None


class TargetResolver:
    """
    Resolve object -> navigation pose

    static object:
        predefined pose lookup

    dynamic object:
        perception module pose lookup
    """

    STATIC_OBJECTS = {
        "safe_observe": "safe_observe_zone",
        "ball": "ball_zone",
        "apple": "apple_zone",
        "bed": "bed_zone",
        "chair": "chair_zone",
        "cat": "cat_zone",
        "vase": "vase_zone",
    }

    DYNAMIC_OBJECTS = {
        "dog",
        "person",
    }

    def __init__(self, target_config="../config/target.yaml"):
        config_path = self._resolve_config_path(target_config)
        self.config_path = config_path

        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        self.targets = data["targets"]
        self.object_centers = data.get("object_centers", {})

    def _resolve_config_path(self, target_config: str) -> Path:
        requested_path = Path(target_config)

        if requested_path.is_absolute() and requested_path.exists():
            return requested_path

        if get_package_share_directory is not None:
            try:
                share_path = Path(get_package_share_directory("pet_robot_pkg"))
                share_config = share_path / "config" / "target.yaml"
                if share_config.exists():
                    return share_config
            except Exception:
                pass

        relative_path = Path(__file__).resolve().parent / target_config
        if relative_path.exists():
            return relative_path

        for parent in Path(__file__).resolve().parents:
            workspace_config = parent / "config" / "target.yaml"
            if workspace_config.exists():
                return workspace_config

        return relative_path

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

    def get_object_center(self, object_name):
        """
        Return the actual object center pose, separate from approach zones.
        """

        if object_name not in self.object_centers:
            raise ValueError(f"Undefined object center: {object_name}")

        return self.object_centers[object_name]

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
        "apple",
        "bed",
        "chair",
        "cat",
        "vase",
        "apple",
    ]

    for obj in test_objects:
        result = resolver.get_pose(obj)
        print(result)
