"""Two-round fair-chance manager and mission orchestrator.

It is the only node that publishes tag, target-pose and porter messages, and the
only perception node that talks to the desk-navigation action/service.
"""
import json
import math
import threading
import time
import uuid

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from geometry_msgs.msg import Point, PointStamped, Pose, PoseStamped, Quaternion
from std_msgs.msg import String

from ic382_interfaces.action import InspectDesk
from ic382_interfaces.msg import (
    AnomalyReport,
    InspectionContext,
    ObjectDetectionArray,
    PorterRequest,
    SafetyState,
    TaggingCommand,
)
from ic382_interfaces.srv import CompleteInspection

from ic382_perception.class_map import CLASS_ID_TO_CODE, role_for_class_name
from ic382_perception.decision_log import SpecDecisionLog
from ic382_perception.eligibility import (
    STATUS_ELIGIBLE,
    STATUS_INELIGIBLE,
    STATUS_UNKNOWN,
    evaluate,
)
from ic382_perception.fair_chance import (
    ACTION_OCCUPIED,
    ACTION_UNKNOWN,
    STATUS_CONFIRMED,
    STATUS_OCCUPIED,
    DetectionRecord,
    associate,
    center_distance_ratio,
    iou_xywh,
    merge_across_views,
    validate_round2,
)

ROUND_ONE = 1
ROUND_TWO = 2


