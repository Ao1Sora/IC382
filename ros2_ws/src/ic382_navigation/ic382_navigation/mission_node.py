import json
import time
import uuid
from pathlib import Path
import yaml
import rclpy
from rclpy.node import Node
from rclpy.clock import Clock, ClockType
from rclpy.qos import qos_profile_sensor_data
from nav_msgs.msg import Odometry
from sensor_msgs.msg import LaserScan
from std_msgs.msg import Bool, String
from std_srvs.srv import Trigger
from lifecycle_msgs.srv import GetState
from lifecycle_msgs.msg import State
from tf2_ros import Buffer, TransformListener
from .core import MissionEngine, positive, validate_route
from .events import Events
from .navigation import Navigator


class Mission(Node):
    def __init__(self):
        super().__init__('ic382_mission')
        path = self.declare_parameter('route', '').value
        with Path(path).expanduser().open(encoding='utf-8') as f:
            route = validate_route(yaml.safe_load(f))
        self.timeout = positive(self.declare_parameter('navigation_timeout', 240.0).value, 'timeout')
        self.sensor_timeout = positive(self.declare_parameter('sensor_timeout', 3.0).value, 'sensor_timeout')
        self.autostart = self.declare_parameter('autostart', False).value
        self.base_frame = self.declare_parameter('base_frame', 'base_footprint').value
        self.events = Events(self, uuid.uuid4().hex)
        self.nav = Navigator(self, self.health, self.events.emit, self.timeout)
        self.engine = MissionEngine(route, self.nav, self.events.emit)
        self.scan_at = self.odom_at = self.logger_at = -float('inf')
        self.logger_ok = False
        self.log_ack = 0
        self.last_ack_at = time.monotonic()
        self.terminal_event = None
        self.started_at = time.monotonic()
        self.ready_timeout = positive(self.declare_parameter('ready_timeout', 90.0).value, 'ready_timeout')
        self.tf = Buffer()
        self.tf_listener = TransformListener(self.tf, self)
        self.lifecycle = self.create_client(GetState, '/bt_navigator/get_state')
        self.nav2_active = False
        self.lifecycle_pending = False
        self.lifecycle_checked = -float('inf')
        self.allow = self.create_publisher(Bool, '/ic382/allow_motion', 10)
        self.status = self.create_publisher(String, '/ic382/mission_status', 10)
        self.create_subscription(LaserScan, 'scan_nav', self.scan, qos_profile_sensor_data)
        self.create_subscription(Odometry, 'odom', self.odom, qos_profile_sensor_data)
        self.create_subscription(Bool, '/ic382/logger_ready', self.logger, 10)
        self.create_subscription(String, '/ic382/log_ack', self.ack, 100)
        self.create_service(Trigger, '/ic382/start_mission', self.start)
        self.create_service(Trigger, '/ic382/cancel_mission', self.cancel)
        self.create_timer(0.1, self.tick, clock=Clock(clock_type=ClockType.STEADY_TIME))

    def scan(self, msg):
        if msg.ranges:
            self.scan_at = time.monotonic()

    def odom(self, msg):
        self.odom_at = time.monotonic()

    def logger(self, msg):
        self.logger_ok, self.logger_at = msg.data, time.monotonic()

    def ack(self, msg):
        try:
            data = json.loads(msg.data)
            if not isinstance(data.get('seq'), int):
                return
        except (ValueError, TypeError, AttributeError):
            return
        if data.get('run_id') == self.events.run_id and data.get('source') == self.get_name():
            self.log_ack = max(self.log_ack, data['seq'])
            self.last_ack_at = time.monotonic()

    def health(self):
        now = time.monotonic()
        if not self.logger_ok or now - self.logger_at > self.sensor_timeout:
            return 'logger_unavailable'
        if self.events.seq > self.log_ack and now - self.last_ack_at > 5.0:
            return 'journal_ack_timeout'
        if now - self.scan_at > self.sensor_timeout:
            return 'scan_stale'
        if now - self.odom_at > self.sensor_timeout:
            return 'odometry_stale'
        if not self.nav2_active or now - self.lifecycle_checked > 10.0:
            return 'nav2_inactive'
        if not self.tf.can_transform('map', self.base_frame, rclpy.time.Time()):
            return 'map_localization_unavailable'
        transform = self.tf.lookup_transform('map', self.base_frame, rclpy.time.Time())
        stamp = transform.header.stamp.sec + transform.header.stamp.nanosec / 1e9
        if self.get_clock().now().nanoseconds / 1e9 - stamp > 5.0:
            return 'localization_transform_stale'
        return ''

    def start(self, request, response):
        if not self.nav.ready():
            response.success, response.message = False, self.health() or 'nav2_not_ready'
            return response
        # Idle may have lasted longer than the acknowledgement timeout.
        self.last_ack_at = time.monotonic()
        response.success = self.engine.start(time.monotonic())
        response.message = self.engine.state
        return response

    def cancel(self, request, response):
        response.success = self.engine.cancel()
        self.allow.publish(Bool(data=False))
        response.message = self.engine.state
        return response

    def tick(self):
        now = time.monotonic()
        if not self.lifecycle_pending and now - self.lifecycle_checked > 2.0:
            if self.lifecycle.service_is_ready():
                self.lifecycle_pending = True
                self.lifecycle.call_async(GetState.Request()).add_done_callback(self.lifecycle_result)
        if self.autostart and self.engine.state == 'IDLE':
            if self.nav.ready():
                self.last_ack_at = now
                self.engine.start(now)
            elif now - self.started_at > self.ready_timeout:
                self.engine.fail('startup_timeout:' + (self.health() or 'nav2_not_ready'))
        active = self.engine.state in ('NAVIGATING', 'INSPECTING', 'TAGGING')
        if active and self.health():
            self.engine.fail(self.health())
        self.engine.tick(now)
        moving = self.engine.state == 'NAVIGATING' and self.nav.motion_allowed
        self.allow.publish(Bool(data=moving))
        terminal = self.engine.state in ('COMPLETED', 'FAILED', 'CANCELED')
        if terminal and self.terminal_event is None:
            self.terminal_event = self.events.seq
        self.status.publish(String(data=json.dumps({
            'run_id': self.events.run_id, 'state': self.engine.state,
            'desk_id': self.engine.waypoint['id'], 'round': self.engine.round,
            'health': self.health(), 'motion_allowed': moving,
            'journal_confirmed': terminal and self.log_ack >= self.terminal_event,
        })))

    def lifecycle_result(self, future):
        self.lifecycle_pending = False
        self.lifecycle_checked = time.monotonic()
        try:
            self.nav2_active = future.result().current_state.id == State.PRIMARY_STATE_ACTIVE
        except Exception:
            self.nav2_active = False


def main(args=None):
    rclpy.init(args=args)
    node = Mission()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        if rclpy.ok():
            node.engine.cancel('shutdown')
            node.allow.publish(Bool(data=False))
        deadline = time.monotonic() + 2.0
        while rclpy.ok() and time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.05)
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
