#!/usr/bin/env python3
"""Read-only preflight for the Jetson camera/depth/TF/model inputs.

It never publishes commands or moves the robot. Run after the Astra driver and
the robot's TF tree are up.
"""
import argparse
import json
import math
import time

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rclpy.time import Time
from sensor_msgs.msg import CameraInfo, Image


class Preflight(Node):
    def __init__(self, args):
        super().__init__("perception_preflight")
        self.args = args
        self.counts = {"color": 0, "depth": 0, "info": 0}
        self.last = {"color": None, "depth": None, "info": None}
        self.first_at = {}
        self.last_at = {}
        self.create_subscription(
            Image, args.color_topic, self.on_color, qos_profile_sensor_data)
        self.create_subscription(
            Image, args.depth_topic, self.on_depth, qos_profile_sensor_data)
        self.create_subscription(
            CameraInfo, args.info_topic, self.on_info, qos_profile_sensor_data)
        self.tf_buffer = None
        try:
            from tf2_ros.buffer import Buffer
            from tf2_ros.transform_listener import TransformListener

            self.tf_buffer = Buffer()
            self.tf_listener = TransformListener(self.tf_buffer, self)
        except Exception as exc:  # pragma: no cover
            self.get_logger().error("TF unavailable: " + str(exc))
        self.create_timer(1.0, self.report)
        self.started = time.monotonic()

    def mark(self, key):
        now = time.monotonic()
        self.counts[key] += 1
        self.first_at.setdefault(key, now)
        self.last_at[key] = now

    def on_color(self, msg):
        self.last["color"] = msg
        self.mark("color")

    def on_depth(self, msg):
        self.last["depth"] = msg
        self.mark("depth")

    def on_info(self, msg):
        self.last["info"] = msg
        self.mark("info")

    def report(self):
        elapsed = max(1e-6, time.monotonic() - self.started)
        info = self.last["info"]
        color = self.last["color"]
        depth = self.last["depth"]
        tf_ok = None
        if self.tf_buffer is not None:
            try:
                tf_ok = self.tf_buffer.can_transform(
                    self.args.base_frame, self.args.camera_frame, Time())
            except Exception:
                tf_ok = False
        report = {
            "elapsed_s": round(elapsed, 1),
            "rates_hz": {key: round(self.counts[key] / elapsed, 2)
                         for key in self.counts},
            "color_size": [color.width, color.height] if color else None,
            "depth_size": [depth.width, depth.height] if depth else None,
            "depth_encoding": depth.encoding if depth else None,
            "intrinsics": [info.k[0], info.k[4], info.k[2], info.k[5]] if info else None,
            "intrinsics_valid": bool(
                info and math.isfinite(info.k[0]) and info.k[0] > 0
                and math.isfinite(info.k[4]) and info.k[4] > 0),
            "tf_ok": tf_ok,
            "frame_id": color.header.frame_id if color else None,
        }
        print(json.dumps(report), flush=True)
        if elapsed >= self.args.seconds:
            rclpy.shutdown()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--color-topic", default="/camera/color/image_raw")
    parser.add_argument("--depth-topic", default="/camera/depth/image_raw")
    parser.add_argument("--info-topic", default="/camera/color/camera_info")
    parser.add_argument("--base-frame", default="base_link")
    parser.add_argument("--camera-frame", default="camera_color_optical_frame")
    parser.add_argument("--seconds", type=float, default=10.0)
    args = parser.parse_args()

    rclpy.init()
    node = Preflight(args)
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
