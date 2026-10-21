#!/usr/bin/env python3
"""Adapt teacher Nav2 params to the measured team robot and exported 10x map."""
import argparse
import json
import math
from pathlib import Path
import yaml

p = argparse.ArgumentParser()
p.add_argument('--environment', default='/workspace')
p.add_argument('--output', required=True)
p.add_argument('--footprint', default='[[-1.3,-2.6],[-1.3,2.1],[5.05,2.1],[5.05,-2.6]]')
args = p.parse_args()
env = Path(args.environment)
data = yaml.safe_load((env/'dev/custom_nav2_params.yaml').read_text())
live = json.loads((env/'logs/course601-live.json').read_text())
q = live['world_orientation']
yaw = math.atan2(2*(q[0]*q[3]+q[1]*q[2]), 1-2*(q[2]**2+q[3]**2))
amcl = data['amcl']['ros__parameters']
amcl.update(scan_topic='scan_nav', laser_max_range=200.0, laser_min_range=1.0,
            laser_likelihood_max_dist=4.0, sigma_hit=0.75, max_beams=120,
            update_min_d=0.15, update_min_a=0.10, transform_tolerance=2.0,
            set_initial_pose=True, always_reset_initial_pose=True,
            initial_pose={'x': live['world_pose'][0], 'y': live['world_pose'][1],
                          'z': 0.0, 'yaw': yaw})
controller = data['controller_server']['ros__parameters']
controller.update(controller_frequency=10.0, failure_tolerance=1.0)
controller['progress_checker'].update(required_movement_radius=0.10, movement_time_allowance=30.0)
controller['general_goal_checker'].update(xy_goal_tolerance=0.5, yaw_goal_tolerance=0.2)
controller['FollowPath'].update(max_vel_x=2.0, max_speed_xy=2.0, max_vel_theta=0.3,
    min_speed_xy=0.0, min_speed_theta=0.05, acc_lim_theta=0.5, decel_lim_theta=-0.5,
    xy_goal_tolerance=0.5, trans_stopped_velocity=0.05,
    vx_samples=20, vtheta_samples=20, sim_time=2.0, transform_tolerance=1.0)
for kind in ('local_costmap', 'global_costmap'):
    params = data[kind][kind]['ros__parameters']
    params.update(footprint=args.footprint, footprint_padding=0.15, resolution=0.25,
                  transform_tolerance=2.0, update_frequency=3.0, publish_frequency=1.0)
    if kind == 'local_costmap':
        params.update(width=30, height=30)
    layer = params['obstacle_layer']['scan']
    layer.update(topic='/scan_nav', min_obstacle_height=-10.0, max_obstacle_height=20.0,
                 inf_is_valid=True, raytrace_max_range=100.0, obstacle_max_range=80.0,
                 raytrace_min_range=1.0, obstacle_min_range=1.0)
    params['inflation_layer'].update(inflation_radius=3.5, cost_scaling_factor=1.0)
data['planner_server']['ros__parameters']['GridBased'].update(allow_unknown=False, tolerance=0.5)
data['behavior_server']['ros__parameters'].update(max_rotational_vel=0.3,
    min_rotational_vel=0.05, rotational_acc_lim=0.5, transform_tolerance=2.0)
data['velocity_smoother']['ros__parameters'].update(
    max_velocity=[2.0, 0.0, 0.3], min_velocity=[-0.5, 0.0, -0.3],
    max_accel=[1.0, 0.0, 0.5], max_decel=[-1.0, 0.0, -0.5], velocity_timeout=1.0)
out = Path(args.output)
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(yaml.safe_dump(data, sort_keys=False), encoding='utf-8')
print(json.dumps({'params': str(out), 'initial_pose': amcl['initial_pose'],
                  'scene_scale': 10.0, 'footprint': json.loads(args.footprint)}, indent=2))
