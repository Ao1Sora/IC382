"""Record a measured map-frame base pose while the robot is parked at a desk."""
import argparse
import math
from pathlib import Path
import time
import yaml
import rclpy
from rclpy.node import Node
from tf2_ros import Buffer, TransformListener


def main(args=None):
    p = argparse.ArgumentParser()
    p.add_argument('--id', required=True)
    p.add_argument('--route', required=True)
    p.add_argument('--base-frame', default='base_footprint')
    p.add_argument('--replace', action='store_true')
    parsed, ros_args = p.parse_known_args(args)
    rclpy.init(args=ros_args)
    node = Node('record_waypoint')
    b = Buffer()
    listener = TransformListener(b, node)
    try:
        deadline = time.monotonic() + 15
        while not b.can_transform('map', parsed.base_frame, rclpy.time.Time()):
            if time.monotonic() > deadline:
                raise RuntimeError('No map localization; start AMCL and set initial pose first')
            rclpy.spin_once(node, timeout_sec=0.1)
        tf = b.lookup_transform('map', parsed.base_frame, rclpy.time.Time()).transform
        q = tf.rotation
        yaw = math.atan2(2*(q.w*q.z+q.x*q.y), 1-2*(q.y*q.y+q.z*q.z))
        target = Path(parsed.route).expanduser()
        data = yaml.safe_load(target.read_text()) if target.exists() else {
            'schema_version': 1, 'frame_id': 'map', 'calibrated': False,
            'rounds': 2, 'inspection_seconds': 3.0, 'tagging_seconds': 3.0, 'waypoints': []}
        if any(x['id'] == parsed.id for x in data['waypoints']) and not parsed.replace:
            raise ValueError('Waypoint exists; use --replace to overwrite this id')
        data['waypoints'] = [x for x in data['waypoints'] if x['id'] != parsed.id]
        point = {'id': parsed.id, 'x': tf.translation.x, 'y': tf.translation.y, 'yaw': yaw}
        data['waypoints'].append(point)
        # A recorded pose is not automatically a verified docking pose.
        data['calibrated'] = False
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix('.tmp')
        temp.write_text(yaml.safe_dump(data, sort_keys=False), encoding='utf-8')
        temp.replace(target)
        print(point)
        print('Verify the route in RViz, then explicitly set calibrated: true.')
    finally:
        node.destroy_node()
        rclpy.shutdown()
