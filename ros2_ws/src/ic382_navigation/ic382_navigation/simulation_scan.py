"""Convert Isaac's negative no-return sentinel to infinity, not a fake obstacle."""
import math
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan


def normalize_ranges(ranges, minimum, maximum):
    return [float(v) if math.isfinite(v) and minimum <= v <= maximum
            else float('inf') for v in ranges]


class ScanFilter(Node):
    def __init__(self):
        super().__init__('navigation_scan_filter')
        self.maximum = float(self.declare_parameter('max_range', 200.0).value)
        self.pub = self.create_publisher(LaserScan, 'scan_nav', 10)
        self.create_subscription(LaserScan, 'scan', self.scan, qos_profile_sensor_data)

    def scan(self, msg):
        if not msg.ranges or msg.range_min <= 0 or msg.range_max <= msg.range_min:
            return
        msg.range_max = min(msg.range_max, self.maximum)
        if msg.range_max <= msg.range_min:
            return
        msg.ranges = normalize_ranges(msg.ranges, msg.range_min, msg.range_max)
        self.pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = ScanFilter()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
