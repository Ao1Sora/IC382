#!/usr/bin/env python3
"""Interactive IC382 main program. Keyboard and ROS run in this process."""
import argparse
import json
import math
import os
from pathlib import Path
import select
import shutil
import signal
import sys
import termios
import time
import tty
import tempfile
import subprocess
import yaml
import rclpy
from rclpy.action import ActionClient
from rclpy.signals import SignalHandlerOptions
from rclpy.qos import QoSProfile, DurabilityPolicy, qos_profile_sensor_data
from sensor_msgs.msg import LaserScan
from geometry_msgs.msg import Twist, PoseWithCovarianceStamped, PointStamped, PoseStamped, PolygonStamped, Point32
from nav2_msgs.action import NavigateToPose
from visualization_msgs.msg import MarkerArray
from std_srvs.srv import Empty
from lifecycle_msgs.srv import GetState
from map_ui import desk_markers, select_desk
from map_catalog import MapCatalog, read_config, scene_ready
from std_msgs.msg import Bool, String
from ic382_interfaces.action import InspectDesk
from ic382_interfaces.srv import CompleteInspection
from keyboard_bindings import moveBindings, speedBindings
from process_control import terminate


def prepare_keyboard_repeat():
    """x11vnc defaults to suppressing X repeat; allow held terminal keys."""
    if not os.environ.get('DISPLAY') or not shutil.which('xset'):
        return
    if shutil.which('x11vnc'):
        # The query waits for the server to process the preceding remote command.
        for option in ('-R', '-Q'):
            try:
                subprocess.run(['x11vnc', option, 'repeat'], stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, timeout=3, check=False)
            except (OSError, subprocess.TimeoutExpired):
                pass
    for arguments in (['r', 'on'], ['r', 'rate', '250', '20']):
        subprocess.run(['xset']+arguments, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=3, check=False)


