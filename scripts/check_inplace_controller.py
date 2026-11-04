#!/usr/bin/env python3
"""Exercise the installed controller in an isolated ROS domain, without hardware."""
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
from geometry_msgs.msg import PoseStamped, TransformStamped, Twist
from lifecycle_msgs.srv import ChangeState
from nav2_msgs.action import FollowPath
from nav_msgs.msg import OccupancyGrid, Odometry, Path as RosPath
from rclpy.action import ActionClient
from rclpy.qos import QoSProfile, DurabilityPolicy
from tf2_ros import TransformBroadcaster
from ic382_navigation.teacher_profile import differential_drive_profile
from ic382_navigation.teacher_profile import differential_clearance_profile
import json


def main():
    vendor = Path(get_package_share_directory('wheeltec_nav2'))
    data = differential_drive_profile(yaml.safe_load((vendor / 'param/wheeltec_params/param_senior_diff.yaml').read_text()), .05, .15)
    for name in ('local_costmap','global_costmap'):
        data[name][name]['ros__parameters']['footprint']=json.dumps(
            [[-.24089,-.19984],[.15911,-.19984],[.15911,.20016],[-.24089,.20016]])
    data=differential_clearance_profile(data)
    controller = data['controller_server']['ros__parameters']
    controller['odom_topic'] = '/test_odom'
    costmap = data['local_costmap']['local_costmap']['ros__parameters']
    costmap.update(global_frame='map', robot_base_frame='base_footprint',
                   plugins=['static_layer'], update_frequency=10., publish_frequency=5.,
                   transform_tolerance=.5)
    costmap['static_layer'] = dict(plugin='nav2_costmap_2d::StaticLayer',
                                  map_subscribe_transient_local=True, map_topic='/test_map')
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as stream:
        yaml.safe_dump(data, stream)
        config = stream.name
    log = tempfile.TemporaryFile(mode='w+')
    process = subprocess.Popen(['ros2', 'run', 'nav2_controller', 'controller_server',
        '--ros-args', '--params-file', config], stdout=log, stderr=log, start_new_session=True)
    rclpy.init()
    node = rclpy.create_node('isolated_arrival_check')
    broadcaster = TransformBroadcaster(node)
    qos = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
    maps = node.create_publisher(OccupancyGrid, '/test_map', qos)
    odom = node.create_publisher(Odometry, '/test_odom', 10)
    commands = []
    node.create_subscription(Twist, '/cmd_vel', lambda msg: commands.append(msg), 10)
    yaw = [0.]
    position_x=[0.]

    def publish():
        now = node.get_clock().now().to_msg()
        tf = TransformStamped()
        tf.header.stamp, tf.header.frame_id, tf.child_frame_id = now, 'map', 'base_footprint'
        tf.transform.translation.x=position_x[0]
        tf.transform.rotation.z = math.sin(yaw[0] / 2)
        tf.transform.rotation.w = math.cos(yaw[0] / 2)
        broadcaster.sendTransform(tf)
        message = Odometry()
        message.header.stamp, message.header.frame_id = now, 'map'
        message.child_frame_id = 'base_footprint'
        message.pose.pose.orientation = tf.transform.rotation
        odom.publish(message)

    node.create_timer(.025, publish)
    grid = OccupancyGrid()
    grid.header.frame_id = 'map'
    grid.info.resolution, grid.info.width, grid.info.height = .05, 100, 100
    grid.info.origin.position.x = grid.info.origin.position.y = -2.5
    grid.info.origin.orientation.w = 1.
    grid.data = [0] * 10000
    if os.environ.get('TEST_ROTATION_OBSTACLE')=='1':
        # Outside the current body, but inside the swept rear corner at yaw 1.
        grid.data[44*100+50]=100
    maps.publish(grid)

    def wait(future, timeout=20):
        deadline = time.monotonic() + timeout
        while not future.done() and time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=.05)
        assert future.done(), 'ROS request timed out'
        return future.result()

    try:
        service = node.create_client(ChangeState, '/controller_server/change_state')
        assert service.wait_for_service(timeout_sec=15), 'Controller did not start'
        for transition in (1, 3):
            request = ChangeState.Request()
            request.transition.id = transition
            assert wait(service.call_async(request)).success, 'Lifecycle transition failed'
        action = ActionClient(node, FollowPath, '/follow_path')
        assert action.wait_for_server(timeout_sec=5)
        path = RosPath()
        path.header.frame_id = 'map'
        for x in (0., .12):
            pose = PoseStamped()
            pose.header.frame_id = 'map'
            pose.pose.position.x = x
            pose.pose.orientation.z = math.sin(.5)
            pose.pose.orientation.w = math.cos(.5)
            path.poses.append(pose)
        goal = FollowPath.Goal()
        goal.path, goal.controller_id, goal.goal_checker_id = path, 'FollowPath', 'goal_checker'
        handle = wait(action.send_goal_async(goal))
        assert handle.accepted, 'FollowPath rejected'
        deadline=time.monotonic()+.5
        while time.monotonic()<deadline:rclpy.spin_once(node,timeout_sec=.025)
        assert any(m.linear.x>0 for m in commands), 'Approach did not advance before entering XY tolerance'
        assert all(abs(m.angular.z)<1e-6 for m in commands), 'Aligned final heading before reaching position'
        position_x[0]=.03
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=.05)
        rotating = [msg for msg in commands if abs(msg.angular.z) > .01]
        assert rotating, 'Expected rotation within the 0.1 m position tolerance'
        assert all(abs(msg.linear.x) < 1e-6 and abs(msg.linear.y) < 1e-6 for msg in rotating), 'Translation during final alignment'
        assert max(abs(msg.angular.z) for msg in rotating) <= .15001
        print('Stationary-odom rotation range:', min(abs(msg.angular.z) for msg in rotating),
              max(abs(msg.angular.z) for msg in rotating), flush=True)
        assert min(abs(msg.angular.z) for msg in rotating[-10:]) >= .14, 'Rotation stuck below usable startup speed'
        # Drift back outside the original XY threshold after it has latched.
        before=len(commands);position_x[0]=0.
        deadline=time.monotonic()+1.
        while time.monotonic()<deadline:rclpy.spin_once(node,timeout_sec=.05)
        assert all(abs(m.linear.x)<1e-6 for m in commands[before:]), 'Translation resumed after position latch'
        yaw[0] = 1.
        result = wait(handle.get_result_async())
        assert result.status == 4, 'Expected success after final yaw alignment'
        print('PASS: reached XY then drifted to 0.12 m: translation stays locked; exact yaw succeeds')
        # The shortest heading difference across +/-pi is already within tolerance.
        yaw[0]=-math.pi+.02;position_x[0]=0.
        deadline=time.monotonic()+.2
        while time.monotonic()<deadline:rclpy.spin_once(node,timeout_sec=.025)
        path.poses[-1].pose.position.x=.05
        path.poses[-1].pose.orientation.z=math.sin((math.pi-.02)/2)
        path.poses[-1].pose.orientation.w=math.cos((math.pi-.02)/2)
        goal.path=path;before=len(commands)
        handle=wait(action.send_goal_async(goal));assert handle.accepted
        result=wait(handle.get_result_async());assert result.status==4
        assert all(abs(m.linear.x)<1e-6 and abs(m.angular.z)<1e-6 for m in commands[before:])
        print('PASS: +/-pi wrap uses shortest yaw; no unnecessary full turn')
        if os.environ.get('TEST_ROTATION_OBSTACLE')=='1':
            yaw[0]=0.;position_x[0]=0.;path.poses=[]
            for y in (0.,.8):
                p=PoseStamped();p.header.frame_id='map';p.pose.position.y=y
                p.pose.orientation.z=math.sin(math.pi/4);p.pose.orientation.w=math.cos(math.pi/4)
                path.poses.append(p)
            goal.path=path;before=len(commands)
            handle=wait(action.send_goal_async(goal));assert handle.accepted
            outcome=handle.get_result_async();deadline=time.monotonic()+2.
            while time.monotonic()<deadline:rclpy.spin_once(node,timeout_sec=.025)
            assert not outcome.done(),'Path-alignment turn aborted near swept obstacle'
            moving=commands[before:]
            assert any(abs(m.angular.z)>.14 for m in moving)
            assert all(abs(m.linear.x)<1e-6 and abs(m.linear.y)<1e-6 for m in moving)
            wait(handle.cancel_goal_async());wait(outcome)
            print('PASS: swept obstacle does not reject final-yaw or path-alignment pure rotation')
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
        print(log.read()[-4500:])
        log.close()


if __name__ == '__main__':
    main()
