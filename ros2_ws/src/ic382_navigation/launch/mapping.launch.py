from pathlib import Path
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    sim = ParameterValue(LaunchConfiguration('use_sim_time'), value_type=bool)
    share = get_package_share_directory('slam_toolbox')
    return LaunchDescription([
        DeclareLaunchArgument('params_file'),
        DeclareLaunchArgument('use_sim_time', default_value='true'),
        Node(package='ic382_navigation', executable='scan_filter',
             parameters=[{'use_sim_time': sim}], output='screen'),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(str(Path(share)/'launch/online_async_launch.py')),
            launch_arguments={'use_sim_time': LaunchConfiguration('use_sim_time'),
                              'slam_params_file': LaunchConfiguration('params_file')}.items()),
    ])
