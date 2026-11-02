#!/usr/bin/env python3
"""Independent simulator-pose evidence. Publishes no ROS messages or commands."""
import json
import math
from pathlib import Path
import time
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import yaml
from ic382_navigation.simulation_profile import prepare_simulation

root = Path('/workspace/robot-ros2')
config = yaml.safe_load((root/'simulation/config/runtime.yaml').read_text())
_, document = prepare_simulation(yaml.safe_load(Path(config['params_file']).read_text()),
                                yaml.safe_load(Path(config['overrides']).read_text()), config)
points = {p['id']:p for p in document['waypoints']}
report = {'purpose':'independent simulation evidence; never a localization input', 'arrivals':[], 'terminal':None}
out = root/'results/isaac-20261102/independent-arrivals.json'
rclpy.init()
node = Node('isaac_inspection_evidence')


def event(message):
    record = json.loads(message.data)
    if record['event'] == 'inspection_point_ready':
        point = points[record['data']['point_id']]
        path = Path('/workspace/logs/course601-live.json')
        live = json.loads(path.read_text())
        q = live['world_orientation']  # Isaac reports quaternion as w,x,y,z.
        yaw = math.atan2(2*(q[0]*q[3]+q[1]*q[2]), 1-2*(q[2]**2+q[3]**2))
        position = live['world_pose'][:2]
        report['arrivals'].append({'point_id':point['id'], 'goal':point,
            'truth_xy':position, 'truth_yaw':yaw, 'snapshot_age_seconds':time.time()-path.stat().st_mtime,
            'position_error_m':math.hypot(position[0]-point['x'],position[1]-point['y'])/config['scene_scale'],
            'yaw_error_rad':math.atan2(math.sin(yaw-point['yaw']),math.cos(yaw-point['yaw']))})
    if record['event'] in ('desk_inspection_completed','desk_inspection_failed','desk_inspection_canceled'):
        report['terminal'] = record
    out.write_text(json.dumps(report, indent=2))


node.create_subscription(String, '/ic382/events', event, 100)
end = time.monotonic()+1000
try:
    while time.monotonic()<end and report['terminal'] is None:
        rclpy.spin_once(node, timeout_sec=.2)
finally:
    out.write_text(json.dumps(report, indent=2))
    node.destroy_node()
    rclpy.shutdown()
