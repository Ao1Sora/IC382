#!/usr/bin/env python3
"""Run the actual navigator BT against isolated mock actions; never use hardware."""
import os
import signal
import subprocess
import tempfile
import time
from pathlib import Path
assert os.environ.get('ROS_DOMAIN_ID') == '138'
import rclpy
import yaml
from action_msgs.msg import GoalStatus
from ament_index_python.packages import get_package_share_directory
from geometry_msgs.msg import PoseStamped, TransformStamped
from lifecycle_msgs.srv import ChangeState
from nav2_msgs.action import BackUp, ComputePathToPose, FollowPath, NavigateToPose
from nav2_msgs.srv import ClearEntireCostmap
from nav_msgs.msg import Odometry
from rclpy.action import ActionClient, ActionServer
from tf2_ros import TransformBroadcaster


def main():
    blocked = os.environ.get('TEST_BLOCKED_BACKUP') == '1'
    rclpy.init()
    node = rclpy.create_node('isolated_recovery_backends')
    events = []
    follows = [0]
    failures=int(os.environ.get("TEST_FAILURES","1"))
    robot_x=[0.]
    planning_positions=[]
    servers = []

    def compute(handle):
        events.append(handle.request.planner_id)
        planning_positions.append(robot_x[0])
        result = ComputePathToPose.Result()
        result.path.header.frame_id = 'map'
        for x in (robot_x[0], .8):
            pose = PoseStamped()
            pose.header.frame_id = 'map'
            pose.pose.position.x = x
            pose.pose.orientation.w = 1.
            result.path.poses.append(pose)
        handle.succeed()
        return result

    def follow(handle):
        follows[0] += 1
        events.append('follow')
        if follows[0] <= failures:
            handle.abort()
        else:
            handle.succeed()
        return FollowPath.Result()

    def backup(handle):
        events.append('backup')
        assert abs(handle.request.target.x - .1) < 1e-6
        assert abs(handle.request.speed - .05) < 1e-6
        assert handle.request.time_allowance.sec == 12
        if blocked:
            handle.abort()
        else:
            robot_x[0]-=.1
            events.append('backup_success')
            handle.succeed()
        return BackUp.Result()

    for kind, name, callback in ((ComputePathToPose, 'compute_path_to_pose', compute),
            (FollowPath, 'follow_path', follow), (BackUp, 'backup', backup)):
        servers.append(ActionServer(node, kind, name, callback))
    for name in ('local_costmap', 'global_costmap'):
        def clear(request, response, name=name):
            events.append('clear_' + name)
            return response
        servers.append(node.create_service(ClearEntireCostmap,
            f'/{name}/clear_entirely_{name}', clear))
    broadcaster = TransformBroadcaster(node)
    odom = node.create_publisher(Odometry, '/test_odom', 10)

    def publish():
        tf = TransformStamped()
        tf.header.stamp = node.get_clock().now().to_msg()
        tf.header.frame_id, tf.child_frame_id = 'map', 'base_footprint'
        tf.transform.rotation.w = 1.
        tf.transform.translation.x=robot_x[0]
        broadcaster.sendTransform(tf)
        msg = Odometry()
        msg.header.stamp = tf.header.stamp
        msg.header.frame_id, msg.child_frame_id = 'map', 'base_footprint'
        msg.pose.pose.orientation.w = 1.
        odom.publish(msg)

    node.create_timer(.025, publish)
    share = Path(get_package_share_directory('ic382_navigation'))
    # This test exercises single-goal navigation only; do not require unrelated
    # through-poses action servers while the navigator activates both interfaces.
    with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as stream:
        stream.write('<root main_tree_to_execute="Unused"><BehaviorTree ID="Unused"><AlwaysSuccess/></BehaviorTree></root>')
        unused_tree = stream.name
    params = dict(use_sim_time=False, global_frame='map', robot_base_frame='base_footprint',
        odom_topic='/test_odom', transform_tolerance=.3, default_server_timeout=1000,
        default_nav_through_poses_bt_xml=unused_tree,
        default_nav_to_pose_bt_xml=str(share/'behavior_trees/retreat_and_replan.xml'))
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as stream:
        yaml.safe_dump({'bt_navigator':{'ros__parameters':params}}, stream)
        config = stream.name
    log = tempfile.TemporaryFile(mode='w+')
    process = subprocess.Popen(['ros2','run','nav2_bt_navigator','bt_navigator',
        '--ros-args','--params-file',config,'-r','goal_pose:=/ic382/nav2_legacy_goal_pose'], stdout=log, stderr=log, start_new_session=True)

    def wait(future):
        end = time.monotonic() + 25
        while not future.done() and time.monotonic() < end:
            rclpy.spin_once(node, timeout_sec=.03)
        assert future.done(), 'ROS request timed out'
        return future.result()

    try:
        service = node.create_client(ChangeState, '/bt_navigator/change_state')
        assert service.wait_for_service(timeout_sec=15)
        for transition in (1, 3):
            request = ChangeState.Request()
            request.transition.id = transition
            assert wait(service.call_async(request)).success, 'Navigator lifecycle failed'
        action = ActionClient(node, NavigateToPose, '/navigate_to_pose')
        assert action.wait_for_server(timeout_sec=5)
        topic_pub=node.create_publisher(PoseStamped,'/goal_pose',10)
        sample=PoseStamped();sample.header.frame_id='map';sample.pose.orientation.w=1.
        sample.pose.position.x=.8;topic_pub.publish(sample)
        until=time.monotonic()+.4
        while time.monotonic()<until:rclpy.spin_once(node,timeout_sec=.02)
        assert not events, 'Native navigator duplicated the console-owned /goal_pose route'
        print('PASS: native goal topic isolated; guarded console is the sole goal bridge')
        goal = NavigateToPose.Goal()
        goal.pose.header.frame_id = 'map'
        goal.pose.pose.position.x = .8
        goal.pose.pose.orientation.w = 1.
        handle = wait(action.send_goal_async(goal))
        assert handle.accepted
        result = wait(handle.get_result_async())
        print('Recovery events:', events, flush=True)
        if blocked:
            assert result.status == GoalStatus.STATUS_ABORTED
            assert 'GridBasedWide' not in events and follows[0] == 1
            print('PASS: blocked retreat stops navigation; no wider-plan retry or blind motion')
        elif failures>2:
            assert result.status==GoalStatus.STATUS_ABORTED
            assert events.count('backup')==2 and follows[0]==3
            print('PASS: stops after two failed recovery attempts')
        else:
            assert result.status == GoalStatus.STATUS_SUCCEEDED
            assert events.index('backup_success') < events.index('GridBasedWide')
            assert abs(planning_positions[1]+.1)<1e-8
            assert follows[0] == failures+1
            print('PASS: failed tracking -> 10 cm backup -> wider planner -> success')
    finally:
        os.killpg(process.pid, signal.SIGINT)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
        log.seek(0)
        print(log.read()[-3000:])
        for server in servers:
            if isinstance(server, ActionServer):
                server.destroy()
        node.destroy_node()
        rclpy.shutdown()
        log.close()
        os.unlink(config)
        os.unlink(unused_tree)


if __name__ == '__main__':
    main()
