"""The sole final cmd_vel publisher in patrol.launch.py; independent wall-clock watchdog."""
import math
import time
import rclpy
from rclpy.node import Node
from rclpy.clock import Clock, ClockType
from rclpy.qos import qos_profile_sensor_data
from geometry_msgs.msg import Twist
from sensor_msgs.msg import LaserScan
from nav_msgs.msg import Odometry
from std_msgs.msg import Bool
from .core import MotionGuard, positive


class VelocityGate(Node):
    def __init__(self):
        super().__init__('velocity_gate')
        self.guard = MotionGuard(
            positive(self.declare_parameter('max_linear', 0.2).value, 'max_linear'),
            positive(self.declare_parameter('max_angular', 0.3).value, 'max_angular'),
            positive(self.declare_parameter('watchdog_timeout', 3.0).value, 'watchdog_timeout'))
        self.v = self.w = 0.0
        self.output = self.create_publisher(Twist, 'cmd_vel', 10)
        self.create_subscription(Twist, 'nav2_cmd_vel', self.command, 10)
        self.create_subscription(Bool, '/ic382/allow_motion', self.allow, 10)
        self.create_subscription(LaserScan, 'scan_nav', self.scan, qos_profile_sensor_data)
        self.create_subscription(Odometry, 'odom', self.odom, qos_profile_sensor_data)
        self.create_timer(0.05, self.tick, clock=Clock(clock_type=ClockType.STEADY_TIME))

    def command(self, msg):
        self.v, self.w = msg.linear.x, msg.angular.z
        self.guard.command_at = time.monotonic()

    def allow(self, msg):
        self.guard.allow, self.guard.allowed_at = msg.data, time.monotonic()

    def scan(self, msg):
        if msg.ranges:
            self.guard.scan_at = time.monotonic()

    def odom(self, msg):
        self.guard.odom_at = time.monotonic()

    def tick(self):
        out = Twist()
        out.linear.x, out.angular.z = self.guard.command(time.monotonic(), self.v, self.w)
        self.output.publish(out)


def main(args=None):
    rclpy.init(args=args)
    node = VelocityGate()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if rclpy.ok():
            node.output.publish(Twist())
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