class FairChanceManagerNode(Node):
    def __init__(self):
        super().__init__("fair_chance_manager")

        self.declare_parameter("desks", [])
        self.declare_parameter("auto_start", True)
        self.declare_parameter("mission_id", "")
        self.declare_parameter("round2_delay_seconds", 60.0)
        self.declare_parameter("observation_window_seconds", 8.0)
        self.declare_parameter("min_frames", 5)
        self.declare_parameter("action_timeout_seconds", 900.0)
        self.declare_parameter("work_timeout_seconds", 120.0)
        self.declare_parameter("perception_required", False)
        self.declare_parameter("tagging_enabled", False)
        self.declare_parameter("tag_settle_seconds", 0.0)
        self.declare_parameter("spec_log_path", "/home/student/dev/decision_log.json")
        self.declare_parameter("jsonl_path", "")
        self.declare_parameter("porter_topic", "/porter_cmd")
        self.declare_parameter("tagging_topic", "/tagging_cmd")
        self.declare_parameter("target_pose_topic", "/target_tag_pose")
        self.declare_parameter("context_topic", "/ic382/perception/context")
        self.declare_parameter("classified_topic", "/ic382/perception/classified")
        self.declare_parameter("anomalies_topic", "/ic382/perception/anomalies")
        self.declare_parameter("safety_state_topic", "/ic382/safety_state")
        self.declare_parameter("status_topic", "/ic382/perception/status")
        self.declare_parameter("person_desk_limit_m", 1.5)
        self.declare_parameter("reserved_card_conf", 0.5)
        self.declare_parameter("safety_timeout", 2.0)
        self.declare_parameter("base_frame", "base_link")
        self.declare_parameter("map_frame", "map")
        self.declare_parameter("use_tf", True)
        self.declare_parameter("tf_timeout", 0.1)

        self.desks = [str(value) for value in self.get_parameter("desks").value]
        self.mission_id = str(self.get_parameter("mission_id").value) or uuid.uuid4().hex
        self.round2_delay = float(
            self.get_parameter("round2_delay_seconds").value)
        self.observation_window = float(
            self.get_parameter("observation_window_seconds").value)
        self.min_frames = max(1, int(self.get_parameter("min_frames").value))
        self.action_timeout = float(
            self.get_parameter("action_timeout_seconds").value)
        self.work_timeout = float(
            self.get_parameter("work_timeout_seconds").value)
        self.perception_required = bool(
            self.get_parameter("perception_required").value)
        self.tagging_enabled = bool(
            self.get_parameter("tagging_enabled").value)
        self.tag_settle = float(self.get_parameter("tag_settle_seconds").value)
        self.spec_log_path = str(self.get_parameter("spec_log_path").value)
        self.jsonl_path = str(self.get_parameter("jsonl_path").value)
        self.person_desk_limit = float(
            self.get_parameter("person_desk_limit_m").value)
        self.reserved_card_conf = float(
            self.get_parameter("reserved_card_conf").value)
        self.safety_timeout = float(self.get_parameter("safety_timeout").value)
        self.base_frame = str(self.get_parameter("base_frame").value)
        self.map_frame = str(self.get_parameter("map_frame").value)
        self.use_tf = bool(self.get_parameter("use_tf").value)
        self.tf_timeout = float(self.get_parameter("tf_timeout").value)

        self._lock = threading.Lock()
        self._classified_frames = []
        self._anomalies = []
        self._feedback = None
        self._feedback_event = threading.Event()
        self._feedback_lock = threading.Lock()
        self._safety_state = None
        self._safety_at = -math.inf
        self._shutdown = threading.Event()
        self._thread = None

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

        self.action_client = ActionClient(
            self, InspectDesk, "/ic382/inspect_desk")
        self.complete_client = self.create_client(
            CompleteInspection, "/ic382/complete_inspection")

        self.context_pub = self.create_publisher(
            InspectionContext, str(self.get_parameter("context_topic").value), 10)
        self.tag_pub = self.create_publisher(
            TaggingCommand, str(self.get_parameter("tagging_topic").value), 10)
        self.pose_pub = self.create_publisher(
            PoseStamped, str(self.get_parameter("target_pose_topic").value), 10)
        self.porter_pub = self.create_publisher(
            PorterRequest, str(self.get_parameter("porter_topic").value), 10)

        self.create_subscription(
            ObjectDetectionArray,
            str(self.get_parameter("classified_topic").value),
            self.on_classified, 10)
        self.create_subscription(
            AnomalyReport,
            str(self.get_parameter("anomalies_topic").value),
            self.on_anomaly, 10)
        self.create_subscription(
            SafetyState,
            str(self.get_parameter("safety_state_topic").value),
            self.on_safety, 10)
        self.create_subscription(
            String, str(self.get_parameter("status_topic").value),
            self.on_status, 10)

        if self.desks and bool(self.get_parameter("auto_start").value):
            self._thread = threading.Thread(target=self.run_mission, daemon=True)
            self._thread.start()
        elif not self.desks:
            self.get_logger().warn("No desks configured; fair-chance manager idle")

    # ---------------------------------------------------------------- callbacks
    def on_classified(self, msg):
        with self._lock:
            self._classified_frames.append(msg)

    def on_anomaly(self, msg):
        with self._lock:
            self._anomalies.append(msg)

    def on_safety(self, msg):
        self._safety_state = msg
        self._safety_at = time.monotonic()

    def on_status(self, msg):
        try:
            status = json.loads(msg.data)
        except (ValueError, TypeError):
            return
        if status.get("source") == "safety_monitor" and "tagging_enabled" in status:
            self.tagging_enabled = bool(status["tagging_enabled"])

    def _on_feedback(self, msg):
        with self._feedback_lock:
            self._feedback = msg.feedback
        self._feedback_event.set()

    # ---------------------------------------------------------------- mission
    def run_mission(self):
        try:
            decision_log = SpecDecisionLog(self.spec_log_path)
        except Exception as exc:  # noqa: BLE001
            self.get_logger().error("Cannot create decision log: " + str(exc))
            decision_log = None

        if not self.action_client.wait_for_server(timeout_sec=90.0):
            self.get_logger().error("InspectDesk action server unavailable")
            return
        if not self.complete_client.wait_for_service(timeout_sec=10.0):
            self.get_logger().error("CompleteInspection service unavailable")
            return

        states = {desk: self._new_state() for desk in self.desks}
        round1_started = time.monotonic()
        for desk in self.desks:
            if self._shutdown.is_set():
                return
            state = states[desk]
            if decision_log:
                decision_log.begin_desk(desk)
            self.get_logger().info("Round 1 inspecting " + desk)
            self._inspect_desk(desk, ROUND_ONE, state, decision_log)
            self._record_round1(desk, state, decision_log)

        elapsed = time.monotonic() - round1_started
        if elapsed < self.round2_delay:
            self.get_logger().info(
                "Waiting %.1f s before round 2" % (self.round2_delay - elapsed))
            self._sleep(self.round2_delay - elapsed)

        for desk in self.desks:
            if self._shutdown.is_set():
                return
            state = states[desk]
            if state["status"] != STATUS_ELIGIBLE or not state["items"]:
                self._finalize_no_round2(desk, state, decision_log)
                continue
            self.get_logger().info("Round 2 inspecting " + desk)
            self._inspect_desk(desk, ROUND_TWO, state, decision_log)
            self._finalize_round2(desk, state, decision_log)

        self._publish_porter(states)
        if decision_log:
            decision_log.finish()
        self.get_logger().info("Fair-chance mission complete")

    @staticmethod
    def _new_state():
        return {
            "items": [],
            "next_id": 1,
            "status": "PENDING",
            "anomalies": {},
            "matches": {},
            "validation": {},
            "tagged": set(),
            "new_records": [],
            "occupied": False,
        }

    def _inspect_desk(self, desk_id, round_number, state, decision_log):
        with self._feedback_lock:
            self._feedback = None
        self._feedback_event.clear()
        goal = InspectDesk.Goal()
        goal.desk_id = desk_id
        send_future = self.action_client.send_goal_async(
            goal, feedback_callback=self._on_feedback)
        goal_handle = self._await(send_future, 10.0)
        if goal_handle is None or not goal_handle.accepted:
            self.get_logger().error("Goal rejected for " + desk_id)
            return
        result_future = goal_handle.get_result_async()
        handled = set()
        deadline = time.monotonic() + self.action_timeout
        while not self._shutdown.is_set() and time.monotonic() < deadline:
            if result_future.done():
                break
            feedback = self._wait_feedback(result_future, handled, deadline)
            if feedback is None:
                if result_future.done():
                    break
                continue
            handled.add(feedback.point_id)
            self._handle_point(
                feedback.task_id, desk_id, feedback.point_id,
                round_number, state, decision_log)
        if not result_future.done():
            self.get_logger().error("Desk inspection timed out: " + desk_id)
            try:
                goal_handle.cancel_goal_async()
            except Exception:  # noqa: BLE001
                pass
            return
        response = result_future.result()
        result = getattr(response, "result", None)
        if result is not None and not result.success:
            self.get_logger().error(
                "Desk inspection failed for %s: %s" % (desk_id, result.message))

    def _wait_feedback(self, result_future, handled, deadline):
        while time.monotonic() < deadline and not self._shutdown.is_set():
            self._feedback_event.wait(0.1)
            self._feedback_event.clear()
            with self._feedback_lock:
                feedback = self._feedback
            if (feedback is not None
                    and feedback.state == "WAITING_FOR_WORK"
                    and feedback.point_id
                    and feedback.point_id not in handled):
                return feedback
            if result_future.done():
                return None
        return None

    def _handle_point(self, task_id, desk_id, point_id, round_number, state,
                      decision_log):
        state["task_id"] = task_id
        with self._lock:
            self._classified_frames = []
            self._anomalies = []
        self._publish_context(
            task_id, desk_id, point_id, round_number, active=True)
        self._sleep(self.observation_window)
        self._publish_context(
            task_id, desk_id, point_id, round_number, active=False)

        with self._lock:
            frames = list(self._classified_frames)
            anomalies = list(self._anomalies)

        records, reserved_confidence = self._records_from_frames(frames)
        nearest_person = self._nearest_person()
        data_fresh = self._safety_fresh()
        eligibility = evaluate(
            nearest_person, reserved_confidence,
            person_limit_m=self.person_desk_limit,
            reserved_min=self.reserved_card_conf,
            data_fresh=data_fresh)
        state["status"] = self._merge_status(state["status"], eligibility.status)
        if eligibility.status == STATUS_INELIGIBLE:
            state["occupied"] = True
            if round_number == ROUND_TWO:
                self.get_logger().warn(
                    "Desk %s became ineligible during round 2" % desk_id)

        self._record_anomalies(desk_id, anomalies, state, decision_log)

        if round_number == ROUND_ONE:
            state["items"], state["next_id"] = merge_across_views(
                state["items"], records, state["next_id"])
        else:
            self._process_round2_point(
                task_id, desk_id, point_id, state, records, decision_log)

        if self.perception_required and len(frames) < self.min_frames:
            self.get_logger().error(
                "Insufficient perception output for %s/%s (%d frames)"
                % (desk_id, point_id, len(frames)))
            success = False
        else:
            success = True
        self._complete(task_id, point_id, success)

    def _process_round2_point(self, task_id, desk_id, point_id, state,
                              records, decision_log):
        records = self._dedupe(records)
        unmatched = [
            item for item in state["items"]
            if item.item_id not in state["matches"]
        ]
        matches = associate(unmatched, records)
        used = {id(record) for record in matches.values()}
        for item_id, record in matches.items():
            state["matches"][item_id] = record
        for record in records:
            if id(record) not in used:
                state["new_records"].append(record)

    def _finalize_round2(self, desk_id, state, decision_log):
        results = validate_round2(
            state["items"], state["matches"],
            occupied=state["occupied"], tagging_enabled=self.tagging_enabled)
        for result in results:
            action_taken = result.action_taken
            if result.status == STATUS_CONFIRMED:
                record = state["matches"].get(result.item_id)
                if (self._can_tag(state) and record is not None
                        and record.base_position_m is not None):
                    self._publish_tag(
                        desk_id, record, result.item, state.get("task_id", ""))
                    state["tagged"].add(result.item_id)
                else:
                    action_taken = ACTION_UNKNOWN
            state["validation"][result.item_id] = (result.status, action_taken)
            if decision_log:
                decision_log.record_round2(
                    desk_id, result.item_id, result.status, action_taken)

        for record in state["new_records"]:
            if decision_log:
                decision_log.record_anomaly(
                    desk_id, record.class_name, record.confidence,
                    "new_in_round_2")
        if decision_log:
            decision_log.update_desk_status(desk_id, state["status"])

    def _finalize_no_round2(self, desk_id, state, decision_log):
        status = state["status"] if state["status"] != "PENDING" else STATUS_UNKNOWN
        if decision_log:
            decision_log.update_desk_status(desk_id, status)
            if status == STATUS_INELIGIBLE:
                for item in state["items"]:
                    decision_log.record_round2(
                        desk_id, item.item_id, STATUS_OCCUPIED, ACTION_OCCUPIED)

    def _record_round1(self, desk_id, state, decision_log):
        status = state["status"] if state["status"] != "PENDING" else STATUS_UNKNOWN
        state["status"] = status
        if decision_log:
            decision_log.update_desk_status(desk_id, status)
            for item in state["items"]:
                decision_log.record_round1(
                    desk_id, item.item_id, item.class_code, item.confidence)

    def _record_anomalies(self, desk_id, anomalies, state, decision_log):
        for anomaly in anomalies:
            if anomaly.detection_id in state["anomalies"]:
                continue
            state["anomalies"][anomaly.detection_id] = anomaly
            if decision_log:
                decision_log.record_anomaly(
                    desk_id, anomaly.class_name, anomaly.confidence,
                    anomaly.reason)

    # -------------------------------------------------------------- conversion
    def _records_from_frames(self, frames):
        records = []
        reserved_confidence = 0.0
        for frame in frames:
            for detection in frame.detections:
                role = detection.role or role_for_class_name(detection.class_name)
                if role == "RESERVED_CARD":
                    reserved_confidence = max(
                        reserved_confidence, float(detection.confidence))
                if detection.class_code not in ("A", "B", "C"):
                    continue
                base_position = None
                map_position = None
                if detection.position_valid:
                    base_position = (
                        float(detection.position_base.x),
                        float(detection.position_base.y),
                        float(detection.position_base.z))
                    map_position = self._to_map(
                        base_position,
                        detection.position_frame or self.base_frame,
                        frame.header)
                records.append(DetectionRecord(
                    class_code=detection.class_code,
                    class_name=detection.class_name,
                    confidence=float(detection.confidence),
                    bbox=(float(detection.center_x), float(detection.center_y),
                          float(detection.width), float(detection.height)),
                    position_m=map_position,
                    base_position_m=base_position,
                    point_id=detection.point_id,
                ))
        return records, reserved_confidence

    def _dedupe(self, records):
        kept = []
        for record in records:
            duplicate = False
            for index, existing in enumerate(kept):
                if existing.class_code != record.class_code:
                    continue
                if (iou_xywh(existing.bbox, record.bbox) >= 0.3
                        or center_distance_ratio(existing.bbox, record.bbox) <= 0.3):
                    if record.confidence > existing.confidence:
                        kept[index] = record
                    duplicate = True
                    break
            if not duplicate:
                kept.append(record)
        return kept

    def _map_to_base(self, position):
        if not self.use_tf or self.tf_buffer is None:
            return None
        try:
            from rclpy.duration import Duration
            from rclpy.time import Time
            from tf2_geometry_msgs import do_transform_point

            transform = self.tf_buffer.lookup_transform(
                self.base_frame, self.map_frame, Time(),
                timeout=Duration(seconds=self.tf_timeout))
            point = PointStamped()
            point.header.stamp = self.get_clock().now().to_msg()
            point.header.frame_id = self.map_frame
            point.point = Point(
                x=float(position[0]), y=float(position[1]), z=float(position[2]))
            out = do_transform_point(point, transform)
            return (out.point.x, out.point.y, out.point.z)
        except Exception:  # noqa: BLE001 - fall back to the capture-time base point
            return None

    def _to_map(self, position, frame, header):
        if not self.use_tf or self.tf_buffer is None or not frame:
            return None
        try:
            from rclpy.duration import Duration
            from rclpy.time import Time
            from tf2_geometry_msgs import do_transform_point

            stamp = Time.from_msg(header.stamp)
            transform = self.tf_buffer.lookup_transform(
                self.map_frame, frame, stamp,
                timeout=Duration(seconds=self.tf_timeout))
            point = PointStamped()
            point.header.stamp = header.stamp
            point.header.frame_id = frame
            point.point = Point(
                x=float(position[0]), y=float(position[1]), z=float(position[2]))
            out = do_transform_point(point, transform)
            return (out.point.x, out.point.y, out.point.z)
        except Exception:  # noqa: BLE001 - association falls back to bbox
            return None

    # ------------------------------------------------------------------ output
    def _can_tag(self, state):
        return (
            self.tagging_enabled
            and state["status"] == STATUS_ELIGIBLE
            and not self._safety_stopped()
        )

    def _publish_tag(self, desk_id, record, item, task_id=""):
        stamp = self.get_clock().now().to_msg()
        # Prefer the map-frame position transformed into the current base frame;
        # the robot is stopped at the last inspection pose when this runs.
        position = None
        if record.position_m is not None:
            position = self._map_to_base(record.position_m)
        if position is None:
            position = record.base_position_m
        if position is None:
            return
        tag = TaggingCommand()
        tag.item_id = str(item.item_id)
        tag.mission_id = self.mission_id
        tag.task_id = task_id
        tag.desk_id = desk_id
        tag.point_id = record.point_id
        tag.class_code = item.class_code
        tag.class_id = _class_id_for_code(item.class_code)
        tag.class_name = item.class_name
        tag.confidence = float(record.confidence)
        tag.position = Point(
            x=float(position[0]), y=float(position[1]), z=float(position[2]))
        tag.frame_id = self.base_frame
        tag.stamp = stamp
        self.tag_pub.publish(tag)

        pose = PoseStamped()
        pose.header.stamp = stamp
        pose.header.frame_id = self.base_frame
        pose.pose = Pose(
            position=Point(
                x=float(position[0]), y=float(position[1]), z=float(position[2])),
            orientation=Quaternion(x=0.0, y=0.0, z=0.0, w=1.0))
        self.pose_pub.publish(pose)
        self.get_logger().info(
            "Tag %s/%s class %s" % (desk_id, item.item_id, item.class_code))
        if self.tag_settle > 0:
            self._sleep(self.tag_settle)

    def _publish_porter(self, states):
        desk_ids = []
        item_ids = []
        for desk, state in states.items():
            for item in state["items"]:
                if item.item_id not in state["tagged"]:
                    continue
                if item.class_code != "C":
                    continue
                if desk not in desk_ids:
                    desk_ids.append(desk)
                item_ids.append("%s-%d" % (desk, item.item_id))
        if not desk_ids:
            return
        request = PorterRequest()
        request.mission_id = self.mission_id
        request.desk_ids = desk_ids
        request.item_ids = item_ids
        request.stamp = self.get_clock().now().to_msg()
        self.porter_pub.publish(request)
        self.get_logger().info(
            "Porter requested for desks: " + ", ".join(desk_ids))

    def _publish_context(self, task_id, desk_id, point_id, round_number, active):
        context = InspectionContext()
        context.header.stamp = self.get_clock().now().to_msg()
        context.header.frame_id = self.map_frame
        context.mission_id = self.mission_id
        context.task_id = task_id
        context.desk_id = desk_id
        context.point_id = point_id
        context.round = int(round_number)
        context.active = bool(active)
        context.tagging_allowed = bool(self.tagging_enabled)
        self.context_pub.publish(context)

    def _complete(self, task_id, point_id, success):
        if not self.complete_client.service_is_ready():
            self.get_logger().error("CompleteInspection service not ready")
            return
        request = CompleteInspection.Request()
        request.task_id = task_id
        request.point_id = point_id
        request.success = bool(success)
        response = self._await(self.complete_client.call_async(request), 10.0)
        if response is None or not response.accepted:
            self.get_logger().error(
                "Completion rejected for %s/%s" % (task_id, point_id))

    # ------------------------------------------------------------------ helpers
    def _nearest_person(self):
        state = self._safety_state
        if state is None:
            return None
        if not state.person_visible:
            return None
        distance = float(state.nearest_person_m)
        return distance if math.isfinite(distance) else math.nan

    def _safety_fresh(self):
        if not self.perception_required:
            return True
        return self._safety_state is not None and (
            time.monotonic() - self._safety_at <= self.safety_timeout)

    def _safety_stopped(self):
        return bool(self._safety_state and self._safety_state.stop)

    @staticmethod
    def _merge_status(current, new):
        if current == STATUS_INELIGIBLE or new == STATUS_INELIGIBLE:
            return STATUS_INELIGIBLE
        if current == STATUS_UNKNOWN or new == STATUS_UNKNOWN:
            return STATUS_UNKNOWN
        if current == "PENDING":
            return new
        return current

    @staticmethod
    def _await(future, timeout):
        deadline = time.monotonic() + timeout
        while not future.done() and time.monotonic() < deadline:
            time.sleep(0.05)
        if not future.done():
            return None
        try:
            return future.result()
        except Exception:  # noqa: BLE001
            return None

    def _sleep(self, seconds):
        self._shutdown.wait(max(0.0, float(seconds)))

    def destroy_node(self):
        self._shutdown.set()
        return super().destroy_node()


def _class_id_for_code(class_code):
    for class_id, code in CLASS_ID_TO_CODE.items():
        if code == class_code:
            return class_id
    return -1


def main(args=None):
    rclpy.init(args=args)
    node = FairChanceManagerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
