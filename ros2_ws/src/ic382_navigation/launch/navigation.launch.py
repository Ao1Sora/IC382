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
from ic382_navigation.teacher_profile import (teacher_profile, validate_physical_points,
    differential_drive_profile, differential_clearance_profile, laser_primary_amcl)
from ic382_navigation.runtime_config import resolve_runtime, generate_candidates, laser_body_footprint


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
    data['amcl']['ros__parameters']['set_initial_pose'] = False
    if config.get('localization', {}).get('mode', 'laser_primary') == 'laser_primary':
        data['amcl']['ros__parameters'] = laser_primary_amcl(data['amcl']['ros__parameters'])
    if 'diff' in car:
        data = differential_drive_profile(data, linear, angular, xy_tolerance=0.1)
        data['bt_navigator']['ros__parameters']['default_nav_to_pose_bt_xml'] = str(
            Path(get_package_share_directory('ic382_navigation'))/'behavior_trees/retreat_and_replan.xml')
    inspection = dict(config.get('inspection', {}))
    if inspection.get('laser_body_bounds'):
        model = yaml.safe_load((base/'config/robot_model.yaml').read_text())['robot_model'][car]
        transform = model['base_to_laser']
        inspection['laser_in_base'] = [transform[0],transform[1],transform[3]]
        inspection['robot_footprint'] = laser_body_footprint(
            inspection['laser_body_bounds'], inspection['laser_in_base'])
    footprint = inspection.get('robot_footprint')
    if footprint:
        import json
        for name in ('local_costmap', 'global_costmap'):
            data[name][name]['ros__parameters']['footprint'] = json.dumps(footprint)
    if 'diff' in car:
        data = differential_clearance_profile(data)
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
                    include(base/'launch/turn_on_wheeltec_robot.launch.py', {'carto_slam':'false', 'robot_nav':'false',
                        'use_imu':str(config.get('localization', {}).get('use_imu',True)).lower()}),
                    include(base/'launch/wheeltec_lidar.launch.py')]
    # Scope remaps to Nav2: chassis must continue subscribing to the final /cmd_vel.
    external = raw('external_localization').lower() == 'true'
    navigation_entry = (Path(get_package_share_directory('nav2_bringup'))/'launch/navigation_launch.py'
                        if external else vendor/'launch/bringup_launch.py')
    actions += [GroupAction([
        # RViz /goal_pose is owned by robot_console's guarded action bridge.
        # Humble bt_navigator otherwise self-submits a second identical action.
        SetRemap(src='goal_pose', dst='/ic382/nav2_legacy_goal_pose'),
        SetRemap(src='/goal_pose', dst='/ic382/nav2_legacy_goal_pose'),
        SetRemap(src='cmd_vel', dst='/ic382/nav2_cmd_vel'),
        SetRemap(src='/cmd_vel', dst='/ic382/nav2_cmd_vel'),
        SetRemap(src='cmd_vel_smoothed', dst='/ic382/nav2_cmd_vel'),
        include(navigation_entry, {'map':value('map'), 'params_file':generated,
                 'use_sim_time':'false', 'use_composition':'False', 'autostart':'true'})])]
    if overlay:
        actions += [Node(package='nav2_map_server', executable='map_server', name='inspection_map_server',
                         parameters=[common, {'yaml_filename':overlay, 'topic_name':'/ic382/navigation_map'}]),
                    Node(package='nav2_lifecycle_manager', executable='lifecycle_manager', name='inspection_map_manager',
                         parameters=[common, {'autostart':True, 'node_names':['inspection_map_server']}])]
    remaps = [('scan_nav','/scan'), ('odom','/odom_combined')]
    actions += [Node(package='ic382_navigation', executable='journal', output='screen',
                     parameters=[common, {'log_directory':value('log_directory')}]),
                Node(package='ic382_navigation', executable='velocity_gate', output='screen',
                     parameters=[common, {'max_linear':linear, 'max_angular':angular, 'watchdog_timeout':1.}],
                     remappings=remaps+[('nav2_cmd_vel','/ic382/nav2_cmd_vel')]),
                Node(package='ic382_navigation', executable='desk_navigation', output='screen',
                     parameters=[common, {'points':points, 'localization':'wheeltec_amcl',
                                          'require_local_alignment':bool(config.get('localization', {}).get('local_scan_match',False)),
                                          'minimum_dwell_seconds':float(value('minimum_dwell_seconds')),
                                          'work_timeout_seconds':float(value('work_timeout_seconds'))}], remappings=remaps)]
    if not external and config.get('localization', {}).get('local_scan_match',False):
        actions += [Node(package='ic382_navigation', executable='local_alignment', output='screen')]
    return actions


def generate_launch_description():
    share = Path(get_package_share_directory('ic382_navigation'))
    required = [DeclareLaunchArgument('config_file', default_value=str(share/'config/physical_runtime.yaml'))]
    defaults = {key:'' for key in ('map','points','params_file','navigation_map','start_hardware','external_localization',
                'max_linear','max_angular','minimum_dwell_seconds','work_timeout_seconds','log_directory')}
    return LaunchDescription(required + [DeclareLaunchArgument(k, default_value=v) for k,v in defaults.items()]
                             + [OpaqueFunction(function=setup)])
