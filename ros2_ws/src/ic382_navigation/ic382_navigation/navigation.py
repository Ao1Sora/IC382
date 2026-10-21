"""Bounded asynchronous client for the upstream Humble NavigateToPose action."""
import math
import time
from action_msgs.msg import GoalStatus
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient


class Navigator:
    def __init__(self, node, health, emit, timeout):
        self.node, self.health, self.emit, self.timeout = node, health, emit, timeout
        self.client = ActionClient(node, NavigateToPose, 'navigate_to_pose')
        self.handle = None
        self.result = None
        self.pending = False
        self.cancel_reason = ''
        self.started = 0.0
        self.last_feedback = 0.0

    def ready(self):
        return self.client.server_is_ready() and not self.health()

    @property
    def motion_allowed(self):
        return self.pending and self.handle is not None and not self.cancel_reason and not self.health()

    def start(self, point, now):
        if self.pending:
            raise RuntimeError('Previous navigation has not reached a terminal result')
        self.result, self.handle, self.cancel_reason = None, None, ''
        self.started, self.pending = now, True
        if not self.ready():
            self.pending, self.result = False, 'navigation_not_ready:' + self.health()
            return
        goal = NavigateToPose.Goal()
        goal.pose.header.frame_id = 'map'
        goal.pose.header.stamp = self.node.get_clock().now().to_msg()
        goal.pose.pose.position.x = float(point['x'])
        goal.pose.pose.position.y = float(point['y'])
        goal.pose.pose.orientation.z = math.sin(point['yaw'] / 2)
        goal.pose.pose.orientation.w = math.cos(point['yaw'] / 2)
        self.client.send_goal_async(goal, feedback_callback=self._feedback).add_done_callback(self._accepted)

    def _accepted(self, future):
        try:
            self.handle = future.result()
            if not self.handle.accepted:
                self.pending, self.result = False, 'goal_rejected'
                return
            self.handle.get_result_async().add_done_callback(self._finished)
            if self.cancel_reason:
                self.handle.cancel_goal_async()
        except Exception as exc:
            self.pending, self.result = False, 'goal_transport_error:' + str(exc)

    def _finished(self, future):
        self.pending = False
        try:
            status = future.result().status
            self.result = self.cancel_reason or {
                GoalStatus.STATUS_SUCCEEDED: 'SUCCEEDED',
                GoalStatus.STATUS_CANCELED: 'CANCELED',
                GoalStatus.STATUS_ABORTED: 'navigation_aborted',
            }.get(status, 'unexpected_action_status:' + str(status))
        except Exception as exc:
            self.result = 'result_transport_error:' + str(exc)

    def _feedback(self, message):
        if time.monotonic() - self.last_feedback >= 1.0:
            self.last_feedback = time.monotonic()
            f = message.feedback
            self.emit('navigation_feedback', {'distance_remaining': f.distance_remaining,
                                             'recoveries': f.number_of_recoveries})

    def cancel(self, reason):
        self.cancel_reason = reason
        if self.handle and self.handle.accepted and self.pending:
            self.handle.cancel_goal_async()

    def poll(self, now):
        if self.pending and not self.cancel_reason:
            reason = self.health()
            if reason or now - self.started > self.timeout:
                self.cancel(reason or 'navigation_wall_timeout')
                self.emit('navigation_cancel_requested', {'reason': self.cancel_reason})
        # Stop the mission even if a failed server never acknowledges cancellation.
        # The independent velocity gate is already closed. No new goal is accepted.
        if self.cancel_reason:
            return self.cancel_reason
        return self.result
