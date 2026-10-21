from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from rclpy.clock import Clock
from rclpy.task import Future
import ic382_navigation.navigation as implementation


class Client:
    def __init__(self, *args):
        self.response = Future()
        self.online = True

    def server_is_ready(self):
        return self.online

    def send_goal_async(self, goal, feedback_callback):
        self.goal = goal
        return self.response


def make(monkeypatch, health=lambda: ''):
    monkeypatch.setattr(implementation, 'ActionClient', Client)
    node = SimpleNamespace(get_clock=lambda: Clock())
    return implementation.Navigator(node, health, lambda *a: None, 10.)


def accepted(nav):
    handle = SimpleNamespace(accepted=True, cancel_goal_async=Mock(), get_result_async=lambda: result)
    result = Future()
    nav.client.response.set_result(handle)
    return handle, result


def test_cancel_before_acceptance_cancels_late_goal(monkeypatch):
    nav = make(monkeypatch)
    nav.start(dict(x=1., y=2., yaw=0.), 0.)
    nav.cancel('operator_cancelled')
    handle, result = accepted(nav)
    handle.cancel_goal_async.assert_called_once()
    assert not nav.motion_allowed
    result.set_result(SimpleNamespace(status=5))
    assert nav.poll(1.) == 'operator_cancelled'


def test_failed_or_canceled_action_never_counts_as_success(monkeypatch):
    for status, expected in [(4, 'SUCCEEDED'), (5, 'CANCELED'), (6, 'navigation_aborted')]:
        nav = make(monkeypatch)
        nav.start(dict(x=1., y=2., yaw=0.), 0.)
        handle, result = accepted(nav)
        result.set_result(SimpleNamespace(status=status))
        assert nav.poll(1.) == expected


def test_wall_timeout_closes_motion_even_without_cancel_ack(monkeypatch):
    nav = make(monkeypatch)
    nav.start(dict(x=1., y=2., yaw=0.), 0.)
    handle, _ = accepted(nav)
    assert nav.motion_allowed
    assert nav.poll(11.) == 'navigation_wall_timeout'
    assert not nav.motion_allowed
    handle.cancel_goal_async.assert_called_once()
    with pytest.raises(RuntimeError):
        nav.start(dict(x=1., y=2., yaw=0.), 12.)
