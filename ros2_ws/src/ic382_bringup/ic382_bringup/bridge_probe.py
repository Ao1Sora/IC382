"""Observe the bridge without issuing motion commands."""
import argparse
import json
import math
from pathlib import Path
import time

from ic382_bringup.health import has_valid_range, healthy


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--output", default="results/bridge.json")
    parser.add_argument("--commit", default="unknown")
    args = parser.parse_args()
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("--timeout must be positive and finite")

    import rclpy
    from rclpy.node import Node
    from rclpy.qos import qos_profile_sensor_data
    from nav_msgs.msg import Odometry
    from rosgraph_msgs.msg import Clock
    from sensor_msgs.msg import LaserScan

    rclpy.init(args=[])
    node = Node("ic382_bridge_probe")
    counts = dict(clock=0, odom=0, scan=0)
    first_clock = None
    last_clock = None
    valid_scans = 0
    last_clock_advance = -float("inf")

    def on_clock(msg):
        nonlocal first_clock, last_clock, last_clock_advance
        counts["clock"] += 1
        current = msg.clock.sec * 1000000000 + msg.clock.nanosec
        if last_clock is not None and current > last_clock:
            last_clock_advance = time.monotonic()
        last_clock = current
        if first_clock is None:
            first_clock = last_clock

    def on_odom(msg):
        counts["odom"] += 1

    def on_scan(msg):
        nonlocal valid_scans
        counts["scan"] += 1
        if has_valid_range(msg.ranges, msg.range_min, msg.range_max):
            valid_scans += 1

    subscriptions = [
        node.create_subscription(Clock, "/clock", on_clock, qos_profile_sensor_data),
        node.create_subscription(Odometry, "/odom", on_odom, qos_profile_sensor_data),
        node.create_subscription(LaserScan, "/scan", on_scan, qos_profile_sensor_data),
    ]
    try:
        start = time.monotonic()
        last_received = {}
        previous = counts.copy()
        while time.monotonic() - start < args.timeout:
            rclpy.spin_once(node, timeout_sec=0.1)
            for topic, count in counts.items():
                if count != previous[topic]:
                    last_received[topic] = time.monotonic()
            previous = counts.copy()
        subscribers = node.count_subscribers("/cmd_vel")
        recent = all(time.monotonic() - last_received.get(topic, -float("inf")) < 2.0
                     for topic in counts)
        clock_advancing = time.monotonic() - last_clock_advance < 2.0
        passed = recent and clock_advancing and healthy(
            counts, first_clock, last_clock, valid_scans, subscribers)
        report = dict(commit=args.commit, passed=passed, counts=counts,
                      valid_scan_frames=valid_scans, clock_start_ns=first_clock,
                      clock_end_ns=last_clock, cmd_vel_subscribers=subscribers,
                      messages_recent=recent, clock_advancing=clock_advancing)
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))
    finally:
        node.destroy_node()
        rclpy.shutdown()
    raise SystemExit(0 if passed else 1)

