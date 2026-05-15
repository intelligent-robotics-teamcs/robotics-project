#!/usr/bin/env python3

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource


def generate_launch_description():
    package_share_dir = get_package_share_directory("pet_robot_pkg")
    turtlebot3_share_dir = get_package_share_directory("turtlebot3_gazebo")
    world_path = os.path.join(
        package_share_dir,
        "worlds",
        "world_yolo_sanity_check",
    )
    model_path = os.path.join(turtlebot3_share_dir, "models")
    package_model_path = os.path.join(package_share_dir, "models")
    gazebo_model_path = os.environ.get("GAZEBO_MODEL_PATH", "")
    gazebo_model_paths = os.pathsep.join(
        path for path in [model_path, package_model_path, gazebo_model_path] if path
    )

    gazebo_launch = os.path.join(
        get_package_share_directory("gazebo_ros"),
        "launch",
        "gazebo.launch.py",
    )

    return LaunchDescription(
        [
            SetEnvironmentVariable("GAZEBO_MODEL_PATH", gazebo_model_paths),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(gazebo_launch),
                launch_arguments={"world": world_path}.items(),
            )
        ]
    )
