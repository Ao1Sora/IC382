#!/usr/bin/env python3
"""ROS interface regression with fake Nav2, not a physical navigation test.

Run in a separate ROS_DOMAIN_ID with the built workspace sourced.
Exercises real navigation action, velocity gate, journal and work service.
"""
import json
import threading
import time

import rclpy
from rclpy.action import ActionClient, ActionServer
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from geometry_msgs.msg import TransformStamped, Twist
from lifecycle_msgs.srv import GetState
from nav_msgs.msg import Odometry
from nav2_msgs.action import ComputePathToPose, NavigateToPose
from sensor_msgs.msg import LaserScan
from tf2_ros import TransformBroadcaster
from ic382_interfaces.action import InspectDesk
from ic382_interfaces.srv import CompleteInspection
from ic382_navigation.desk_navigation import DeskNavigation
from ic382_navigation.journal_node import Journal
from ic382_navigation.velocity_gate import VelocityGate


class FakeNav2(Node):
    def __init__(self):
        super().__init__('fake_nav2_interface_test')
        group = ReentrantCallbackGroup()
        self.xy = [0., 0.]
        self.tf = TransformBroadcaster(self)
        self.scan = self.create_publisher(LaserScan, '/scan_nav', 10)
        self.odom = self.create_publisher(Odometry, '/odom', 10)
        self.twist = self.create_publisher(Twist, '/nav2_cmd_vel', 10)
        self.create_service(GetState, '/bt_navigator/get_state', self.lifecycle, callback_group=group)
        self.planner = ActionServer(self, ComputePathToPose, '/compute_path_to_pose', self.plan, callback_group=group)
        self.navigator = ActionServer(self, NavigateToPose, '/navigate_to_pose', self.navigate, callback_group=group)
        self.create_timer(.05, self.tick, callback_group=group)

    def lifecycle(self, request, response):
        response.current_state.id = 3
        return response

    def plan(self, handle):
        result = ComputePathToPose.Result()
        result.path.header.frame_id = 'map'
        result.path.poses = [handle.request.start, handle.request.goal]
        handle.succeed()
        return result

    def navigate(self, handle):
        p = handle.request.pose.pose.position
        self.xy = [p.x, p.y]
        handle.succeed()
        return NavigateToPose.Result()

    def tick(self):
        stamp = self.get_clock().now().to_msg()
        transform = TransformStamped()
        transform.header.stamp = stamp
        transform.header.frame_id = 'map'
        transform.child_frame_id = 'base_footprint'
        transform.transform.translation.x, transform.transform.translation.y = self.xy
        transform.transform.rotation.w = 1.
        self.tf.sendTransform(transform)
        scan = LaserScan()
        scan.header.stamp = stamp
        scan.ranges = [10.] * 8
        self.scan.publish(scan)
        odom = Odometry()
        odom.header.stamp = stamp
        self.odom.publish(odom)
        # An upstream nonzero command must still be blocked during work.
        command = Twist()
        command.linear.x = .2
        self.twist.publish(command)


def main():
    rclpy.init()
    server, fake, journal, gate, caller = DeskNavigation(), FakeNav2(), Journal(), VelocityGate(), Node('desk_api_test_caller')
    nodes = [server, fake, journal, gate, caller]
    executor = MultiThreadedExecutor(num_threads=8)
    for node in nodes:
        executor.add_node(node)
    thread = threading.Thread(target=executor.spin, daemon=True)
    thread.start()
    action = ActionClient(caller, InspectDesk, '/ic382/inspect_desk')
    work = caller.create_client(CompleteInspection, '/ic382/complete_inspection')
    commands = []
    caller.create_subscription(Twist, '/cmd_vel', lambda m: commands.append((time.monotonic(), m.linear.x, m.angular.z)), 10)

    def wait(predicate, timeout=15):
        end = time.monotonic() + timeout
        while not predicate() and time.monotonic() < end:
            time.sleep(.02)
        assert predicate(), 'Timed out waiting for test condition'

    def resolved(future):
        wait(future.done)
        return future.result()

    def acknowledge(task_id, point, success=True):
        request = CompleteInspection.Request()
        request.task_id, request.point_id, request.success = task_id, point, success
        return resolved(work.call_async(request)).accepted

    try:
        wait(lambda: action.server_is_ready() and work.service_is_ready() and not server.health())
        assert not acknowledge('wrong', 'T04-A')
        invalid = resolved(action.send_goal_async(InspectDesk.Goal(desk_id='T99')))
        assert not invalid.accepted
        goal = resolved(action.send_goal_async(InspectDesk.Goal(desk_id='T04')))
        assert goal.accepted
        result = goal.get_result_async()
        concurrent = resolved(action.send_goal_async(InspectDesk.Goal(desk_id='T01')))
        assert not concurrent.accepted
        visited = []
        for _ in range(3):
            wait(lambda: server.state == 'WAITING_FOR_WORK' and server.point_id not in visited)
            point = server.point_id
            assert not result.done(), 'Navigation must wait for main-program work'
            assert not acknowledge('wrong', point)
            assert not acknowledge(server.task_id, 'wrong-point')
            stopped_at = time.monotonic()
            time.sleep(.4)
            samples = [s for s in commands if s[0] >= stopped_at + .15]
            assert samples and all(abs(v) < .001 and abs(w) < .001 for _, v, w in samples)
            assert acknowledge(server.task_id, point)
            assert not acknowledge(server.task_id, point), 'Duplicate work acknowledgement accepted'
            visited.append(point)
        response = resolved(result)
        assert response.status == 4 and response.result.success
        assert list(response.result.visited_points) == visited and len(set(visited)) == 3
        wait(lambda: server.log_ack >= server.events.seq)
        # A second task can be canceled while safely waiting for work.
        second = resolved(action.send_goal_async(InspectDesk.Goal(desk_id='T01')))
        assert second.accepted
        second_result = second.get_result_async()
        wait(lambda: server.state == 'WAITING_FOR_WORK' and server.desk_id == 'T01')
        resolved(second.cancel_goal_async())
        canceled = resolved(second_result)
        assert canceled.status == 5 and not canceled.result.success
        print(json.dumps({'passed': True, 'physical_navigation_test': False, 'visited_points': visited,
                          'invalid_desk_rejected': True, 'busy_rejected': True, 'wrong_and_duplicate_ack_rejected': True,
                          'zero_motion_while_waiting': True, 'cancel_status': canceled.status}))
    finally:
        executor.shutdown()
        thread.join(timeout=3)
        for node in reversed(nodes):
            node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
