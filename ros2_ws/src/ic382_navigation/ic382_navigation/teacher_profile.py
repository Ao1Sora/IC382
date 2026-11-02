"""Adapt the installed Wheeltec profile without replacing its navigation plugins."""
from copy import deepcopy
import math
from .inspection import load_desks


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
