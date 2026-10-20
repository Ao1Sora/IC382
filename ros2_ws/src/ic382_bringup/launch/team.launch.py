from pathlib import Path
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from ic382_bringup.config import load_nodes


def start_nodes(context):
    entries = load_nodes(LaunchConfiguration("config").perform(context))
    return [
        Node(package=item["package"], executable=item["executable"],
             name=item["name"], arguments=item.get("arguments", []),
             parameters=[{"use_sim_time": True}], output="screen")
        for item in entries if item.get("enabled", True)
    ]


def generate_launch_description():
    default = Path(get_package_share_directory("ic382_bringup")) / "config" / "team-nodes.json"
    return LaunchDescription([
        DeclareLaunchArgument("config", default_value=str(default)),
        OpaqueFunction(function=start_nodes),
    ])

