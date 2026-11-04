"""Exercise task dispatch against real ROS types with mocked task backends."""
from pathlib import Path
from unittest.mock import Mock
import rclpy
from rclpy.task import Future
from robot_console import Console

rclpy.init()
app = Console(Path(__file__).resolve().parents[1], test_mode=True)
commands = []
app.start = lambda name, command: commands.append((name, command))
app.open_rviz = lambda: app.start('rviz', ['rviz2'])
try:
    app.key('S')
    assert app.mode == 'SLAM'
    assert [x[0] for x in commands] == ['lidar', 'slam', 'rviz']
    assert all('turn_on_wheeltec_robot.launch.py' not in cmd for _, cmd in commands)
    app.key('V')
    assert commands[-1][0] == 'save-map'
    app.key('X')
    assert app.mode == 'MANUAL'
    # No real navigation/action server is started in this check.
    app.key('N')
    assert app.mode == 'NAVIGATION'
    assert commands[-2][0] == 'navigation'
    generation = app.generation
    app.key('N')
    assert app.generation == generation, 'Repeated N must not restart navigation'
    assert any('start_hardware:=false' in cmd for _, cmd in commands)
    app.key('i')
    assert app.x == 0., 'Manual motion must be ignored during navigation'
    from geometry_msgs.msg import PointStamped
    from map_ui import desk_markers, select_desk
    desk = app.config['inspection']['desks'][0]
    point = PointStamped(); point.header.frame_id = 'map'
    point.point.x = sum(p[0] for p in desk['polygon'])/len(desk['polygon'])
    point.point.y = sum(p[1] for p in desk['polygon'])/len(desk['polygon'])
    app.map_click(point)
    assert app.desk_index == 0
    assert app.goal is None and not app.pending_goal, 'Map selection must not send a goal'
    assert select_desk(app.config['inspection']['desks'], 1e6, 1e6) is None
    markers = desk_markers(app.config['inspection']['desks'], 0, app.node.get_clock().now().to_msg())
    assert any('[SELECTED]' in marker.text for marker in markers.markers)
    app.client = Mock()
    app.client.server_is_ready.return_value = True
    accepted = Future()
    app.client.send_goal_async.return_value = accepted
    app.key('P')
    assert app.pending_goal
    request = app.client.send_goal_async.call_args.args[0]
    assert request.desk_id == app.desks[app.desk_index]
    handle = Mock(); handle.accepted = True
    handle.get_result_async.return_value = Future()
    accepted.set_result(handle)
    assert app.goal is handle
    app.complete = Mock(); app.complete.service_is_ready.return_value = True
    app.complete.call_async.return_value = Future()
    app.feedback = dict(state='WAITING_FOR_WORK', task_id='test-task', point_id='point-2')
    app.key('C')
    request = app.complete.call_async.call_args.args[0]
    assert (request.task_id, request.point_id, request.success) == ('test-task', 'point-2', True)
    app.key('X')
    handle.cancel_goal_async.assert_called_once()
    assert app.mode == 'MANUAL'
    app.key('N'); app.key('P')
    late = Future(); app.client.send_goal_async.return_value = late
    app.stop_tasks(); app.key('N'); app.key('P'); app.stop_tasks()
    late_handle = Mock(); late_handle.accepted = True
    late.set_result(late_handle)
    late_handle.cancel_goal_async.assert_called_once()
    app.key('Q'); assert app.quit
    print('PASS: SLAM/save-map, navigation, desk goal, completion, cancellation, delayed goal cancellation, quit')
finally:
    app.node.destroy_node(); rclpy.shutdown()
