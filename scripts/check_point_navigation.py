"""Regression: mode transition preserves AMCL; clicked goals retain stop/watchdog."""
from pathlib import Path
from unittest.mock import Mock
import time
import rclpy
from rclpy.task import Future
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import Bool
from robot_console import Console
from ic382_navigation.velocity_gate import VelocityGate

rclpy.init()
app=Console(Path(__file__).resolve().parents[1],test_mode=True)
gate=VelocityGate()
try:
    amcl=Mock();amcl.poll.return_value=None
    app.mode='LOCALIZATION';app.processes['localization']=amcl
    app.localization_active=True;app.global_requested=False
    calls=[];app.start=lambda name,command:calls.append((name,command));app.open_rviz=lambda:None
    app.start_navigation()
    assert app.processes['localization'] is amcl
    assert app.localization_active and not app.global_requested
    assert 'external_localization:=true' in calls[-1][1]
    app.point_client=Mock();app.point_client.server_is_ready.return_value=True
    response=Future();app.point_client.send_goal_async.return_value=response
    goal=PoseStamped();goal.header.frame_id='map';goal.pose.orientation.w=1.;goal.pose.position.x=1.
    app.point_goal(goal);app.point_client.send_goal_async.assert_not_called()
    app.feedback={'health':'','state':'IDLE'};app.feedback_at=time.monotonic()
    app.point_goal(goal);app.point_client.send_goal_async.assert_not_called()
    app.alignment_ok=True;app.alignment_at=time.monotonic()
    app.point_goal(goal);assert app.point_pending
    handle=Mock();handle.accepted=True;handle.get_result_async.return_value=Future()
    response.set_result(handle);assert app.point_handle is handle
    app.direct_permission=Mock();app.tick()
    assert app.direct_permission.publish.call_args.args[0].data
    now=time.monotonic();gate.guard.command_at=gate.guard.scan_at=gate.guard.odom_at=now
    gate.v=.9;gate.w=.8;gate.output=Mock()
    gate.allow(Bool(data=False));gate.direct(Bool(data=True));gate.tick()
    assert 0<gate.output.publish.call_args.args[0].linear.x<=gate.guard.max_linear
    gate.permissions['direct']=(True,now-5);gate.tick()
    assert gate.output.publish.call_args.args[0].linear.x==0., 'Dead direct heartbeat must stop'
    app.alignment_ok=False;app.tick()
    handle.cancel_goal_async.assert_called_once();assert app.point_handle is None
    app.feedback_at=now-5;app.tick()
    handle.cancel_goal_async.assert_called_once();assert app.point_handle is None
    assert not app.direct_permission.publish.call_args.args[0].data
    app.processes.clear()
    print('PASS: AMCL preserved, no unhealthy goal, clicked goal bridge, gated motion, dead heartbeat stop, health-loss cancellation')
finally:app.node.destroy_node();gate.destroy_node();rclpy.shutdown()
