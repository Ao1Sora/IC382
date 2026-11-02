"""Use the course Wheeltec lidar + chassis + SLAM entry unchanged."""
from pathlib import Path
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource


def generate_launch_description():
    source = Path(get_package_share_directory('wheeltec_slam_toolbox'))/'launch/online_async_launch.py'
    return LaunchDescription([IncludeLaunchDescription(PythonLaunchDescriptionSource(str(source)))])
