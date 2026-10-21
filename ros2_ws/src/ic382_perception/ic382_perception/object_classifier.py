"""Object classification node.

Subscribes to camera image/depth/camera_info, runs YOLO detection, applies the
"log only, no tag" anomalous protocol, and publishes tagging and porter commands.

This module imports rclpy/cv_bridge/tf2 at module scope and is only loaded by the
object_classifier executable under ROS. Unit tests import the pure modules
(decision, transform, class_map, decision_log) instead.
"""
import math

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from cv_bridge import CvBridge
from geometry_msgs.msg import Point, PointStamped
from sensor_msgs.msg import CameraInfo, Image

from ic382_interfaces.msg import PorterRequest, TaggingCommand

from ic382_perception.class_map import CLASS_ID_TO_CODE
from ic382_perception.decision import Action, classify, reason
from ic382_perception.decision_log import write_entry
from ic382_perception.detector import get_detector
from ic382_perception.transform import pixel_to_3d


class ObjectClassifierNode(Node):
    def __init__(self):
        super().__init__("object_classifier")

        # Camera topic names and frames still need confirmation in the running
        # scene, so they are all parameterised with defaults per ROS_CONTRACT.md.
        self.declare_parameter("image_topic", "/camera/image_raw")
        self.declare_parameter("depth_topic", "/camera/depth/image_raw")
        self.declare_parameter("camera_info_topic", "/camera/camera_info")
        self.declare_parameter("tagging_cmd_topic", "/tagging_cmd")
        self.declare_parameter("porter_cmd_topic", "/porter_cmd")
        self.declare_parameter("detector_mode", "ultralytics")
        self.declare_parameter("model_path", "")
        self.declare_parameter("conf_threshold", 0.5)
        self.declare_parameter("valid_class_ids", [0, 1, 2])
        self.declare_parameter("camera_frame", "camera_color_optical_frame")
        self.declare_parameter("base_frame", "base_link")
        self.declare_parameter("use_tf", True)
        self.declare_parameter("depth_scale", 0.001)
        self.declare_parameter("table_id", "unknown")
        self.declare_parameter("log_path", "results/decision_log.jsonl")

        self.conf_threshold = float(self.get_parameter("conf_threshold").value)
        self.valid_class_ids = set(self.get_parameter("valid_class_ids").value)
        self.depth_scale = float(self.get_parameter("depth_scale").value)
        self.table_id = str(self.get_parameter("table_id").value)
        self.log_path = str(self.get_parameter("log_path").value)
        self.camera_frame = str(self.get_parameter("camera_frame").value)
        self.base_frame = str(self.get_parameter("base_frame").value)
        self.use_tf = bool(self.get_parameter("use_tf").value)

        self.bridge = CvBridge()
        self.detector = get_detector(
            str(self.get_parameter("detector_mode").value),
            model_path=str(self.get_parameter("model_path").value),
        )

        self.tag_pub = self.create_publisher(
            TaggingCommand, str(self.get_parameter("tagging_cmd_topic").value), 10)
        self.porter_pub = self.create_publisher(
            PorterRequest, str(self.get_parameter("porter_cmd_topic").value), 10)

        qos = qos_profile_sensor_data
        self.create_subscription(
            Image, str(self.get_parameter("image_topic").value), self.on_image, qos)
        self.create_subscription(
            Image, str(self.get_parameter("depth_topic").value), self.on_depth, qos)
        self.create_subscription(
            CameraInfo, str(self.get_parameter("camera_info_topic").value),
            self.on_camera_info, qos)

        self.latest_depth = None
        self.latest_camera_info = None

        self.tf_buffer = None
        self.tf_listener = None
        if self.use_tf:
            try:
                from tf2_ros.buffer import Buffer
                from tf2_ros.transform_listener import TransformListener
                self.tf_buffer = Buffer()
                self.tf_listener = TransformListener(self.tf_buffer, self)
            except Exception as exc:  # pragma: no cover - depends on runtime
                self.get_logger().warn(
                    "TF init failed, publishing in camera frame: %s" % exc)

    def on_depth(self, msg):
        self.latest_depth = msg

    def on_camera_info(self, msg):
        self.latest_camera_info = msg

    def on_image(self, msg):
        if self.latest_depth is None or self.latest_camera_info is None:
            self.get_logger().info("Waiting for depth and camera info")
            return

        try:
            image = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
            depth = self.bridge.imgmsg_to_cv2(self.latest_depth)
        except Exception as exc:
            self.get_logger().error("Failed to decode images: %s" % exc)
            return

        try:
            detections = self.detector.detect(image)
        except Exception as exc:
            self.get_logger().error("Detection failed: %s" % exc)
            return

        for detection in detections:
            self.handle_detection(detection, depth)

    def handle_detection(self, detection, depth):
        if classify(detection, self.conf_threshold, self.valid_class_ids) is Action.TAG:
            self.publish_tag(detection, depth)
        else:
            self.log_only(detection)

    def publish_tag(self, detection, depth):
        camera_info = self.latest_camera_info
        fx, fy, cx, cy = camera_info.k[0], camera_info.k[4], camera_info.k[2], camera_info.k[5]

        d = self.sample_depth(depth, detection.x_center, detection.y_center)
        if d is None:
            self.log_only(detection, reason_override="missing_depth")
            return

        point_cam = pixel_to_3d(detection.x_center, detection.y_center, d, fx, fy, cx, cy)
        if point_cam is None:
            self.log_only(detection, reason_override="invalid_depth")
            return

        point_base = self.to_base_frame(point_cam)
        stamp = self.get_clock().now().to_msg()

        tag = TaggingCommand()
        tag.class_code = CLASS_ID_TO_CODE.get(detection.class_id, "?")
        tag.class_id = detection.class_id
        tag.confidence = detection.confidence
        tag.position = Point(x=point_base[0], y=point_base[1], z=point_base[2])
        tag.stamp = stamp
        self.tag_pub.publish(tag)

        porter = PorterRequest()
        porter.table_id = self.table_id
        porter.position = tag.position
        porter.stamp = stamp
        self.porter_pub.publish(porter)

    def sample_depth(self, depth, u, v):
        height, width = depth.shape[:2]
        if not (0 <= u < width and 0 <= v < height):
            return None
        raw = float(depth[int(round(v)), int(round(u))])
        if not math.isfinite(raw) or raw <= 0:
            return None
        return raw * self.depth_scale

    def to_base_frame(self, point):
        if not self.use_tf or self.tf_buffer is None:
            return point
        try:
            from tf2_geometry_msgs import do_transform_point
            transform = self.tf_buffer.lookup_transform(
                self.base_frame, self.camera_frame, rclpy.time.Time())
            point_stamped = PointStamped()
            point_stamped.header.frame_id = self.camera_frame
            point_stamped.point.x = point[0]
            point_stamped.point.y = point[1]
            point_stamped.point.z = point[2]
            out = do_transform_point(point_stamped, transform)
            return (out.point.x, out.point.y, out.point.z)
        except Exception as exc:
            self.get_logger().warn(
                "TF lookup failed, publishing in camera frame: %s" % exc,
                throttle_duration_sec=10.0)
            return point

    def log_only(self, detection, reason_override=None):
        entry = {
            "action": "log_only",
            "table_id": self.table_id,
            "class_id": detection.class_id,
            "confidence": detection.confidence,
            "bbox": list(detection.bbox),
            "reason": reason_override or reason(
                detection, self.conf_threshold, self.valid_class_ids),
        }
        write_entry(self.log_path, entry)
        self.get_logger().info("Log only, no tag: %s" % entry)


def main():
    rclpy.init()
    node = ObjectClassifierNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
