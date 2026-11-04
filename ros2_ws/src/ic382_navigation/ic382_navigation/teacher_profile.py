"""Adapt Wheeltec parameters and select a controller suited to differential drive."""
from copy import deepcopy
import json
import math
from .inspection import load_desks


def laser_primary_amcl(params):
    """More frequent scan matching; keep a motion threshold to avoid static collapse."""
    params = deepcopy(params)
    params.update(use_sim_time=False, set_initial_pose=False,
        min_particles=1000, max_particles=5000, max_beams=120,
        scan_topic='/scan', odom_frame_id='odom_combined',
        base_frame_id='base_footprint', global_frame_id='map',
        update_min_d=0.02, update_min_a=0.02,
        laser_model_type='likelihood_field', sigma_hit=0.12, z_hit=0.8, z_rand=0.2,
        transform_tolerance=0.2)
    return params


def differential_clearance_profile(data):
    """Use the measured body polygon directly, without obstacle inflation."""
    data = deepcopy(data)
    for name in ('local_costmap', 'global_costmap'):
        costmap = data[name][name]['ros__parameters']
        footprint = costmap.get('footprint', '')
        if isinstance(footprint, str):
            footprint = json.loads(footprint)
        if not footprint or len(footprint) < 3 or any(
                len(point) != 2 or not all(math.isfinite(v) for v in point) for point in footprint):
            raise ValueError('Measured polygon footprint required for differential navigation')
        costmap['footprint_padding'] = 0.0
        costmap['plugins'] = [p for p in costmap['plugins'] if p != 'inflation_layer']
        costmap.setdefault('inflation_layer', {})['enabled'] = False
    return data


def differential_drive_profile(data, max_linear, max_angular, xy_tolerance=0.1, lattice_filepath=None):
    """2D obstacle routing, then zero-linear-velocity alignment at the goal."""
    data = deepcopy(data)
    controller = data['controller_server']['ros__parameters']
    controller['controller_plugins'] = ['FollowPath']
    controller['goal_checker_plugins'] = ['goal_checker']
    controller['goal_checker_plugin'] = 'goal_checker'
    controller['goal_checker'] = dict(plugin='nav2_controller::SimpleGoalChecker',
        xy_goal_tolerance=xy_tolerance, yaw_goal_tolerance=0.15, stateful=True)
    controller['progress_checker'] = dict(plugin='nav2_controller::SimpleProgressChecker',
        required_movement_radius=0.02, movement_time_allowance=60.0)
    # RPP ramps from measured odometry, not the previous command. At 20 Hz,
    # 0.3 rad/s^2 requests only 0.015 rad/s forever if the chassis cannot start.
    # Reach the already proven manual rotation command without raising its cap.
    rotation_accel = max(0.3, 2 * max_angular * float(controller.get('controller_frequency', 20.0)))
    controller['FollowPath'] = dict(
        plugin='ic382_planners/StagedGoalController',
        desired_linear_vel=max_linear, lookahead_dist=0.15,
        use_velocity_scaled_lookahead_dist=False,
        use_rotate_to_heading=False, allow_reversing=False,
        rotate_to_heading_angular_vel=max_angular, rotate_to_heading_min_angle=0.3,
        max_angular_accel=rotation_accel, transform_tolerance=0.2,
        min_approach_linear_velocity=min(0.02,max_linear), approach_velocity_scaling_dist=0.4,
        # Humble samples prediction every one costmap cell. At 0.02 m/s on
        # a 0.05 m grid the first sample is 2.5 seconds ahead, so 1s skips it.
        # Lookahead still bounds the translation distance being checked.
        use_collision_detection=True, max_allowed_time_to_collision_up_to_carrot=3.0,
        use_regulated_linear_velocity_scaling=True,
        regulated_linear_scaling_min_radius=max(0.3,max_linear/max_angular),
        regulated_linear_scaling_min_speed=min(0.02,max_linear),
        use_cost_regulated_linear_velocity_scaling=False)
    planner = data['planner_server']['ros__parameters']
    planner['planner_plugins'] = ['GridBased', 'GridBasedWide']
    if lattice_filepath is None:
        from ament_index_python.packages import get_package_share_directory
        from pathlib import Path
        lattice_filepath = str(Path(get_package_share_directory('nav2_smac_planner')) /
            'sample_primitives/5cm_resolution/0.5m_turning_radius/diff/output.json')
    planner['GridBased'] = dict(plugin='ic382_planners/ClearanceLattice', planning_clearance=0.10,
        lattice_filepath=str(lattice_filepath), tolerance=0.05, allow_unknown=False,
        max_iterations=1000000, max_on_approach_iterations=1000,
        max_planning_time=5.0, cost_penalty=4.0, allow_reverse_expansion=False,
        smooth_path=False, rotation_penalty=1.0, non_straight_penalty=1.5,
        analytic_expansion_max_length=0.1)
    planner['GridBasedWide'] = dict(planner['GridBased'],
        plugin='ic382_planners/ClearanceLattice', planning_clearance=0.10)
    behavior = data.setdefault('behavior_server', {}).setdefault('ros__parameters', {})
    behavior.update(global_frame=data.get('local_costmap', {}).get('local_costmap', {}).get('ros__parameters', {}).get('global_frame','map'),
        robot_base_frame='base_footprint', use_sim_time=False,
        max_rotational_vel=max_angular, min_rotational_vel=min(0.05,max_angular),
        rotational_acc_lim=rotation_accel, transform_tolerance=0.2)

    return data


