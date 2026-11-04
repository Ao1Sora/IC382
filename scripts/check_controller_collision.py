#!/usr/bin/env python3
"""Regression: low-speed collision prediction must inspect cells ahead."""
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
from ic382_navigation.teacher_profile import differential_drive_profile, differential_clearance_profile
from ic382_navigation.runtime_config import laser_body_footprint
import json


def main():
    vendor = Path(get_package_share_directory('wheeltec_nav2'))
    data = differential_drive_profile(yaml.safe_load((vendor / 'param/wheeltec_params/param_senior_diff.yaml').read_text()), float(os.environ.get('TEST_LINEAR_LIMIT','0.05')), .15)
    model=yaml.safe_load((Path(get_package_share_directory('turn_on_wheeltec_robot'))/'config/robot_model.yaml').read_text())['robot_model']['senior_diff']['base_to_laser']
    body=laser_body_footprint(dict(front=.1,back=.3,left=.2,right=.2),[model[0],model[1],model[3]])
    for name in ('local_costmap','global_costmap'):
        data[name][name]['ros__parameters']['footprint']=json.dumps(body)
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

    def publish():
        now = node.get_clock().now().to_msg()
        tf = TransformStamped()
        tf.header.stamp, tf.header.frame_id, tf.child_frame_id = now, 'map', 'base_footprint'
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
    for row in range(40,61):grid.data[row*100+54]=100  # wall at x=0.20 m
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
        for x in (0., .8):
            pose = PoseStamped()
            pose.header.frame_id = 'map'
            pose.pose.position.x = x
            pose.pose.orientation.z = 0.
            pose.pose.orientation.w = 1.
            path.poses.append(pose)
        goal = FollowPath.Goal()
        goal.path, goal.controller_id, goal.goal_checker_id = path, 'FollowPath', 'goal_checker'
        handle = wait(action.send_goal_async(goal))
        assert handle.accepted, 'FollowPath rejected'
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=.05)
        maximum=max((abs(msg.linear.x) for msg in commands),default=0.)
        print('Maximum forward command with wall ahead:',maximum,flush=True)
        assert commands, 'No controller output'
        assert maximum<1e-6, 'Controller skipped predictive collision checks at 0.05 m/s'
        result=wait(handle.get_result_async())
        assert result.status==6, 'Expected collision-aborted action'
        print('PASS: stopped before footprint reached wall, measured body, no inflation')

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
