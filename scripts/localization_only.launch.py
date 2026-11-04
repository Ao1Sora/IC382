"""AMCL on the selected map, without planners, controllers or inspection data."""
from pathlib import Path
import yaml
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from ic382_navigation.teacher_profile import laser_primary_amcl


def setup(context):
    config = yaml.safe_load(Path(LaunchConfiguration('config_file').perform(context)).read_text())
    base = Path(get_package_share_directory('turn_on_wheeltec_robot'))
    car = yaml.safe_load((base/'config/wheeltec_param.yaml').read_text())['car_mode']
    vendor = Path(get_package_share_directory('wheeltec_nav2'))
    params = yaml.safe_load((vendor/'param/wheeltec_params'/('param_'+car+'.yaml')).read_text())['amcl']['ros__parameters']
    params.update(use_sim_time=False, set_initial_pose=False, max_particles=5000,
                  min_particles=1000, scan_topic='/scan', odom_frame_id='odom_combined',
                  base_frame_id='base_footprint', global_frame_id='map',
                  update_min_d=0.05, update_min_a=0.1)
    if config.get('localization', {}).get('mode', 'laser_primary') == 'laser_primary':
        params = laser_primary_amcl(params)
    actions = [
        Node(package='nav2_map_server', executable='map_server', name='map_server',
             parameters=[{'yaml_filename': config['map'], 'use_sim_time': False}]),
        Node(package='nav2_amcl', executable='amcl', name='amcl', parameters=[params]),
        Node(package='nav2_lifecycle_manager', executable='lifecycle_manager', name='lifecycle_manager_localization',
             parameters=[{'autostart': True, 'node_names': ['map_server','amcl'], 'use_sim_time': False}]),
    ]
    if config.get('localization', {}).get('local_scan_match',False):
        actions.append(Node(package='ic382_navigation', executable='local_alignment', output='screen'))
    return actions


def generate_launch_description():
    return LaunchDescription([DeclareLaunchArgument('config_file'), OpaqueFunction(function=setup)])