def validate_physical_points(document):
    if document.get('scene_scale') != 1 or document.get('calibrated') is not True:
        raise ValueError('Physical points require scene_scale: 1 and calibrated: true')
    return load_desks(document)


def teacher_profile(baseline, max_linear, max_angular, navigation_map=False, live_obstacles=True,
                    inflation_enabled=True):
    if not all(math.isfinite(v) and 0 < v <= limit
               for v, limit in ((max_linear, .3), (max_angular, .6))):
        raise ValueError('Physical limits: 0 < linear <= 0.3, 0 < angular <= 0.6')
    data = deepcopy(baseline)
    if 'amcl' not in data or 'controller_server' not in data:
        raise ValueError('Expected the installed Wheeltec AMCL/Nav2 profile')
    controller = data['controller_server']['ros__parameters']
    for name in controller.get('controller_plugins', ['FollowPath']):
        tracker = controller.get(name, {})
        # MPPI and DWB use different names. Limit their trajectory predictions too,
        # rather than relying on output clipping to slow a fast planned trajectory.
        for key in ('vx_max', 'max_vel_x', 'max_speed_xy'):
            if key in tracker:
                tracker[key] = min(float(tracker[key]), max_linear)
        for key in ('vx_min', 'min_vel_x'):
            if key in tracker:
                tracker[key] = max(float(tracker[key]), -max_linear)
        for key in ('wz_max', 'max_vel_theta'):
            if key in tracker:
                tracker[key] = min(float(tracker[key]), max_angular)
        if 'min_speed_xy' in tracker:
            tracker['min_speed_xy'] = min(float(tracker['min_speed_xy']), max_linear)
        if 'min_speed_theta' in tracker:
            tracker['min_speed_theta'] = min(float(tracker['min_speed_theta']), max_angular)
    for name in ('local_costmap', 'global_costmap'):
        params = data[name][name]['ros__parameters']
        plugins = params['plugins']
        if 'static_layer' not in plugins:
            params['plugins'] = ['static_layer'] + plugins
        if not live_obstacles:
            params['plugins'] = ['static_layer', 'inflation_layer']
        params.setdefault('inflation_layer', {})['enabled'] = inflation_enabled
        static = params.setdefault('static_layer', {})
        static.update(plugin='nav2_costmap_2d::StaticLayer', map_subscribe_transient_local=True)
        if navigation_map:
            static['map_topic'] = '/ic382/navigation_map'
        # Laser clearing must not erase static tabletop occupancy.
        for plugin in params['plugins']:
            layer = params.get(plugin, {})
            if layer.get('plugin', '').endswith(('ObstacleLayer', 'VoxelLayer')):
                layer['combination_method'] = 1
    # The final gate enforces these bounds independently of controller type.
    # Keep vendor tuning and plugins; standard velocity smoother also gets the limits.
    smoother = data.get('velocity_smoother', {}).get('ros__parameters')
    if smoother is not None:
        smoother['max_velocity'] = [max_linear, 0., max_angular]
        smoother['min_velocity'] = [-max_linear, 0., -max_angular]
    return data
