"""Classification node for one active inspection point.

The safety monitor owns the YOLO engine and publishes raw detections. This node
maps class names to the team's five roles, filters anomalies, projects valid
detections into the base frame, and publishes classified observations. It never
publishes tag or porter commands; the fair-chance manager does that only after
round-two confirmation.
"""
import json
import math
import time
import uuid

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from geometry_msgs.msg import Point, PointStamped
from sensor_msgs.msg import CameraInfo
from std_msgs.msg import String

from ic382_interfaces.msg import (
    AnomalyReport,
    DetectedObjectArray,
    InspectionContext,
    ObjectDetection,
    ObjectDetectionArray,
)

from ic382_perception.class_map import (
    ROLE_OUT_OF_SCOPE,
    class_code_for_role,
    role_for_class_name,
)
from ic382_perception.decision import Action, decide
from ic382_perception.decision_log import write_entry
from ic382_perception.transform import pixel_to_3d, valid_intrinsics


class ObjectClassifierNode(Node):
    def __init__(self):
        super().__init__("object_classifier")

        self.declare_parameter("detections_topic", "/ic382/perception/detections")
        self.declare_parameter("context_topic", "/ic382/perception/context")
        self.declare_parameter("classified_topic", "/ic382/perception/classified")
        self.declare_parameter("anomalies_topic", "/ic382/perception/anomalies")
        self.declare_parameter("status_topic", "/ic382/perception/status")
        self.declare_parameter("camera_info_topic", "/camera/color/camera_info")
        self.declare_parameter("tag_conf_threshold", 0.5)
        self.declare_parameter("tagging_enabled", False)
        self.declare_parameter("roi", [0.0, 0.0, 1.0, 1.0])
        self.declare_parameter("max_fps", 5.0)
        self.declare_parameter("base_frame", "base_link")
        self.declare_parameter("camera_frame", "camera_color_optical_frame")
        self.declare_parameter("use_tf", True)
        self.declare_parameter("tf_timeout", 0.1)
        self.declare_parameter("allow_camera_frame_fallback", False)
        self.declare_parameter("log_path", "")
        self.declare_parameter("save_anomaly_evidence", False)
        self.declare_parameter("evidence_dir", "results/evidence")

        self.tag_conf_threshold = float(
            self.get_parameter("tag_conf_threshold").value)
        self.tagging_enabled = bool(self.get_parameter("tagging_enabled").value)
        self.roi = self._read_roi(self.get_parameter("roi").value)
        self.max_fps = max(0.5, float(self.get_parameter("max_fps").value))
        self.min_period = 1.0 / self.max_fps
        self.last_process = -math.inf
        self.base_frame = str(self.get_parameter("base_frame").value)
        self.camera_frame = str(self.get_parameter("camera_frame").value)
        self.use_tf = bool(self.get_parameter("use_tf").value)
        self.tf_timeout = float(self.get_parameter("tf_timeout").value)
        self.allow_camera_frame_fallback = bool(
            self.get_parameter("allow_camera_frame_fallback").value)
        self.log_path = str(self.get_parameter("log_path").value)
        self.camera_info = None
        self.context = None
        self.context_received_at = -math.inf
        self.sequence = 0
        self.last_status = {}

        self.tf_buffer = None
        self.tf_listener = None
        if self.use_tf:
            try:
                from tf2_ros.buffer import Buffer
                from tf2_ros.transform_listener import TransformListener

                self.tf_buffer = Buffer()
                self.tf_listener = TransformListener(self.tf_buffer, self)
            except Exception as exc:  # pragma: no cover - runtime dependent
                self.get_logger().error("TF unavailable: " + str(exc))

        self.classified_pub = self.create_publisher(
            ObjectDetectionArray,
            str(self.get_parameter("classified_topic").value), 10)
        self.anomaly_pub = self.create_publisher(
            AnomalyReport,
            str(self.get_parameter("anomalies_topic").value), 10)
        self.status_pub = self.create_publisher(
            String, str(self.get_parameter("status_topic").value), 10)

        self.create_subscription(
            DetectedObjectArray,
            str(self.get_parameter("detections_topic").value),
            self.on_detections, 10)
        self.create_subscription(
            InspectionContext,
            str(self.get_parameter("context_topic").value),
            self.on_context, 10)
        self.create_subscription(
            CameraInfo,
            str(self.get_parameter("camera_info_topic").value),
            self.on_camera_info, qos_profile_sensor_data)
        self.create_subscription(
            String, str(self.get_parameter("status_topic").value),
            self.on_status, 10)
        self.create_timer(1.0, self.publish_status)

    @staticmethod
    def _read_roi(value):
        values = list(value)
        if len(values) != 4:
            raise ValueError("roi must be [xmin, ymin, xmax, ymax]")
        x_min, y_min, x_max, y_max = (float(item) for item in values)
        if not (0.0 <= x_min < x_max <= 1.0 and 0.0 <= y_min < y_max <= 1.0):
            raise ValueError("roi values must be inside [0, 1] and ordered")
        return (x_min, y_min, x_max, y_max)

    def on_camera_info(self, msg):
        self.camera_info = msg

    def on_context(self, msg):
        self.context = msg
        self.context_received_at = time.monotonic()
        self.last_process = -math.inf

    def on_status(self, msg):
        try:
            status = json.loads(msg.data)
        except (ValueError, TypeError):
            return
        if status.get("source") != "safety_monitor":
            return
        if "tagging_enabled" in status:
            self.tagging_enabled = bool(status["tagging_enabled"])

    def on_detections(self, msg):
        if self.context is None or not self.context.active:
            return
        now = time.monotonic()
        if now - self.last_process < self.min_period:
            return
        self.last_process = now
        self.process(msg)

    def process(self, msg):
        info = self.camera_info
        if info is None:
            self.publish_status()
            return
        if not valid_intrinsics(float(info.k[0]), float(info.k[4])):
            self.publish_status()
            return

        fx, fy = float(info.k[0]), float(info.k[4])
        cx, cy = float(info.k[2]), float(info.k[5])
        array = ObjectDetectionArray()
        array.header = msg.header
        array.mission_id = self.context.mission_id
        array.task_id = self.context.task_id
        array.desk_id = self.context.desk_id
        array.point_id = self.context.point_id
        array.round = self.context.round

        for item in msg.objects:
            role = role_for_class_name(item.class_name)
            in_roi = self._in_roi(item, msg.image_width, msg.image_height)
            position = None
            position_valid = False
            projection_reason = "missing_depth"

            if in_roi and role != ROLE_OUT_OF_SCOPE:
                position, projection_reason = self._project(
                    item, msg.header, fx, fy, cx, cy)
                position_valid = position is not None
            elif not in_roi:
                projection_reason = "out_of_roi"

            action, reason = decide(
                role,
                float(item.confidence),
                tagging_enabled=self.tagging_enabled,
                position_valid=position_valid or role not in ("A", "B", "C"),
                confirmed=True,
                conf_threshold=self.tag_conf_threshold,
                projection_reason=projection_reason,
            )

            if action is Action.ANOMALY:
                self.publish_anomaly(msg, item, reason)
                continue
            if not in_roi:
                self.publish_anomaly(msg, item, "out_of_roi")
                continue

            detection = self.build_detection(
                msg, item, role, position, position_valid, projection_reason)
            array.detections.append(detection)

            if (role in ("A", "B", "C") and not position_valid
                    and not self.allow_camera_frame_fallback):
                self.publish_anomaly(msg, item, projection_reason)

        self.classified_pub.publish(array)
        self.publish_status(detections=len(array.detections))

    def _in_roi(self, item, image_width, image_height):
        if image_width <= 0 or image_height <= 0:
            return True
        x = float(item.center_x) / float(image_width)
        y = float(item.center_y) / float(image_height)
        x_min, y_min, x_max, y_max = self.roi
        return x_min <= x <= x_max and y_min <= y <= y_max

    def _project(self, item, header, fx, fy, cx, cy):
        if not item.distance_valid or not math.isfinite(float(item.distance_m)):
            return None, "missing_depth"
        point_cam = pixel_to_3d(
            float(item.center_x), float(item.center_y),
            float(item.distance_m), fx, fy, cx, cy)
        if point_cam is None:
            return None, "invalid_depth"
        return self.to_base_frame(point_cam, header)

    def to_base_frame(self, point, header):
        if not self.use_tf or self.tf_buffer is None:
            if self.allow_camera_frame_fallback:
                return point, "camera_frame_fallback"
            return None, "tf_unavailable"
        try:
            from rclpy.duration import Duration
            from rclpy.time import Time
            from tf2_geometry_msgs import do_transform_point

            stamp = Time.from_msg(header.stamp)
            frame = header.frame_id or self.camera_frame
            transform = self.tf_buffer.lookup_transform(
                self.base_frame, frame, stamp,
                timeout=Duration(seconds=self.tf_timeout))
            point_stamped = PointStamped()
            point_stamped.header.frame_id = frame
            point_stamped.header.stamp = header.stamp
            point_stamped.point.x, point_stamped.point.y, point_stamped.point.z = point
            out = do_transform_point(point_stamped, transform)
            return (out.point.x, out.point.y, out.point.z), "ok"
        except Exception as exc:  # noqa: BLE001 - report, never guess a frame
            self.get_logger().warn(
                "TF lookup failed: " + str(exc), throttle_duration_sec=10.0)
            if self.allow_camera_frame_fallback:
                return point, "camera_frame_fallback"
            return None, "tf_unavailable"

    def build_detection(self, msg, item, role, position, position_valid,
                        projection_reason):
        self.sequence += 1
        detection = ObjectDetection()
        detection.header = msg.header
        detection.detection_id = uuid.uuid4().hex[:12]
        detection.mission_id = self.context.mission_id
        detection.task_id = self.context.task_id
        detection.desk_id = self.context.desk_id
        detection.point_id = self.context.point_id
        detection.round = self.context.round
        detection.class_name = item.class_name
        detection.class_id = int(item.class_id)
        detection.role = role
        detection.class_code = class_code_for_role(role) or ""
        detection.confidence = float(item.confidence)
        detection.center_x = float(item.center_x)
        detection.center_y = float(item.center_y)
        detection.width = float(item.width)
        detection.height = float(item.height)
        detection.position_valid = bool(position_valid)
        if position is not None:
            detection.position_base = Point(
                x=float(position[0]), y=float(position[1]), z=float(position[2]))
            detection.position_frame = self.base_frame
        else:
            detection.position_base = Point()
            detection.position_frame = ""
        detection.projection_reason = projection_reason
        return detection

    def publish_anomaly(self, msg, item, reason):
        anomaly = AnomalyReport()
        anomaly.header = msg.header
        anomaly.detection_id = uuid.uuid4().hex[:12]
        anomaly.mission_id = self.context.mission_id
        anomaly.task_id = self.context.task_id
        anomaly.desk_id = self.context.desk_id
        anomaly.point_id = self.context.point_id
        anomaly.round = self.context.round
        anomaly.class_name = item.class_name
        anomaly.class_id = int(item.class_id)
        anomaly.confidence = float(item.confidence)
        anomaly.center_x = float(item.center_x)
        anomaly.center_y = float(item.center_y)
        anomaly.width = float(item.width)
        anomaly.height = float(item.height)
        anomaly.reason = reason
        self.anomaly_pub.publish(anomaly)
        if self.log_path:
            write_entry(self.log_path, {
                "action": "anomaly",
                "mission_id": self.context.mission_id,
                "task_id": self.context.task_id,
                "desk_id": self.context.desk_id,
                "point_id": self.context.point_id,
                "round": int(self.context.round),
                "class_name": anomaly.class_name,
                "class_id": anomaly.class_id,
                "confidence": anomaly.confidence,
                "bbox": [anomaly.center_x, anomaly.center_y,
                         anomaly.width, anomaly.height],
                "reason": reason,
            })

    def publish_status(self, detections=None):
        status = {
            "source": self.get_name(),
            "tagging_enabled": self.tagging_enabled,
            "context_active": bool(self.context and self.context.active),
            "mission_id": self.context.mission_id if self.context else "",
            "task_id": self.context.task_id if self.context else "",
            "desk_id": self.context.desk_id if self.context else "",
            "point_id": self.context.point_id if self.context else "",
            "round": int(self.context.round) if self.context else 0,
            "detections": detections,
        }
        self.last_status = status
        self.status_pub.publish(
            String(data=json.dumps(status, allow_nan=False)))


def main(args=None):
    rclpy.init(args=args)
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
