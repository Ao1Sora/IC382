"""Continuous pedestrian safety monitor and the only YOLO inference process.

It publishes raw detections for the classifier and a boolean safety stop for
the velocity gate. The node never publishes motion commands.
"""
import json
import math
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from cv_bridge import CvBridge
from message_filters import ApproximateTimeSynchronizer, Subscriber
from sensor_msgs.msg import CameraInfo, Image
from std_msgs.msg import Bool, String

from ic382_interfaces.msg import (
    DetectedObject,
    DetectedObjectArray,
    SafetyState,
)

from ic382_perception.class_map import ROLE_PERSON
from ic382_perception.detector import get_detector
from ic382_perception.model_profile import resolve_profile
from ic382_perception.safety import (
    PersonSafetyGovernor,
    estimate_distance_from_height,
)
from ic382_perception.transform import sample_depth_patch, valid_intrinsics


class SafetyMonitorNode(Node):
    def __init__(self):
        super().__init__("safety_monitor")

        self.declare_parameter("detector_mode", "ultralytics")
        self.declare_parameter("model_path", "")
        self.declare_parameter("model_profile", "coco_bootstrap")
        self.declare_parameter("device", "")
        self.declare_parameter("imgsz", 640)
        self.declare_parameter("detection_conf", 0.35)
        self.declare_parameter("iou", 0.45)
        self.declare_parameter("half", False)
        self.declare_parameter("max_det", 50)
        self.declare_parameter("warmup", True)
        self.declare_parameter("max_fps", 20.0)
        self.declare_parameter("image_topic", "/camera/color/image_raw")
        self.declare_parameter("depth_topic", "/camera/depth/image_raw")
        self.declare_parameter("camera_info_topic", "/camera/color/camera_info")
        self.declare_parameter("depth_scale", 0.001)
        self.declare_parameter("depth_is_aligned", True)
        self.declare_parameter("min_depth_m", 0.1)
        self.declare_parameter("max_depth_m", 10.0)
        self.declare_parameter("stop_distance_m", 0.8)
        self.declare_parameter("clear_distance_m", 1.2)
        self.declare_parameter("confirm_frames", 3)
        self.declare_parameter("clear_frames", 5)
        self.declare_parameter("sensor_timeout", 0.5)
        self.declare_parameter("fail_safe_on_stale", True)
        self.declare_parameter("unknown_distance_stop", True)
        self.declare_parameter("person_height_m", 1.7)
        self.declare_parameter("detections_topic", "/ic382/perception/detections")
        self.declare_parameter("safety_state_topic", "/ic382/safety_state")
        self.declare_parameter("safety_stop_topic", "/ic382/safety_stop")
        self.declare_parameter("status_topic", "/ic382/perception/status")

        self.bridge = CvBridge()
        self.depth_scale = float(self.get_parameter("depth_scale").value)
        self.depth_is_aligned = bool(self.get_parameter("depth_is_aligned").value)
        self.min_depth = float(self.get_parameter("min_depth_m").value)
        self.max_depth = float(self.get_parameter("max_depth_m").value)
        self.person_height = float(self.get_parameter("person_height_m").value)
        self.max_fps = max(1.0, float(self.get_parameter("max_fps").value))
        self.min_period = 1.0 / self.max_fps
        self.last_process = -math.inf

        self.governor = PersonSafetyGovernor(
            stop_distance_m=float(self.get_parameter("stop_distance_m").value),
            clear_distance_m=float(self.get_parameter("clear_distance_m").value),
            confirm_frames=int(self.get_parameter("confirm_frames").value),
            clear_frames=int(self.get_parameter("clear_frames").value),
            sensor_timeout=float(self.get_parameter("sensor_timeout").value),
            fail_safe_on_stale=bool(self.get_parameter("fail_safe_on_stale").value),
            unknown_distance_stop=bool(self.get_parameter("unknown_distance_stop").value),
        )

        self.detector = None
        self.profile = None
        self.detector_ok = False
        self.detector_error = ""
        try:
            self.detector = get_detector(
                str(self.get_parameter("detector_mode").value),
                model_path=str(self.get_parameter("model_path").value),
                conf=float(self.get_parameter("detection_conf").value),
                iou=float(self.get_parameter("iou").value),
                imgsz=int(self.get_parameter("imgsz").value),
                device=str(self.get_parameter("device").value),
                half=bool(self.get_parameter("half").value),
                max_det=int(self.get_parameter("max_det").value),
                warmup=bool(self.get_parameter("warmup").value),
            )
            names = self.detector.load()
            self.profile = resolve_profile(
                str(self.get_parameter("model_profile").value), names)
            self.detector_ok = True
            if self.profile.degraded_reason:
                self.get_logger().error(
                    "Model profile degraded: " + self.profile.degraded_reason)
        except Exception as exc:  # noqa: BLE001 - keep the safety node alive
            self.detector_error = str(exc)
            self.get_logger().error("Detector unavailable: " + self.detector_error)

        self.detections_pub = self.create_publisher(
            DetectedObjectArray,
            str(self.get_parameter("detections_topic").value), 10)
        self.state_pub = self.create_publisher(
            SafetyState, str(self.get_parameter("safety_state_topic").value), 10)
        self.stop_pub = self.create_publisher(
            Bool, str(self.get_parameter("safety_stop_topic").value), 10)
        self.status_pub = self.create_publisher(
            String, str(self.get_parameter("status_topic").value), 10)

        self.camera_info = None
        color = Subscriber(
            self, Image, str(self.get_parameter("image_topic").value),
            qos_profile=qos_profile_sensor_data)
        depth = Subscriber(
            self, Image, str(self.get_parameter("depth_topic").value),
            qos_profile=qos_profile_sensor_data)
        self.create_subscription(
            CameraInfo, str(self.get_parameter("camera_info_topic").value),
            self.on_camera_info, qos_profile_sensor_data)
        self.sync = ApproximateTimeSynchronizer(
            [color, depth], queue_size=10, slop=0.1)
        self.sync.registerCallback(self.on_bundle)
        self.create_timer(0.1, self.watchdog)
        self.create_timer(1.0, self.publish_status)
        self.publish_status()

    def on_camera_info(self, msg):
        self.camera_info = msg

    def watchdog(self):
        decision = self.governor.tick(time.monotonic())
        self.publish_safety(decision, self.get_clock().now().to_msg())

    def on_bundle(self, image_msg, depth_msg):
        now = time.monotonic()
        if now - self.last_process < self.min_period:
            return
        self.last_process = now
        if not self.detector_ok:
            decision = self.governor.update(None, False, now)
            self.publish_safety(decision, image_msg.header.stamp)
            return

        try:
            image = self.bridge.imgmsg_to_cv2(image_msg, desired_encoding="bgr8")
            depth = (
                self.bridge.imgmsg_to_cv2(depth_msg)
                if self.depth_is_aligned else None
            )
        except Exception as exc:  # noqa: BLE001 - report stale rather than crash
            self.get_logger().error("Failed to decode camera images: " + str(exc))
            decision = self.governor.update(None, False, now)
            self.publish_safety(decision, image_msg.header.stamp)
            return

        try:
            detections = self.detector.detect(image)
        except Exception as exc:  # noqa: BLE001
            self.get_logger().error("Detection failed: " + str(exc))
            decision = self.governor.update(None, False, now)
            self.publish_safety(decision, image_msg.header.stamp)
            return

        info = self.camera_info
        fx, fy = (float(info.k[0]), float(info.k[4])) if info is not None else (0.0, 0.0)
        array = DetectedObjectArray()
        array.header = image_msg.header
        array.image_width = int(image_msg.width)
        array.image_height = int(image_msg.height)

        person_distances = []
        person_visible = False
        for detection in detections:
            role = self.profile.role_for(detection.class_id)
            distance = self.measure_distance(detection, depth, fy)
            item = DetectedObject()
            item.class_name = detection.class_name or self.detector.class_name(
                detection.class_id)
            item.class_id = int(detection.class_id)
            item.confidence = float(detection.confidence)
            item.center_x = float(detection.x_center)
            item.center_y = float(detection.y_center)
            item.width = float(detection.width)
            item.height = float(detection.height)
            item.distance_valid = distance is not None
            item.distance_m = float(distance) if distance is not None else math.nan
            array.objects.append(item)
            if role == ROLE_PERSON:
                person_visible = True
                if distance is not None:
                    person_distances.append(distance)

        self.detections_pub.publish(array)
        if person_visible:
            nearest = min(person_distances) if person_distances else math.nan
        else:
            nearest = None
        decision = self.governor.update(nearest, True, now)
        self.publish_safety(decision, image_msg.header.stamp, person_visible)

    def measure_distance(self, detection, depth, fy):
        if self.depth_is_aligned and depth is not None:
            raw = sample_depth_patch(
                depth,
                detection.x_center,
                detection.y_center + 0.3 * detection.height,
            )
            if raw is not None:
                distance = raw * self.depth_scale
                if self.min_depth <= distance <= self.max_depth:
                    return distance
        if self.profile is not None and self.profile.role_for(
                detection.class_id) == ROLE_PERSON:
            if valid_intrinsics(fy, fy):
                return estimate_distance_from_height(
                    fy, detection.height, self.person_height)
        return None

    def publish_safety(self, decision, stamp, person_visible=None):
        state = SafetyState()
        state.header.stamp = stamp
        state.stop = bool(decision.stop)
        state.state = decision.state
        state.person_visible = bool(
            person_visible if person_visible is not None
            else (decision.nearest_person_m == decision.nearest_person_m))
        state.nearest_person_m = (
            float(decision.nearest_person_m)
            if decision.nearest_person_m == decision.nearest_person_m else math.nan)
        state.stop_distance_m = float(self.governor.stop_distance_m)
        state.clear_distance_m = float(self.governor.clear_distance_m)
        state.source = self.get_name()
        self.state_pub.publish(state)

        stop = Bool()
        stop.data = bool(decision.stop)
        self.stop_pub.publish(stop)

    def publish_status(self):
        status = {
            "source": self.get_name(),
            "state": self.governor.state,
            "stop": self.governor.stop,
            "detector_ok": self.detector_ok,
            "detector_error": self.detector_error,
            "profile": self.profile.name if self.profile else "",
            "tagging_enabled": bool(self.profile.tagging_enabled) if self.profile else False,
            "degraded_reason": self.profile.degraded_reason if self.profile else "",
            "nearest_person_m": (
                self.governor.nearest_person_m
                if self.governor.nearest_person_m == self.governor.nearest_person_m
                else None),
        }
        self.status_pub.publish(
            String(data=json.dumps(status, allow_nan=False)))


def main(args=None):
    rclpy.init(args=args)
    node = SafetyMonitorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
