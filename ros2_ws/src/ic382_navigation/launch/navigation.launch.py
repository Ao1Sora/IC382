"""Wheeltec classroom localization/navigation with the team's three-point action."""
from pathlib import Path
import tempfile
import yaml
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction, IncludeLaunchDescription, OpaqueFunction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node, SetRemap
from ic382_navigation.teacher_profile import teacher_profile, validate_physical_points
from ic382_navigation.runtime_config import resolve_runtime, generate_candidates


def setup(context):
    raw = lambda key: LaunchConfiguration(key).perform(context)
    config_path = Path(raw('config_file')).expanduser()
    config = resolve_runtime(yaml.safe_load(config_path.read_text()), config_path)
    value = lambda key: raw(key) or str(config.get(key, ''))
    base = Path(get_package_share_directory('turn_on_wheeltec_robot'))
    vendor = Path(get_package_share_directory('wheeltec_nav2'))
    for key in ('map',):
        if not Path(value(key)).is_file():
            raise ValueError('Missing physical ' + key)
    car = yaml.safe_load((base/'config/wheeltec_param.yaml').read_text())['car_mode']
    params = Path(value('params_file')) if value('params_file') else vendor/'param/wheeltec_params'/('param_'+car+'.yaml')
    linear, angular = float(value('max_linear')), float(value('max_angular'))
    overlay = value('navigation_map')
    if overlay and not Path(overlay).is_file():
        raise ValueError('Missing annotated navigation_map')
    data = teacher_profile(yaml.safe_load(params.read_text()), linear, angular, bool(overlay),
                           config.get('live_obstacles', True), config.get('inflation_enabled', True))
    inspection = config.get('inspection', {})
    footprint = inspection.get('robot_footprint')
    if footprint:
        import json
        for name in ('local_costmap', 'global_costmap'):
            data[name][name]['ros__parameters']['footprint'] = json.dumps(footprint)
    points = value('points')
    if not points:
        if not overlay:
            raise ValueError('Auto desk viewpoints require a tabletop-annotated navigation_map')
        document = generate_candidates(inspection, data['local_costmap']['local_costmap']['ros__parameters']['footprint'])
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', prefix='ic382-desk-candidates-', delete=False) as f:
            yaml.safe_dump(document, f)
            points = f.name
    validate_physical_points(yaml.safe_load(Path(points).read_text()))
    # Only the controller action client drives routes. Do not launch vendor waypoint_cycle.
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', prefix='ic382-wheeltec-', delete=False) as f:
        yaml.safe_dump(data, f, sort_keys=False)
        generated = f.name
    common = {'use_sim_time': False}
    include = lambda path, args={}: IncludeLaunchDescription(
        PythonLaunchDescriptionSource(str(path)), launch_arguments=args.items())
    actions = []
    if value('start_hardware').lower() == 'true':
        actions += [include(base/'launch/imu_processor.launch.py'),
                    include(base/'launch/turn_on_wheeltec_robot.launch.py', {'carto_slam':'false', 'robot_nav':'false'}),
                    include(base/'launch/wheeltec_lidar.launch.py')]
    # Scope remaps to Nav2: chassis must continue subscribing to the final /cmd_vel.
    actions += [GroupAction([
        SetRemap(src='cmd_vel', dst='/ic382/nav2_cmd_vel'),
        SetRemap(src='/cmd_vel', dst='/ic382/nav2_cmd_vel'),
        SetRemap(src='cmd_vel_smoothed', dst='/ic382/nav2_cmd_vel'),
        include(vendor/'launch/bringup_launch.py', {'map':value('map'), 'params_file':generated,
                 'use_sim_time':'false', 'use_composition':'False', 'autostart':'true'})])]
    if overlay:
        actions += [Node(package='nav2_map_server', executable='map_server', name='inspection_map_server',
                         parameters=[common, {'yaml_filename':overlay, 'topic_name':'/ic382/navigation_map'}]),
                    Node(package='nav2_lifecycle_manager', executable='lifecycle_manager', name='inspection_map_manager',
                         parameters=[common, {'autostart':True, 'node_names':['inspection_map_server']}])]
    remaps = [('scan_nav','/scan'), ('odom','/odom_combined')]
    require_safety = str(value('require_safety') or 'true').lower() == 'true'
    actions += [Node(package='ic382_navigation', executable='journal', output='screen',
                     parameters=[common, {'log_directory':value('log_directory')}]),
                Node(package='ic382_navigation', executable='velocity_gate', output='screen',
                     parameters=[common, {'max_linear':linear, 'max_angular':angular, 'watchdog_timeout':1.,
                                          'require_safety':require_safety, 'safety_timeout':0.5}],
                     remappings=remaps+[('nav2_cmd_vel','/ic382/nav2_cmd_vel')]),
                Node(package='ic382_navigation', executable='desk_navigation', output='screen',
                     parameters=[common, {'points':points, 'localization':'wheeltec_amcl',
                                          'minimum_dwell_seconds':float(value('minimum_dwell_seconds')),
                                          'work_timeout_seconds':float(value('work_timeout_seconds'))}], remappings=remaps)]
    if str(value('start_perception') or 'true').lower() == 'true':
        perception = Path(get_package_share_directory('ic382_perception'))/'launch/perception.launch.py'
        actions.append(IncludeLaunchDescription(
            PythonLaunchDescriptionSource(str(perception)),
            launch_arguments={'use_sim_time':'false',
                              'model_path':str(value('model_path')),
                              'model_profile':str(value('model_profile') or 'coco_bootstrap'),
                              'tagging_enabled':str(value('tagging_enabled') or 'false'),
                              'perception_required':str(value('perception_required') or 'false')}.items()))
    return actions


def generate_launch_description():
    share = Path(get_package_share_directory('ic382_navigation'))
    required = [DeclareLaunchArgument('config_file', default_value=str(share/'config/physical_runtime.yaml'))]
    defaults = {key:'' for key in ('map','points','params_file','navigation_map','start_hardware',
                'max_linear','max_angular','minimum_dwell_seconds','work_timeout_seconds','log_directory',
                'model_path','model_profile','tagging_enabled','perception_required')}
    defaults['start_perception'] = 'true'
    defaults['require_safety'] = ''
    return LaunchDescription(required + [DeclareLaunchArgument(k, default_value=v) for k,v in defaults.items()]
                             + [OpaqueFunction(function=setup)])
