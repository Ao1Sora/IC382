"""Isaac-only unit adaptation; the inspection action remains shared with Jetson."""
from copy import deepcopy
import json
from .runtime_config import generate_candidates
from .teacher_profile import teacher_profile


def merge(left, right):
    result = deepcopy(left)
    for key, value in right.items():
        result[key] = merge(result[key], value) if isinstance(value, dict) and isinstance(result.get(key), dict) else deepcopy(value)
    return result


def prepare_simulation(baseline, overrides, config):
    scale = float(config['scene_scale'])
    if scale != 10. or config.get('use_sim_time') is not True:
        raise ValueError('This adapter is only for the existing 10x Isaac scene')
    linear, angular = float(config['max_linear_mps']), float(config['max_angular'])
    data = teacher_profile(merge(baseline, overrides), linear, angular,
                           True, config['live_obstacles'], config['inflation_enabled'])
    controller = data['controller_server']['ros__parameters']['FollowPath']
    controller.update(max_vel_x=linear*scale, max_speed_xy=linear*scale,
                      min_vel_x=-linear*scale, max_vel_theta=angular)
    controller['rotate_to_heading_angular_vel'] = min(angular, controller['rotate_to_heading_angular_vel'])
    data['velocity_smoother']['ros__parameters'].update(
        max_velocity=[linear*scale, 0., angular], min_velocity=[-linear*scale, 0., -angular])
    data['amcl']['ros__parameters'].update(
        base_frame_id='base_footprint', odom_frame_id='odom', scan_topic='scan_nav',
        set_initial_pose=True, always_reset_initial_pose=True, initial_pose=config['initial_pose'])
    for name in ('local_costmap', 'global_costmap'):
        costmap = data[name][name]['ros__parameters']
        costmap['robot_base_frame'] = 'base_footprint'
        costmap['footprint'] = json.dumps(config['robot_footprint_scene'], separators=(',', ':'))
    # The supplied geometry stays in scene coordinates. Convert to real metres
    # for the shared 0.5 m front-clearance generator, then back for Nav2.
    settings = deepcopy(config['inspection'])
    settings['robot_footprint'] = [[x/scale, y/scale] for x,y in config['robot_footprint_scene']]
    for desk in settings['desks']:
        desk['polygon'] = [[x/scale, y/scale] for x,y in desk['polygon']]
    points = generate_candidates(settings, settings['robot_footprint'])
    for point in points['waypoints']:
        point['x'] *= scale
        point['y'] *= scale
    points['scene_scale'] = scale
    points['calibrated'] = False
    points['purpose'] = 'Known scene bounds; camera coverage not calibrated'
    return data, points
