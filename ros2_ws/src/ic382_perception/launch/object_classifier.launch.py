from pathlib import Path
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    config = Path(get_package_share_directory("ic382_perception")) / "config" / "object_classifier.yaml"
    return LaunchDescription([
        Node(
            package="ic382_perception",
            executable="object_classifier",
            name="object_classifier",
            parameters=[str(config)],
            output="screen",
        ),
    ])
