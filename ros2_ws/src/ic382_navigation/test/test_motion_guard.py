import math
from ic382_navigation.core import MotionGuard


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


def test_safety_stop_overrides_authorized_motion():
    guard = MotionGuard(.2, .3, 1., allowed_at=10., command_at=10., scan_at=10.,
                        odom_at=10., allow=True, safety_stop=True)
    assert guard.reason(10.1) == 'safety_stop'
    assert guard.command(10.1, .2, .3) == (0., 0.)


def test_require_safety_blocks_when_status_is_stale():
    guard = MotionGuard(.2, .3, 1., allowed_at=10., command_at=10., scan_at=10.,
                        odom_at=10., allow=True, require_safety=True,
                        safety_timeout=.5, safety_at=10., safety_stop=False)
    assert guard.reason(10.2) == ''
    assert guard.reason(10.6) == 'safety_stale'


def test_safety_defaults_preserve_old_behavior():
    guard = MotionGuard(.2, .3, 1., allowed_at=10., command_at=10., scan_at=10.,
                        odom_at=10., allow=True)
    assert guard.reason(10.1) == ''
    assert guard.command(10.1, .2, .3) == (.2, .3)
