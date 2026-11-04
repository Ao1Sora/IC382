#!/usr/bin/env python3
"""Check installed lattice routes around tabletop occupancy in an isolated domain."""
import json
import math
import os
import signal
import subprocess
import tempfile
import time
from pathlib import Path

assert os.environ.get('ROS_DOMAIN_ID') == '138', 'Use isolated ROS_DOMAIN_ID=138'
import rclpy
import yaml
from ament_index_python.packages import get_package_share_directory
from geometry_msgs.msg import TransformStamped
from lifecycle_msgs.srv import ChangeState
from nav2_msgs.action import ComputePathToPose
from nav_msgs.msg import OccupancyGrid
from rclpy.action import ActionClient
from rclpy.qos import QoSProfile, DurabilityPolicy
from tf2_ros import TransformBroadcaster
from ic382_navigation.teacher_profile import differential_drive_profile, differential_clearance_profile
from ic382_navigation.runtime_config import laser_body_footprint


def main():
    narrow = os.environ.get('TEST_NARROW_PASSAGE') == '1'
    blocked_passage=os.environ.get('TEST_BLOCKED_PASSAGE')=='1'
    preference_overlap=os.environ.get('TEST_PREFERENCE_OVERLAP')=='1'
    vendor = Path(get_package_share_directory('wheeltec_nav2'))
    data = differential_drive_profile(
        yaml.safe_load((vendor / 'param/wheeltec_params/param_senior_diff.yaml').read_text()), .05, .15)
    model=yaml.safe_load((Path(get_package_share_directory('turn_on_wheeltec_robot'))/'config/robot_model.yaml').read_text())['robot_model']['senior_diff']['base_to_laser']
    body=laser_body_footprint(dict(front=.1,back=.3,left=.2,right=.2),[model[0],model[1],model[3]])
    for name in ('local_costmap','global_costmap'):
        data[name][name]['ros__parameters']['footprint']=json.dumps(body)
    data=differential_clearance_profile(data)
    costmap = data['global_costmap']['global_costmap']['ros__parameters']
    costmap['plugins'] = ['static_layer']
    costmap['static_layer'] = dict(plugin='nav2_costmap_2d::StaticLayer',
                                  map_subscribe_transient_local=True, map_topic='/test_map')
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as stream:
        yaml.safe_dump(data, stream)
        config = stream.name
    log = tempfile.TemporaryFile(mode='w+')
    process = subprocess.Popen(['ros2', 'run', 'nav2_planner', 'planner_server',
        '--ros-args', '--params-file', config], stdout=log, stderr=log, start_new_session=True)
    rclpy.init()
    node = rclpy.create_node('isolated_body_clearance_check')
    broadcaster = TransformBroadcaster(node)

    def publish():
        tf = TransformStamped()
        tf.header.stamp = node.get_clock().now().to_msg()
        tf.header.frame_id, tf.child_frame_id = 'map', 'base_footprint'
        if narrow: tf.transform.translation.y = -.025
        tf.transform.rotation.w = 1.
        broadcaster.sendTransform(tf)

    node.create_timer(.05, publish)
    qos = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
    maps = node.create_publisher(OccupancyGrid, '/test_map', qos)
    grid = OccupancyGrid()
    grid.header.frame_id = 'map'
    grid.info.resolution, grid.info.width, grid.info.height = .05, 100, 100
    grid.info.origin.position.x = grid.info.origin.position.y = -2.5
    grid.info.origin.orientation.w = 1.
    grid.data = [0] * 10000
    occupied = []
    for y in (((45,53) if blocked_passage else ((44,54) if preference_overlap else (42,56))) if narrow else range(48,52)):
        for x in (range(100) if narrow else range(63,67)):
            grid.data[y * 100 + x] = 100
            occupied.append((-2.5 + (x + .5) * .05, -2.5 + (y + .5) * .05))
    maps.publish(grid)

    def wait(future):
        deadline = time.monotonic() + 25
        while not future.done() and time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=.05)
        assert future.done(), 'ROS request timed out'
        return future.result()

    try:
        service = node.create_client(ChangeState, '/planner_server/change_state')
        assert service.wait_for_service(timeout_sec=15)
        for transition in (1, 3):
            request = ChangeState.Request()
            request.transition.id = transition
            assert wait(service.call_async(request)).success
        action = ActionClient(node, ComputePathToPose, '/compute_path_to_pose')
        assert action.wait_for_server(timeout_sec=5)
        goal = ComputePathToPose.Goal()
        goal.start.header.frame_id = goal.goal.header.frame_id = 'map'
        goal.start.pose.orientation.w = goal.goal.pose.orientation.w = 1.
        goal.goal.pose.position.x = 1.5
        if not narrow:
            goal.goal.pose.orientation.z=math.sin(.37/2)
            goal.goal.pose.orientation.w=math.cos(.37/2)
        if narrow:
            goal.start.pose.position.y = goal.goal.pose.position.y = -.025
        goal.use_start, goal.planner_id = True, os.environ.get('TEST_PLANNER_ID','GridBased')
        handle = wait(action.send_goal_async(goal))
        assert handle.accepted
        result = wait(handle.get_result_async())
        if narrow and blocked_passage:
            assert result.status==6, 'Measured 0.40 m body must reject a 0.35 m passage'
            print('PASS: measured 0.40 m body rejects physical 0.35 m passage')
            return
        assert result.status == 4, 'Planner failed'
        from nav2_msgs.srv import GetCostmap
        service_map=node.create_client(GetCostmap,'/global_costmap/get_costmap')
        assert service_map.wait_for_service(timeout_sec=5)
        raw=wait(service_map.call_async(GetCostmap.Request())).map
        assert all(value in (0,254,255) for value in raw.data), 'Preference costs leaked into real costmap'
        end=result.result.path.poses[-1].pose
        assert abs(end.orientation.z-goal.goal.pose.orientation.z)<1e-9
        assert abs(end.orientation.w-goal.goal.pose.orientation.w)<1e-9
        points = [p.pose.position for p in result.result.path.poses]
        def overlap(poly, square):
            for shape in (poly,square):
                for i,(x,y) in enumerate(shape):
                    bx,by=shape[(i+1)%len(shape)];nx,ny=by-y,x-bx
                    a=[px*nx+py*ny for px,py in poly];b=[px*nx+py*ny for px,py in square]
                    if max(a)<min(b)-1e-8 or max(b)<min(a)-1e-8:return False
            return True
        if not preference_overlap:
            body=[(x+math.copysign(.10,x),y+math.copysign(.10,y)) for x,y in body]
        for pose in result.result.path.poses:
            q=pose.pose.orientation;heading=2*math.atan2(q.z,q.w)
            c,s=math.cos(heading),math.sin(heading);p=pose.pose.position
            poly=[(p.x+c*x-s*y,p.y+s*x+c*y) for x,y in body]
            for x,y in occupied:
                square=[(x-.025,y-.025),(x+.025,y-.025),(x+.025,y+.025),(x-.025,y+.025)]
                assert not overlap(poly,square), 'Planned body overlaps tabletop occupancy'
        if narrow and preference_overlap:
            assert all(abs(p.y+.025)<.026 for p in points), 'Tight corridor route is not central'
            print('PASS: overlapping 10 cm preferences still allow central route in physical 0.45 m passage')
        elif narrow:
            print('PASS: preferred 10 cm route retained where 0.65 m passage permits it')
        else:
            assert max(abs(p.y) for p in points) > .25, 'Path did not detour around tabletop'
            print(f'PASS: full-body tabletop detour without inflation, {len(points)} path poses checked')

    finally:
        os.killpg(process.pid, signal.SIGINT)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
        node.destroy_node()
        rclpy.shutdown()
        os.unlink(config)
        log.seek(0)
        print(log.read()[-2500:])
        log.close()


if __name__ == '__main__':
    main()
