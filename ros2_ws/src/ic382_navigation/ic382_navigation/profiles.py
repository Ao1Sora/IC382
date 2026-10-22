"""Resolve the unchanged course Nav2 baseline with explicit team adaptations."""
from copy import deepcopy
import json
import math


def merge_profile(baseline, overrides):
    result = deepcopy(baseline)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge_profile(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def validate_profile(profile):
    controller = profile['controller_server']['ros__parameters']
    dwb = controller['FollowPath']
    if dwb['plugin'] != 'dwb_core::DWBLocalPlanner':
        raise ValueError('The course-derived team profile requires plain DWB')
    if 'ObstacleFootprint' not in dwb['critics']:
        raise ValueError('DWB must check the full CAD footprint')
    if not 0 < dwb['min_speed_xy'] <= dwb['max_speed_xy']:
        raise ValueError('Positive min_speed_xy is required for the DWB minimum-turn check')
    if not 0 < dwb['min_speed_theta'] <= dwb['max_vel_theta']:
        raise ValueError('Minimum turn speed must fit within the configured angular limit')
    if dwb['xy_goal_tolerance'] != controller['general_goal_checker']['xy_goal_tolerance']:
        raise ValueError('DWB and the goal checker must agree on position tolerance')
    amcl = profile['amcl']['ros__parameters']
    smoother = profile['velocity_smoother']['ros__parameters']
    if smoother['max_velocity'][0] != dwb['max_vel_x'] or smoother['max_velocity'][2] != dwb['max_vel_theta']:
        raise ValueError('Controller and velocity-smoother limits must agree')
    footprints = []
    for name in ('local_costmap', 'global_costmap'):
        costmap = profile[name][name]['ros__parameters']
        if costmap['robot_base_frame'] != amcl['base_frame_id']:
            raise ValueError('Costmap and AMCL must use the same base frame')
        footprint = json.loads(costmap['footprint'])
        if len(footprint) < 3 or any(len(p) != 2 or not all(math.isfinite(v) for v in p) for p in footprint):
            raise ValueError('Footprint must be a finite XY polygon')
        footprints.append(footprint)
        scan = costmap['obstacle_layer']['scan']
        if not (amcl['laser_min_range'] <= scan['obstacle_min_range'] < scan['obstacle_max_range']
                <= scan['raytrace_max_range'] <= amcl['laser_max_range']):
            raise ValueError('Obstacle and clearing ranges must fit within the laser range')
        if scan['topic'].lstrip('/') != amcl['scan_topic'].lstrip('/'):
            raise ValueError('Localization and obstacle layers must use the same filtered scan')
    if footprints[0] != footprints[1]:
        raise ValueError('Global and local costmaps must agree on the CAD footprint')
    return profile


def build_profile(baseline, overrides, initial_pose=None, footprint=None):
    result = merge_profile(baseline, overrides)
    if footprint is not None:
        for name in ('local_costmap', 'global_costmap'):
            result[name][name]['ros__parameters']['footprint'] = footprint
    if initial_pose is not None:
        if set(initial_pose) != {'x', 'y', 'z', 'yaw'} or not all(math.isfinite(v) for v in initial_pose.values()):
            raise ValueError('Initial pose must contain finite x/y/z/yaw')
        result['amcl']['ros__parameters'].update(
            set_initial_pose=True, always_reset_initial_pose=True, initial_pose=initial_pose)
    return validate_profile(result)
