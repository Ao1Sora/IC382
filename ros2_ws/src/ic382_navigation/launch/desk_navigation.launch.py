"""Nav2 with a known map origin and encoder-only odometry; no AMCL or patrol loop."""
from pathlib import Path
import yaml
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction, IncludeLaunchDescription, OpaqueFunction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node, SetRemap


def setup(context):
    value=lambda key:LaunchConfiguration(key).perform(context)
    sim=value('use_sim_time').lower()=='true'
    common={'use_sim_time':sim}
    if value('odometry_source') not in ('wheels','external'):
        raise ValueError('odometry_source must be wheels or external')
    for key in ('map','points','params_file'):
        if not Path(value(key)).is_file():raise ValueError('Missing '+key)
    if not sim and yaml.safe_load(Path(value('points')).read_text()).get('scene_scale',1.)!=1.:
        raise ValueError('Ten-times scene coordinates cannot be used on physical hardware')
    nav_share=Path(get_package_share_directory('nav2_bringup'))
    nav=IncludeLaunchDescription(PythonLaunchDescriptionSource(str(nav_share/'launch/navigation_launch.py')),
        launch_arguments={'params_file':value('params_file'),'use_sim_time':value('use_sim_time'),
                          'autostart':'true','use_composition':'False'}.items())
    return [
        Node(package='nav2_map_server',executable='map_server',name='map_server',output='screen',
             parameters=[common,{'yaml_filename':value('map')}]),
        Node(package='nav2_lifecycle_manager',executable='lifecycle_manager',name='map_lifecycle_manager',
             parameters=[common,{'autostart':True,'node_names':['map_server']}]),
        Node(package='tf2_ros',executable='static_transform_publisher',name='known_start_map_origin',
             arguments=['--x',value('initial_x'),'--y',value('initial_y'),'--yaw',value('initial_yaw'),
                        '--frame-id','map','--child-frame-id','odom'],parameters=[common]),
        *([Node(package='ic382_navigation',executable='wheel_odometry',output='screen',
             parameters=[common,{'wheel_radius':float(value('wheel_radius')),'wheel_track':float(value('wheel_track')),
                                 'turn_track':float(value('turn_track')),'turn_blend_speed':float(value('turn_blend_speed')),
                                 'base_height':float(value('base_height'))}])]
          if value('odometry_source')=='wheels' else []),
        GroupAction([SetRemap(src='behavior_server:cmd_vel',dst='nav2_cmd_vel'),
                     SetRemap(src='cmd_vel_smoothed',dst='nav2_cmd_vel'),nav]),
        Node(package='ic382_navigation',executable='scan_filter',parameters=[common,{'max_range':200.}]),
        Node(package='ic382_navigation',executable='journal',output='screen',parameters=[common,{'log_directory':value('log_directory')}]),
        Node(package='ic382_navigation',executable='velocity_gate',output='screen',
             parameters=[common,{'max_linear':3.5,'max_angular':.6,'watchdog_timeout':5.}]),
        Node(package='ic382_navigation',executable='desk_navigation',output='screen',
             parameters=[common,{'points':value('points'),'minimum_dwell_seconds':1.,'work_timeout_seconds':120.}]),
    ]


def generate_launch_description():
    share=Path(get_package_share_directory('ic382_navigation'))
    defaults={'map':str(share/'maps/inspection/scene_map.yaml'),
              'points':str(share/'config/desk_inspection_points.yaml'),'params_file':'',
              'use_sim_time':'true','odometry_source':'wheels','initial_x':'-278.8637905602745','initial_y':'32.96996906027461',
              'initial_yaw':'0.0','wheel_radius':'0.630835','wheel_track':'3.611644','turn_track':'3.611644',
              'turn_blend_speed':'0.5','base_height':'0.63',
              'log_directory':'~/.local/state/ic382/missions'}
    return LaunchDescription([DeclareLaunchArgument(k,default_value=v) for k,v in defaults.items()]+[OpaqueFunction(function=setup)])
