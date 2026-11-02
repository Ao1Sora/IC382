"""HPC Isaac scene: teacher Nav2, AMCL, encoder odometry and shared inspection."""
from pathlib import Path
import tempfile
import yaml
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction, IncludeLaunchDescription, OpaqueFunction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node, SetRemap
from ic382_navigation.runtime_config import resolve_runtime
from ic382_navigation.simulation_profile import prepare_simulation


def setup(context):
    path = Path(LaunchConfiguration('config_file').perform(context))
    config = resolve_runtime(yaml.safe_load(path.read_text()), path)
    if config.get('start_hardware', False):
        raise ValueError('Physical drivers are forbidden in the Isaac launch')
    data, points = prepare_simulation(yaml.safe_load(Path(config['params_file']).read_text()),
                                     yaml.safe_load(Path(config['overrides']).read_text()), config)
    def temporary(document):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.safe_dump(document, f, sort_keys=False)
            return f.name
    params, candidates = temporary(data), temporary(points)
    common = {'use_sim_time': True}
    share = Path(get_package_share_directory('nav2_bringup'))
    nav = IncludeLaunchDescription(PythonLaunchDescriptionSource(str(share/'launch/bringup_launch.py')),
        launch_arguments={'map':config['map'], 'params_file':params, 'use_sim_time':'true',
                          'use_composition':'False', 'autostart':'true'}.items())
    return [
        Node(package='ic382_navigation', executable='simulation_encoder', parameters=[common,config['encoder']]),
        Node(package='ic382_navigation', executable='simulation_scan', parameters=[common]),
        GroupAction([SetRemap(src='cmd_vel', dst='/ic382/controller_cmd_vel'),
                     SetRemap(src='/cmd_vel', dst='/ic382/controller_cmd_vel'),
                     SetRemap(src='cmd_vel_smoothed', dst='/ic382/nav2_cmd_vel'), nav]),
        Node(package='nav2_map_server', executable='map_server', name='inspection_map_server',
             parameters=[common, {'yaml_filename':config['navigation_map'], 'topic_name':'/ic382/navigation_map'}]),
        Node(package='nav2_lifecycle_manager', executable='lifecycle_manager', name='inspection_map_manager',
             parameters=[common, {'autostart':True, 'node_names':['inspection_map_server']}]),
        Node(package='ic382_navigation', executable='journal', parameters=[common,{'log_directory':config['log_directory']}]),
        Node(package='ic382_navigation', executable='velocity_gate',
             parameters=[common,{'max_linear':config['max_linear_mps']*config['scene_scale'],
                                 'max_angular':config['max_angular'], 'watchdog_timeout':5.}],
             remappings=[('nav2_cmd_vel','/ic382/nav2_cmd_vel')]),
        Node(package='ic382_navigation', executable='desk_navigation',
             parameters=[common,{'points':candidates, 'localization':'isaac_amcl',
                                 'minimum_dwell_seconds':config['minimum_dwell_seconds'],
                                 'work_timeout_seconds':config['work_timeout_seconds']}]),
    ]


def generate_launch_description():
    return LaunchDescription([DeclareLaunchArgument('config_file'), OpaqueFunction(function=setup)])
