from copy import deepcopy
import math
import pytest
from ic382_navigation.core import MissionEngine, MotionGuard, validate_route


def route():
    return dict(schema_version=1, frame_id='map', calibrated=True, rounds=2,
                inspection_seconds=3., tagging_seconds=3.,
                waypoints=[dict(id='A', x=0., y=1., yaw=0.), dict(id='B', x=2., y=1., yaw=1.)])


class Navigation:
    def __init__(self):
        self.goals = []
        self.result = None
        self.canceled = False

    def start(self, point, now):
        self.goals.append(point['id'])
        self.result = None

    def poll(self, now):
        return self.result

    def cancel(self, reason):
        self.canceled = True


def test_two_rounds_pause_and_tag_only_in_last_round():
    nav, events = Navigation(), []
    engine = MissionEngine(route(), nav, lambda e, d: events.append((e, d)))
    assert engine.start(0.)
    now = 0.
    for index in range(4):
        nav.result = 'SUCCEEDED'
        engine.tick(now)
        assert engine.state == 'INSPECTING'
        engine.tick(now + 2.99)
        assert engine.state == 'INSPECTING'
        engine.tick(now + 3.)
        if index >= 2:
            assert engine.state == 'TAGGING'
            engine.tick(now + 5.99)
            assert engine.state == 'TAGGING'
            engine.tick(now + 6.)
        now += 10.
    assert engine.state == 'COMPLETED'
    assert nav.goals == ['A', 'B', 'A', 'B']
    tags = [d for e, d in events if e == 'tagging_stub_completed']
    assert len(tags) == 2
    assert all(d['simulated'] and not d['actuator_command_sent'] for d in tags)


@pytest.mark.parametrize('result', ['goal_rejected', 'navigation_aborted', 'scan_stale'])
def test_failure_never_runs_inspection_or_next_goal(result):
    nav, events = Navigation(), []
    engine = MissionEngine(route(), nav, lambda e, d: events.append(e))
    engine.start(0.)
    nav.result = result
    engine.tick(1.)
    engine.tick(100.)
    assert engine.state == 'FAILED'
    assert nav.goals == ['A'] and nav.canceled
    assert 'inspection_stub_started' not in events


def test_cancel_during_dwell_never_tags_or_moves_on():
    nav = Navigation()
    engine = MissionEngine(route(), nav, lambda *a: None)
    engine.start(0.)
    nav.result = 'SUCCEEDED'
    engine.tick(1.)
    assert engine.cancel()
    engine.tick(100.)
    assert engine.state == 'CANCELED' and nav.goals == ['A']


@pytest.mark.parametrize('field,value', [('calibrated', False), ('frame_id', 'odom'),
                                        ('rounds', 0), ('rounds', True)])
def test_invalid_route_rejected(field, value):
    r = route()
    r[field] = value
    with pytest.raises(ValueError):
        validate_route(r)


def test_nonfinite_and_duplicate_waypoints_rejected():
    r = route()
    r['waypoints'][1]['id'] = 'A'
    with pytest.raises(ValueError):
        validate_route(r)
    r = route()
    r['waypoints'][0]['x'] = float('nan')
    with pytest.raises(ValueError):
        validate_route(r)


def test_watchdog_closes_on_sensor_or_permission_loss():
    guard = MotionGuard(.2, .3, 1., allowed_at=10., command_at=10., scan_at=10.,
                        odom_at=10., allow=True)
    assert guard.command(10.1, .8, -.9) == (.2, -.3)
    assert guard.command(11.1, .8, -.9) == (0., 0.)
    guard.scan_at = 8.
    assert guard.command(10.1, .1, .1) == (0., 0.)
    guard.scan_at = 10.
    guard.allow = False
    assert guard.command(10.1, .1, .1) == (0., 0.)
    guard.allow = True
    assert guard.command(10.1, math.nan, .1) == (0., 0.)
