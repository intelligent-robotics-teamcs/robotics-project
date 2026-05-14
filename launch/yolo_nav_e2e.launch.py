#!/usr/bin/env python3

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    camera_topic = LaunchConfiguration("camera_topic")
    model_path = LaunchConfiguration("model_path")
    confidence_threshold = LaunchConfiguration("confidence_threshold")
    enable_display = LaunchConfiguration("enable_display")
    execute_once = LaunchConfiguration("execute_once")

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "camera_topic",
                default_value="/camera/image_raw",
            ),
            DeclareLaunchArgument(
                "model_path",
                default_value="yolov8n.pt",
            ),
            DeclareLaunchArgument(
                "confidence_threshold",
                default_value="0.25",
            ),
            DeclareLaunchArgument(
                "enable_display",
                default_value="false",
            ),
            DeclareLaunchArgument(
                "execute_once",
                default_value="true",
            ),
            Node(
                package="pet_robot_pkg",
                executable="camera_image_processor",
                name="camera_image_processor",
                output="screen",
                parameters=[
                    {
                        "camera_topic": camera_topic,
                        "model_path": model_path,
                        "confidence_threshold": confidence_threshold,
                        "enable_display": enable_display,
                    }
                ],
            ),
            Node(
                package="pet_robot_pkg",
                executable="vision_sequence_executor",
                name="vision_sequence_executor",
                output="screen",
                parameters=[
                    {
                        "execute_once": execute_once,
                    }
                ],
            ),
        ]
    )