class Console:
    def __init__(self, root, test_mode=False):
        self.root = root
        self.test_mode = test_mode
        self.node = rclpy.create_node('ic382_robot_main')
        self.pub = self.node.create_publisher(Twist, '/cmd_vel', 10)
        self.allow = self.node.create_publisher(Bool, '/ic382/allow_motion', 10)
        self.pose_pub = self.node.create_publisher(PoseWithCovarianceStamped, '/initialpose', 10)
        self.global_localization = self.node.create_client(Empty, '/reinitialize_global_localization')
        self.nomotion = self.node.create_client(Empty, '/request_nomotion_update')
        self.amcl_state = self.node.create_client(GetState, '/amcl/get_state')
        self.node.create_subscription(PoseWithCovarianceStamped, '/amcl_pose', self.localization_pose, 10)
        self.localization_message = 'not running'
        self.localization_pending = False
        self.localization_active = False
        self.localization_poll = 0.
        self.localization_until = 0.
        self.localization_call = None
        self.global_requested = False
        self.last_global_key = -float('inf')
        self.node.create_subscription(String, '/ic382/mission_status', self.status, 10)
        self.client = ActionClient(self.node, InspectDesk, '/ic382/inspect_desk')
        self.point_client = ActionClient(self.node, NavigateToPose, '/navigate_to_pose')
        self.direct_permission = self.node.create_publisher(Bool, '/ic382/direct_navigation_active', 10)
        self.node.create_subscription(PoseStamped, '/goal_pose', self.point_goal, 10)
        self.point_handle = None
        self.point_pending = False
        self.feedback_at = -float('inf')
        self.pose_at = -float('inf')
        self.nomotion_needed = False
        self.localization_scan_at = -float('inf')
        self.localization_scan_stamp = None
        self.localization_used_scan_stamp = None
        self.node.create_subscription(LaserScan, '/scan', self.localization_scan, qos_profile_sensor_data)
        self.complete = self.node.create_client(CompleteInspection, '/ic382/complete_inspection')
        self.config_path = root/'ros2_ws/src/ic382_navigation/config/physical_runtime.yaml'
        self.config = read_config(self.config_path)
        self.alignment_message='manual initial pose required'
        self.alignment_ok=False;self.alignment_at=-float('inf')
        self.navigation_stop_reason=''
        self.node.create_subscription(String,'/ic382/local_alignment',self.alignment_status,10)
        self.body_pub = self.node.create_publisher(PolygonStamped, '/ic382/body_footprint', 10)
        self.body_laser_transform = None
        self.catalog = MapCatalog(root, self.config_path)
        self.map_items = None
        self.map_index = 0
        self.saving_map = None
        self.desks = [str(d['id']) for d in self.config.get('inspection', {}).get('desks', [])]
        self.desk_index = 0
        self.node.create_subscription(PointStamped, '/clicked_point', self.map_click, 10)
        self.markers = self.node.create_publisher(MarkerArray, '/ic382/desks',
                            QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL))
        self.node.create_timer(0.5, self.publish_desks)
        self.processes = {}
        self._test_logs = tempfile.TemporaryDirectory(prefix='ic382-console-test-') if test_mode else None
        self.log_dir = Path(self._test_logs.name) if self._test_logs else Path.home()/'.local/state/ic382'
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.mode = 'MANUAL'
        self.notice = 'Ready. Movement keys work immediately; no Enter required.'
        self.feedback = {}
        self.goal = None
        self.pending_goal = False
        self.generation = 0
        self.speed, self.turn = .05, .15
        self.x = self.y = self.w = 0.
        self.omni = False
        self.last_move = 0.
        self.last_key = '-'
        self.command = None
        self.quit = False

    def spin(self, seconds=.01):
        rclpy.spin_once(self.node, timeout_sec=seconds)

    def localization_pose(self, message):
        self.pose_at = time.monotonic()
        p = message.pose.pose.position
        c = message.pose.covariance
        self.localization_message = f'estimate x={p.x:.2f} y={p.y:.2f}; variance xy={c[0]:.3f}/{c[7]:.3f} (verify scan alignment)'

    def relocalize(self, global_search=False):
        if 'save-map' in self.processes: raise RuntimeError('Wait for map saving to finish.')
        if not Path(self.config.get('map') or '').is_file(): raise RuntimeError('Select a saved map with L first.')
        if self.mode != 'LOCALIZATION':
            self.stop_tasks()
            self.lidar()
            self.start('localization', ['ros2', 'launch', str(self.root/'scripts/localization_only.launch.py'),
                                        'config_file:='+str(self.config_path)])
            self.mode = 'LOCALIZATION'
            self.open_rviz()
        self.stop_velocity()
        self.global_requested = global_search
        self.omni = False
        self.localization_message = 'waiting for AMCL global search' if global_search else 'set actual position and heading with 2D Pose Estimate'
        self.notice = ('Global search: use i/,/j/l to assist at low speed; SPACE stops motion, X ends localization.'
                       if global_search else 'Set 2D Pose Estimate first; local scan/map refinement runs at 1 Hz.')

    def localization_scan(self, message):
        if message.ranges:
            self.localization_scan_at = time.monotonic()
            self.localization_scan_stamp = (message.header.stamp.sec, message.header.stamp.nanosec)

    def localization_tick(self):
        now = time.monotonic()
        if self.mode not in ('LOCALIZATION', 'NAVIGATION') or now-self.localization_poll < 1.: return
        self.localization_poll = now
        if not self.localization_pending and self.amcl_state.service_is_ready():
            self.localization_pending = True
            def state(future):
                self.localization_pending = False
                self.localization_active = future.result().current_state.id == 3
            self.amcl_state.call_async(GetState.Request()).add_done_callback(state)
        if not self.localization_active: return
        if self.localization_call is not None and not self.localization_call.done(): return
        if self.global_requested and self.global_localization.service_is_ready():
            self.global_requested = False
            self.localization_until = float('inf')
            self.localization_call = self.global_localization.call_async(Empty.Request())
            self.nomotion_needed = True
        elif (self.nomotion.service_is_ready()
              and now-self.localization_scan_at < 1.
              and self.localization_scan_stamp != self.localization_used_scan_stamp):
            # One request per second, including while turning. AMCL applies the
            # request to an incoming scan; never reset the pose or global particles.
            self.localization_call = self.nomotion.call_async(Empty.Request())
            self.localization_used_scan_stamp = self.localization_scan_stamp
            self.nomotion_needed = False

    def publish_desks(self):
        desks = [] if self.mode == 'SLAM' or self.map_items is not None else self.config.get('inspection', {}).get('desks', [])
        self.markers.publish(desk_markers(desks,
                             self.desk_index, self.node.get_clock().now().to_msg()))

    def publish_body(self):
        # Keep the drawing attached to base_footprint even when Nav2 costmaps stop.
        # Costmap polygons in map coordinates otherwise remain at their last pose in RViz.
        settings = self.config.get('inspection', {})
        polygon = settings.get('robot_footprint')
        if settings.get('laser_body_bounds'):
            from ament_index_python.packages import get_package_share_directory
            from ic382_navigation.runtime_config import laser_body_footprint
            if self.body_laser_transform is None:
                base = Path(get_package_share_directory('turn_on_wheeltec_robot'))
                car = yaml.safe_load((base/'config/wheeltec_param.yaml').read_text())['car_mode']
                transform = yaml.safe_load((base/'config/robot_model.yaml').read_text())['robot_model'][car]['base_to_laser']
                self.body_laser_transform = [transform[0],transform[1],transform[3]]
            polygon = laser_body_footprint(settings['laser_body_bounds'], self.body_laser_transform)
        if not polygon:
            return
        if isinstance(polygon,str): polygon=json.loads(polygon)
        message=PolygonStamped()
        message.header.frame_id='base_footprint'
        message.header.stamp=self.node.get_clock().now().to_msg()
        message.polygon.points=[Point32(x=float(x),y=float(y),z=0.) for x,y in polygon]
        self.body_pub.publish(message)

    def open_maps(self):
        if self.map_items is not None: return
        if self.mode == 'SLAM':
            raise RuntimeError('Save with V and stop SLAM with X before choosing a map.')
        if 'save-map' in self.processes:
            raise RuntimeError('Map saving is still running. Wait for the saved message.')
        self.stop_tasks()
        self.map_items = self.catalog.discover(self.config)
        self.map_index = next((i for i,item in enumerate(self.map_items)
                              if item['config']['map'] == self.config.get('map')), 0)
        self.notice = 'Map menu: j/k or arrows to select, Enter to load, Esc to close.'

    def apply_map(self):
        if not self.map_items: raise RuntimeError('No saved maps found; use S then V to create one.')
        item = self.map_items[self.map_index]
        config = self.catalog.activate(item)
        self.config = config
        self.desks = [str(d['id']) for d in config.get('inspection', {}).get('desks', [])]
        self.desk_index = 0
        self.map_items = None
        # Remove markers from the previous scene, including desks no longer present.
        from visualization_msgs.msg import Marker
        clear = Marker(); clear.action = Marker.DELETEALL
        self.markers.publish(MarkerArray(markers=[clear]))
        self.publish_desks()
        # Restart RViz to discard the previously latched map/robot pose display.
        terminate(self.processes.pop('rviz', None))
        # A saved image alone cannot place laser/robot frames in map. Always run AMCL.
        self.relocalize()
        self.notice = 'Loaded '+item['name']+'. Set 2D Pose Estimate first; bounded local refinement runs at 1 Hz.'
        if not item['ready']:
            self.notice += ' Inspection still needs desk/keepout data.'

    def map_click(self, message):
        if self.mode == 'SLAM' or self.map_items is not None:
            self.notice = 'Desk selection is disabled while mapping or choosing a map.'
            return
        if message.header.frame_id != 'map':
            self.notice = 'Select desks in the map frame.'
            return
        index = select_desk(self.config.get('inspection', {}).get('desks', []),
                            message.point.x, message.point.y)
        if index is None:
            self.notice = 'Click on or near a labelled desk using Publish Point.'
            return
        self.desk_index = index
        self.publish_desks()
        self.notice = 'Selected '+self.desks[index]+' in RViz. Return to console and press P to inspect.'

    def open_rviz(self):
        if not os.environ.get('DISPLAY'):
            raise RuntimeError('RViz needs the Jetson desktop; start the console in its terminal.')
        self.start('rviz', ['ros2', 'run', 'rviz2', 'rviz2', '-d', str(self.root/'scripts/robot_navigation.rviz')])

    def status(self, message):
        try:
            self.feedback = json.loads(message.data)
            self.feedback_at = time.monotonic()
        except ValueError:
            pass

    def alignment_status(self,message):
        try:
            data=json.loads(message.data)
            self.alignment_ok=bool(data.get('healthy',False));self.alignment_at=time.monotonic()
            self.alignment_message=data.get('state','unknown')
            if 'before_score' in data:
                self.alignment_message+=' (score %.2f)' % data['before_score']
        except ValueError:pass

    def start(self, name, command):
        if name in self.processes and self.processes[name].poll() is None:
            return
        if self.test_mode:
            raise RuntimeError('Test mode disables hardware and task launches')
        with (self.log_dir/(name+'.log')).open('a') as log:
            self.processes[name] = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                                    start_new_session=True)

    def stop_velocity(self):
        self.x = self.y = self.w = 0.
        self.pub.publish(Twist())

    def point_goal(self, message):
        if self.mode != 'NAVIGATION':
            self.notice = 'Press N before using Nav2 Goal.'; return
        if self.goal is not None or self.pending_goal or self.point_handle is not None or self.point_pending:
            self.notice = 'A task is active. X stops it before choosing a new target.'; return
        if message.header.frame_id != 'map' or not all(math.isfinite(v) for v in
                (message.pose.position.x,message.pose.position.y,message.pose.orientation.z,message.pose.orientation.w)):
            self.notice = 'Invalid map goal.'; return
        if not self.navigation_healthy() or not self.point_client.server_is_ready():
            self.notice = 'Navigation/localization is not ready: '+str(self.feedback.get('health','waiting')); return
        generation = self.generation
        self.navigation_stop_reason=''
        request = NavigateToPose.Goal(); request.pose = message
        self.point_pending = True
        def accepted(future):
            handle = future.result()
            if generation != self.generation:
                if handle.accepted: handle.cancel_goal_async()
                return
            self.point_pending = False
            if not handle.accepted:
                self.notice = 'Nav2 goal rejected.'; return
            self.point_handle = handle
            self.notice = 'Navigating to clicked point. SPACE or X cancels.'
            def finished(f):
                if generation != self.generation: return
                self.point_handle = None
                self.direct_permission.publish(Bool(data=False))
                status=f.result().status
                self.notice = ('Point navigation canceled: '+self.navigation_stop_reason
                    if status==5 and self.navigation_stop_reason else 'Point navigation finished; status='+str(status))
            handle.get_result_async().add_done_callback(finished)
        self.point_client.send_goal_async(request).add_done_callback(accepted)

    def navigation_healthy(self):
        return not self.navigation_health_reason()

    def navigation_health_reason(self):
        now=time.monotonic()
        if self.config.get('localization',{}).get('local_scan_match',False):
            if not self.alignment_ok:return 'alignment_unhealthy: '+self.alignment_message
            if now-self.alignment_at>3.:return 'alignment_heartbeat_stale'
        if now-self.feedback_at>=1.:return 'mission_health_heartbeat_stale'
        if self.feedback.get('health')!='':return 'mission_health: '+str(self.feedback.get('health','missing'))
        if self.feedback.get('state')!='IDLE':return 'mission_state: '+str(self.feedback.get('state','missing'))
        return ''

    def stop_tasks(self, preserve_localization=False):
        self.generation += 1
        self.pending_goal = False
        self.point_pending = False
        self.direct_permission.publish(Bool(data=False))
        if self.point_handle is not None:
            self.point_handle.cancel_goal_async(); self.point_handle = None
        self.allow.publish(Bool(data=False))
        if self.goal is not None:
            self.goal.cancel_goal_async()
            self.goal = None
        self.stop_velocity()
        # Stop the navigation publisher before resuming manual commands.
        for name in ('navigation', 'slam', 'map-preview', 'localization'):
            if preserve_localization and name == 'localization': continue
            terminate(self.processes.pop(name, None))
        self.feedback = {}
        if not preserve_localization:
            self.localization_active = False
            self.global_requested = False
        self.mode = 'MANUAL'
        self.stop_velocity()
        self.notice = 'Task stopped. Manual control ready.'

    def lidar(self):
        self.start('lidar', ['ros2', 'launch', 'turn_on_wheeltec_robot', 'wheeltec_lidar.launch.py'])

    def start_slam(self):
        if self.mode == 'SLAM':
            self.open_rviz()
            return
        self.stop_tasks()
        terminate(self.processes.pop('rviz', None))
        self.lidar()
        from ament_index_python.packages import get_package_share_directory
        params = Path(get_package_share_directory('wheeltec_slam_toolbox'))/'config/mapper_params_online_async.yaml'
        self.start('slam', ['ros2', 'run', 'slam_toolbox', 'async_slam_toolbox_node', '--ros-args',
                           '--params-file', str(params), '-r', 'odom:=odom_combined'])
        self.mode = 'SLAM'
        self.publish_desks()
        self.open_rviz()
        self.notice = 'SLAM running; drive with movement keys. V saves map; X stops.'

    def start_navigation(self):
        if 'save-map' in self.processes:
            raise RuntimeError('Wait for map saving to finish before starting navigation.')
        if self.mode == 'NAVIGATION':
            self.open_rviz()
            return
        # Validate before stopping a working mapping session.
        for name in ('map', 'navigation_map'):
            path = Path(str(self.config.get(name, ''))).expanduser()
            if not path.is_absolute(): path = self.config_path.parent/path
            if not path.is_file(): raise RuntimeError('Missing configured '+name)
        if not self.desks: raise RuntimeError('Selected map has no matched desks; inspection is not configured.')
        if 'localization' not in self.processes:
            self.relocalize()
        self.stop_tasks(preserve_localization=True)
        self.lidar()
        self.start('navigation', ['bash', str(self.root/'run.sh'), 'navigate',
                                 'config_file:='+str(self.config_path), 'start_hardware:=false',
                                 'external_localization:=true'])
        self.mode = 'NAVIGATION'
        self.open_rviz()
        self.notice = 'Existing AMCL retained. RViz Nav2 Goal: click/drag target. Publish Point selects desks; P inspects.'

    def inspect(self):
        if self.point_handle is not None or self.point_pending:
            raise RuntimeError('Point navigation is active. X cancels before desk inspection.')
        if self.mode != 'NAVIGATION':
            raise RuntimeError('Press N to start navigation first')
        if self.pending_goal or self.goal is not None:
            raise RuntimeError('An inspection is already active')
        if not self.client.server_is_ready():
            raise RuntimeError('Inspection server not ready; wait or check navigation.log')
        goal = InspectDesk.Goal()
        goal.desk_id = self.desks[self.desk_index]
        generation = self.generation
        self.pending_goal = True
        future = self.client.send_goal_async(goal, feedback_callback=lambda f: self.feedback.update(
            state=f.feedback.state, point_id=f.feedback.point_id, task_id=f.feedback.task_id,
            completed_points=f.feedback.completed_points))
        def accepted(f):
            handle = f.result()
            if generation != self.generation:
                if handle.accepted: handle.cancel_goal_async()
                return
            self.pending_goal = False
            if not handle.accepted:
                self.notice = 'Inspection rejected (check localization, sensors and desk configuration).'
                return
            self.goal = handle
            def finished(result):
                if generation != self.generation: return
                self.notice = 'Inspection result: '+result.result().result.message
                self.goal = None
            handle.get_result_async().add_done_callback(finished)
        future.add_done_callback(accepted)
        self.notice = 'Inspection requested: '+goal.desk_id

    def acknowledge(self):
        if self.mode != 'NAVIGATION' or self.feedback.get('state') != 'WAITING_FOR_WORK':
            raise RuntimeError('No inspection point is waiting for work completion')
        if not self.complete.service_is_ready(): raise RuntimeError('Completion service unavailable')
        request = CompleteInspection.Request()
        request.task_id = self.feedback['task_id']
        request.point_id = self.feedback['point_id']
        request.success = True
        future = self.complete.call_async(request)
        future.add_done_callback(lambda f: setattr(self, 'notice', 'Work confirmation: '+f.result().message))

    def key(self, key):
        self.last_key = repr(key)
        if key == '\x03' or (self.command is None and key == 'Q'):
            self.quit = True
            return
        if self.map_items is not None:
            if key in ('\x1b', 'L', 'X', ' '):
                self.map_items = None
                self.notice = 'Map menu closed. Manual control; press N to navigate.'
            elif key in ('j', '\x1b[B') and self.map_items:
                self.map_index = (self.map_index+1)%len(self.map_items)
            elif key in ('k', '\x1b[A') and self.map_items:
                self.map_index = (self.map_index-1)%len(self.map_items)
            elif key in ('\r', '\n'): self.apply_map()
            return
        if self.command is not None:
            if key in ('\r', '\n'):
                command, self.command = self.command, None
                parts = command.split()
                if len(parts) != 4 or parts[0] != 'pose':
                    raise RuntimeError('Command syntax: :pose x_metres y_metres yaw_radians')
                if self.mode not in ('NAVIGATION', 'LOCALIZATION'): raise RuntimeError('Start N or G before setting pose')
                x, y, yaw = map(float, parts[1:])
                if not all(math.isfinite(v) for v in (x,y,yaw)): raise RuntimeError('Pose must be finite')
                msg = PoseWithCovarianceStamped()
                msg.header.frame_id = 'map'; msg.header.stamp = self.node.get_clock().now().to_msg()
                msg.pose.pose.position.x = x; msg.pose.pose.position.y = y
                msg.pose.pose.orientation.z = math.sin(yaw/2); msg.pose.pose.orientation.w = math.cos(yaw/2)
                msg.pose.covariance[0] = msg.pose.covariance[7] = .25
                msg.pose.covariance[35] = .0685
                self.pose_pub.publish(msg)
                self.notice = 'Initial pose sent. Verify localization before pressing P.'
            elif key == '\x1b': self.command = None
            elif key in ('\x7f', '\b'): self.command = self.command[:-1]
            elif key.isprintable(): self.command += key
            return
        if key in ('X', 'M') or (self.mode == 'NAVIGATION' and key in (' ', 'k')):
            self.stop_tasks()
        elif key == 'S': self.start_slam()
        elif key == 'N': self.start_navigation()
        elif key == 'R': self.open_rviz()
        elif key == 'L': self.open_maps()
        elif key == 'G':
            now = time.monotonic()
            new_press = now-self.last_global_key > .6
            self.last_global_key = now
            if new_press: self.relocalize(global_search=True)
        elif key == 'P': self.inspect()
        elif key == 'C': self.acknowledge()
        elif key == 'D':
            if self.desks: self.desk_index = (self.desk_index+1)%len(self.desks)
        elif key == ':':
            if self.goal or self.pending_goal: raise RuntimeError('Stop inspection before editing initial pose')
            self.stop_velocity(); self.command = ''
        elif key == 'V':
            if self.mode != 'SLAM': raise RuntimeError('Map saving requires SLAM mode')
            if 'save-map' in self.processes: raise RuntimeError('Map saving is already running')
            path = self.root/'maps'/time.strftime('%Y%m%d-%H%M%S')/'map'
            path.parent.mkdir(parents=True, exist_ok=True)
            self.start('save-map', ['ros2', 'run', 'nav2_map_server', 'map_saver_cli', '-f', str(path)])
            self.saving_map = path.with_suffix('.yaml')
            self.notice = 'Saving map: '+str(path)+'; wait for saved message before X.'
        elif self.mode in ('MANUAL', 'SLAM', 'LOCALIZATION'):
            if key in (' ', 'k'): self.stop_velocity()
            elif key == 'b':
                self.stop_velocity()
                if self.mode == 'LOCALIZATION':
                    self.notice = 'Localization assist uses NORMAL differential drive.'
                else: self.omni = not self.omni
            elif key in speedBindings:
                v, w = speedBindings[key]
                self.speed = min(.1, self.speed*v); self.turn = min(.3, self.turn*w)
            elif key in moveBindings:
                if self.mode == 'LOCALIZATION' and (not self.localization_active or self.global_requested):
                    self.stop_velocity()
                    self.notice = 'Wait for AMCL global search before assisting motion.'
                    return
                x, w = moveBindings[key]
                if self.omni and key in ('.', 'm'): w = -w
                speed = min(self.speed, .05) if self.mode == 'LOCALIZATION' else self.speed
                turn = min(self.turn, .15) if self.mode == 'LOCALIZATION' else self.turn
                self.x = x*speed
                self.y = w*speed if self.omni else 0.
                self.w = 0. if self.omni else w*turn
                self.last_move = time.monotonic()
                if self.mode == 'LOCALIZATION': self.nomotion_needed = True

    def tick(self):
        for name, proc in list(self.processes.items()):
            if proc.poll() is not None:
                self.processes.pop(name)
                if name == 'save-map':
                    if proc.returncode == 0 and self.saving_map:
                        try:
                            self.catalog.register_saved(self.saving_map, self.config)
                            self.notice = 'Map saved. X then L to select it (new map has no desk/keepout data yet).'
                        except Exception as exc: self.notice = 'Map registration failed: '+str(exc)
                    else: self.notice = 'Map save failed; see save-map.log'
                    self.saving_map = None
                    continue
                if name in ('base', 'lidar', 'navigation', 'slam', 'localization'):
                    self.stop_tasks()
                    self.notice = f'{name} exited ({proc.returncode}); see {self.log_dir/name}.log'
                    if name == 'base': self.quit = True
                    break
                self.notice = f'{name} finished ({proc.returncode}); see {self.log_dir/name}.log'
        self.localization_tick()
        self.publish_body()
        direct = self.mode == 'NAVIGATION' and self.point_handle is not None and self.navigation_healthy()
        self.direct_permission.publish(Bool(data=direct))
        if self.point_handle is not None and not direct:
            self.navigation_stop_reason=self.navigation_health_reason() or ('mode_changed: '+self.mode)
            self.point_handle.cancel_goal_async(); self.point_handle = None
            detail=dict(time=time.time(),reason=self.navigation_stop_reason,mode=self.mode,last_key=self.last_key,
                alignment=self.alignment_message,alignment_age=time.monotonic()-self.alignment_at,
                mission_age=time.monotonic()-self.feedback_at,mission=self.feedback)
            try:
                with (self.log_dir/'navigation-cancellations.jsonl').open('a') as log:
                    log.write(json.dumps(detail,ensure_ascii=False)+'\n')
            except OSError as exc:self.node.get_logger().error('Cannot record cancellation: '+str(exc))
            self.notice = 'Point navigation canceled: '+self.navigation_stop_reason
        if self.mode == 'LOCALIZATION' and (not self.localization_active or self.global_requested):
            self.stop_velocity()
        if self.mode in ('MANUAL', 'SLAM', 'LOCALIZATION'):
            if time.monotonic()-self.last_move > .5 or self.command is not None or self.map_items is not None:
                self.x = self.y = self.w = 0.
            twist = Twist()
            twist.linear.x, twist.linear.y, twist.angular.z = self.x, self.y, self.w
            self.pub.publish(twist)
        # In navigation mode only the existing velocity gate publishes motion.

    def draw(self):
        if self.map_items is not None:
            lines = ['IC382 MAP SELECTOR - robot stopped', '='*72,
                     'j/k (or arrows): choose | Enter: load | Esc/L: close',
                     'All maps start localization. Matched scene = inspection data available.', '']
            start = max(0, self.map_index-5)
            for i,item in enumerate(self.map_items[start:start+12], start):
                state = 'MATCHED SCENE' if item['ready'] else 'MAP ONLY'
                active = ' [current]' if item['config']['map'] == self.config.get('map') else ''
                lines.append(('> ' if i == self.map_index else '  ')+f'{i+1}. {item["name"]} | {state}{active}')
            if not self.map_items: lines.append('No saved maps. Close this menu; S starts SLAM, V saves a map.')
            if self.map_items:
                lines += ['', 'Map: '+self.map_items[self.map_index]['config']['map']]
            lines += ['', self.notice]
            sys.stdout.write('\x1b[H'+''.join(line[:110]+'\x1b[K\n' for line in lines)+'\x1b[J')
            sys.stdout.flush()
            return
        desk = self.desks[self.desk_index] if self.desks else '(none configured)'
        text = [
            'IC382 ROBOT CONSOLE | Main program',
            '='*72,
            f'Mode: {self.mode:12}  Desk: {desk}  Drive: {"OMNI" if self.omni else "NORMAL"}',
            'Map: '+str(self.config.get('scene_name') or Path(self.config.get('map') or 'none').parent.name),
            f'Manual command x/y: {self.x:+.3f}/{self.y:+.3f} m/s  yaw: {self.w:+.3f} rad/s',
            f'Initial 0.05 m/s | Selected speed {self.speed:.3f} m/s, {self.turn:.3f} rad/s',
            'u i o / j k l / m , . : move | SPACE/k: STOP | b: omni',
            'q/z: overall speed | w/x: linear | e/c: angular (bounded)',
            '-'*72,
            'L choose map/scene | M manual | S SLAM | V save map',
            'N navigation + RViz | R reopen RViz | D next desk | P inspect desk',
            'G global relocalization + manual assist (limit .05 m/s, .15 rad/s)',
            'C confirm actual work completed at current inspection point',
            'X stop/cancel current task | Q / Ctrl+C stop and exit',
            ':pose x y yaw : set measured initial map pose (metres/radians)',
            '-'*72,
            'Mission: '+str(self.feedback.get('state', 'IDLE'))+'  Point: '+str(self.feedback.get('point_id','-')),
            'Navigation health: '+str(self.feedback.get('health', 'not received')),
            'Localization: '+self.localization_message,
            'Local scan/map match: '+self.alignment_message,
            'Status: '+self.notice,
            'Command: :'+self.command if self.command is not None else 'Last key: '+self.last_key,
            'Manual: 0.5s input timeout; no navigation obstacle avoidance.',
            'Logs: '+str(self.log_dir),
        ]
        sys.stdout.write('\x1b[H'+''.join(line[:110]+'\x1b[K\n' for line in text)+'\x1b[J')
        sys.stdout.flush()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--test-mode', action='store_true', help='Disable all hardware/task launches')
    parser.add_argument('--navigation', action='store_true', help='Open navigation and RViz at startup; sends no goal')
    parser.add_argument('--maps', action='store_true', help='Open the saved map selector at startup')
    parser.add_argument('--localize', action='store_true', help='Global relocalization with low-speed keyboard assistance')
    args, ros_args = parser.parse_known_args()
    if not sys.stdin.isatty(): raise RuntimeError('Use a VNC terminal or ssh -t')
    rclpy.init(args=ros_args, signal_handler_options=SignalHandlerOptions.NO)
    app = Console(Path(__file__).resolve().parents[1], args.test_mode)
    settings = termios.tcgetattr(sys.stdin)
    def interrupted(signum, frame): raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    signal.signal(signal.SIGHUP, interrupted)
    try:
        if not args.test_mode:
            prepare_keyboard_repeat()
            until = time.monotonic()+2
            while time.monotonic()<until: app.spin(.1)
            other = [p for p in app.node.get_publishers_info_by_topic('/cmd_vel') if p.node_name != app.node.get_name()]
            if other or app.node.count_subscribers('/cmd_vel') or app.node.count_publishers('/ic382/nav2_cmd_vel'):
                raise RuntimeError('Existing robot controller detected. Run: bash reset_robot.sh --start')
            app.start('base', ['ros2', 'launch', 'turn_on_wheeltec_robot', 'turn_on_wheeltec_robot.launch.py',
                'use_imu:='+str(app.config.get('localization', {}).get('use_imu',True)).lower()])
            until = time.monotonic()+25
            while app.node.count_subscribers('/cmd_vel') == 0:
                if app.processes['base'].poll() is not None or time.monotonic()>until:
                    raise RuntimeError('Chassis unavailable; check base.log')
                app.spin(.1)
        if args.localize:
            app.relocalize()
        elif args.maps:
            app.open_maps()
        elif args.navigation:
            app.start_navigation()
        sys.stdout.write('\x1b[?1049h\x1b[?25l')
        tty.setcbreak(sys.stdin.fileno())
        while not app.quit:
            if select.select([sys.stdin], [], [], .08)[0]:
                key = os.read(sys.stdin.fileno(), 1).decode('utf-8', errors='ignore')
                if key == '\x1b':
                    for _ in range(2):
                        if not select.select([sys.stdin], [], [], .025)[0]: break
                        key += os.read(sys.stdin.fileno(), 1).decode('utf-8', errors='ignore')
                try: app.key(key)
                except Exception as exc: app.notice = str(exc)
            app.spin(0.)
            app.tick()
            app.draw()
    except KeyboardInterrupt:
        pass
    finally:
        app.stop_tasks()
        for _ in range(5): app.stop_velocity(); app.spin(.05)
        for proc in app.processes.values(): terminate(proc)
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, settings)
        sys.stdout.write('\x1b[?25h\x1b[?1049lStopped. Robot console closed.\n'); sys.stdout.flush()
        app.node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__': main()
