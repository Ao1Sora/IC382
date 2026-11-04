"""View a selected saved map without starting navigation or motion."""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('map'),
        Node(package='nav2_map_server', executable='map_server', name='preview_map_server',
             parameters=[{'yaml_filename': LaunchConfiguration('map'), 'use_sim_time': False}],
             remappings=[('map', '/map')]),
        Node(package='nav2_lifecycle_manager', executable='lifecycle_manager', name='preview_map_manager',
             parameters=[{'autostart': True, 'node_names': ['preview_map_server'], 'use_sim_time': False}]),
    ])
