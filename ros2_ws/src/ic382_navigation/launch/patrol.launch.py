from pathlib import Path
import yaml
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction, IncludeLaunchDescription, OpaqueFunction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node, SetRemap
from launch_ros.parameter_descriptions import ParameterValue


def setup(context):
    value = lambda name: LaunchConfiguration(name).perform(context)
    for name in ('map', 'params_file', 'route'):
        if not Path(value(name)).expanduser().is_file():
            raise ValueError(name + ' does not exist: ' + value(name))
    sim = value('use_sim_time').lower() == 'true'
    route = yaml.safe_load(Path(value('route')).read_text())
    if not sim and route.get('scene_scale', 1.0) != 1.0:
        raise ValueError('A 10x simulation route cannot be used on the physical robot')
    common = {'use_sim_time': sim}
    share = get_package_share_directory('nav2_bringup')
    nav = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(str(Path(share)/'launch/bringup_launch.py')),
        launch_arguments={'map': value('map'), 'params_file': value('params_file'),
                          'use_sim_time': value('use_sim_time'), 'autostart': 'true',
                          'use_composition': 'False', 'slam': 'False'}.items())
    return [
        GroupAction([SetRemap(src='behavior_server:cmd_vel', dst='nav2_cmd_vel'),
                     SetRemap(src='cmd_vel_smoothed', dst='nav2_cmd_vel'), nav]),
        Node(package='ic382_navigation', executable='scan_filter', output='screen',
             parameters=[common, {'max_range': float(value('max_range'))}]),
        Node(package='ic382_navigation', executable='journal', output='screen',
             parameters=[common, {'log_directory': value('log_directory')}]),
        Node(package='ic382_navigation', executable='velocity_gate', output='screen',
             parameters=[common, {'max_linear': float(value('max_linear')),
                                  'max_angular': float(value('max_angular')),
                                  'watchdog_timeout': float(value('sensor_timeout'))}]),
        Node(package='ic382_navigation', executable='mission', output='screen',
             parameters=[common, {'route': value('route'),
                                  'autostart': value('autostart').lower() == 'true',
                                  'navigation_timeout': float(value('navigation_timeout')),
                                  'sensor_timeout': float(value('sensor_timeout'))}]),
    ]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('map'), DeclareLaunchArgument('params_file'),
        DeclareLaunchArgument('route'),
        DeclareLaunchArgument('use_sim_time', default_value='true'),
        DeclareLaunchArgument('autostart', default_value='false'),
        DeclareLaunchArgument('log_directory', default_value='~/.local/state/ic382/missions'),
        DeclareLaunchArgument('max_linear', default_value='1.0'),
        DeclareLaunchArgument('max_angular', default_value='0.3'),
        DeclareLaunchArgument('max_range', default_value='200.0'),
        DeclareLaunchArgument('navigation_timeout', default_value='600.0'),
        DeclareLaunchArgument('sensor_timeout', default_value='5.0'),
        OpaqueFunction(function=setup),
    ])
