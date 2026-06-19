#!/usr/bin/env python3

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, SetEnvironmentVariable
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    enable_initial_scan = LaunchConfiguration("enable_initial_scan")
    scan_angular_speed = LaunchConfiguration("scan_angular_speed")
    scan_duration_sec = LaunchConfiguration("scan_duration_sec")
    scan_start_delay_sec = LaunchConfiguration("scan_start_delay_sec")
    enable_moving_pets = LaunchConfiguration("enable_moving_pets")
    pet_motion_speed = LaunchConfiguration("pet_motion_speed")
    pet_motion_update_rate = LaunchConfiguration("pet_motion_update_rate")

    package_share_dir = get_package_share_directory("pet_robot_pkg")
    turtlebot3_share_dir = get_package_share_directory("turtlebot3_gazebo")
    turtlebot3_description_dir = get_package_share_directory("turtlebot3_description")
    turtlebot3_model = os.environ.get("TURTLEBOT3_MODEL", "waffle_pi")
    world_path = os.path.join(
        package_share_dir,
        "worlds",
        "world_yolo_sanity_check",
    )
    urdf_path = os.path.join(
        turtlebot3_description_dir,
        "urdf",
        f"turtlebot3_{turtlebot3_model}.urdf",
    )
    robot_description = Command(["xacro ", urdf_path])
    model_path = os.path.join(turtlebot3_share_dir, "models")
    package_model_path = os.path.join(package_share_dir, "models")
    source_model_path = os.path.abspath(
        os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "models")
    )
    gazebo_model_path = os.environ.get("GAZEBO_MODEL_PATH", "")
    candidate_model_paths = [
        model_path,
        package_model_path,
        source_model_path,
        gazebo_model_path,
    ]
    unique_model_paths = []
    for path in candidate_model_paths:
        if path and path not in unique_model_paths:
            unique_model_paths.append(path)
    gazebo_model_paths = os.pathsep.join(
        path for path in unique_model_paths if path
    )

    gazebo_launch = os.path.join(
        get_package_share_directory("gazebo_ros"),
        "launch",
        "gazebo.launch.py",
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "enable_initial_scan",
                default_value="true",
            ),
            DeclareLaunchArgument(
                "scan_angular_speed",
                default_value="0.18",
            ),
            DeclareLaunchArgument(
                "scan_duration_sec",
                default_value="0.0",
            ),
            DeclareLaunchArgument(
                "scan_start_delay_sec",
                default_value="3.0",
            ),
            DeclareLaunchArgument(
                "enable_moving_pets",
                default_value="false",
            ),
            DeclareLaunchArgument(
                "pet_motion_speed",
                default_value="0.06",
            ),
            DeclareLaunchArgument(
                "pet_motion_update_rate",
                default_value="10.0",
            ),
            SetEnvironmentVariable("GAZEBO_MODEL_PATH", gazebo_model_paths),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(gazebo_launch),
                launch_arguments={"world": world_path}.items(),
            ),
            Node(
                package="robot_state_publisher",
                executable="robot_state_publisher",
                name="robot_state_publisher",
                output="screen",
                parameters=[
                    {
                        "use_sim_time": True,
                        "robot_description": robot_description,
                    }
                ],
            ),
            Node(
                package="pet_robot_pkg",
                executable="initial_scan_rotator",
                name="initial_scan_rotator",
                output="screen",
                condition=IfCondition(enable_initial_scan),
                parameters=[
                    {
                        "angular_speed": scan_angular_speed,
                        "duration_sec": scan_duration_sec,
                        "start_delay_sec": scan_start_delay_sec,
                    }
                ],
            ),
            Node(
                package="pet_robot_pkg",
                executable="moving_pet_targets",
                name="moving_pet_targets",
                output="screen",
                condition=IfCondition(enable_moving_pets),
                parameters=[
                    {
                        "speed_mps": pet_motion_speed,
                        "cat_speed_mps": pet_motion_speed,
                        "update_rate_hz": pet_motion_update_rate,
                    }
                ],
            ),
        ]
    )
