from pathlib import Path
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from ic382_bringup.config import load_nodes


def start_nodes(context):
    entries = load_nodes(LaunchConfiguration("config").perform(context))
    use_sim_time = ParameterValue(
        LaunchConfiguration("use_sim_time"), value_type=bool)
    return [
        Node(package=item["package"], executable=item["executable"],
             name=item["name"], arguments=item.get("arguments", []),
             parameters=[item.get("parameters", {}), {"use_sim_time": use_sim_time}],
             output="screen")
        for item in entries if item.get("enabled", True)
    ]


def generate_launch_description():
    default = Path(get_package_share_directory("ic382_bringup")) / "config" / "team-nodes.json"
    return LaunchDescription([
        DeclareLaunchArgument("config", default_value=str(default)),
        DeclareLaunchArgument("use_sim_time", default_value="true"),
        OpaqueFunction(function=start_nodes),
    ])

