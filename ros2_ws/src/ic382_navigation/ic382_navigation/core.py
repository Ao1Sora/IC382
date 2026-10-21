"""ROS-independent mission decisions and input validation, using monotonic time."""
from dataclasses import dataclass
import math


def positive(value, name, allow_zero=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{name} must be a number')
    if not math.isfinite(value) or value < 0 or (not allow_zero and value == 0):
        raise ValueError(f'{name} must be finite and positive')
    return float(value)


def validate_route(raw, allow_uncalibrated=False):
    if not isinstance(raw, dict) or raw.get('schema_version') != 1:
        raise ValueError('Route must use schema_version: 1')
    if raw.get('frame_id') != 'map':
        raise ValueError('Waypoints must be in the map frame')
    if raw.get('calibrated') is not True and not allow_uncalibrated:
        raise ValueError('Record and verify real waypoints, then set calibrated: true')
    rounds = raw.get('rounds', 2)
    if isinstance(rounds, bool) or not isinstance(rounds, int) or not 1 <= rounds <= 10:
        raise ValueError('rounds must be an integer in [1, 10]')
    points = raw.get('waypoints')
    if not isinstance(points, list) or not points:
        raise ValueError('At least one waypoint is required')
    ids = set()
    for p in points:
        if not isinstance(p, dict) or not isinstance(p.get('id'), str) or not p['id'].strip():
            raise ValueError('Each waypoint needs a nonempty id')
        if p['id'] in ids:
            raise ValueError('Waypoint ids must be unique')
        ids.add(p['id'])
        for key in ('x', 'y', 'yaw'):
            v = p.get(key)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
                raise ValueError(f'{p["id"]}.{key} must be finite')
    for key in ('inspection_seconds', 'tagging_seconds'):
        positive(raw.get(key, 3.0), key, allow_zero=True)
    return raw


@dataclass
class MotionGuard:
    max_linear: float
    max_angular: float
    timeout: float
    allowed_at: float = -math.inf
    command_at: float = -math.inf
    scan_at: float = -math.inf
    odom_at: float = -math.inf
    allow: bool = False

    def reason(self, now):
        if not self.allow or now - self.allowed_at > self.timeout:
            return 'motion_not_authorized'
        for name in ('command', 'scan', 'odom'):
            if now - getattr(self, name + '_at') > self.timeout:
                return name + '_stale'
        return ''

    def command(self, now, v, w):
        if self.reason(now) or not all(math.isfinite(x) for x in (v, w)):
            return 0.0, 0.0
        return (max(-self.max_linear, min(self.max_linear, v)),
                max(-self.max_angular, min(self.max_angular, w)))


class MissionEngine:
    """Navigation is real. Inspection/tagging are always identified as simulated."""
    def __init__(self, route, navigator, emit):
        self.route = validate_route(route)
        self.navigator = navigator
        self.emit = emit
        self.state = 'IDLE'
        self.index = 0
        self.round = 1
        self.deadline = 0.0

    @property
    def waypoint(self):
        return self.route['waypoints'][self.index]

    def event(self, event, **data):
        self.emit(event, {'desk_id': self.waypoint['id'], 'round': self.round,
                          'state': self.state, **data})

    def start(self, now):
        if self.state != 'IDLE':
            return False
        self.state = 'NAVIGATING'
        self.emit('mission_started', {'rounds': self.route.get('rounds', 2),
                                     'placeholders': True, 'route': self.route})
        self._navigate(now)
        return True

    def _navigate(self, now):
        self.state = 'NAVIGATING'
        self.event('navigation_requested', goal=self.waypoint)
        self.navigator.start(self.waypoint, now)

    def cancel(self, reason='operator_cancelled'):
        if self.state in ('IDLE', 'COMPLETED', 'FAILED', 'CANCELED'):
            return False
        self.navigator.cancel(reason)
        self.state = 'CANCELED'
        self.event('mission_canceled', reason=reason)
        return True

    def fail(self, reason):
        self.navigator.cancel(reason)
        self.state = 'FAILED'
        self.event('mission_failed', reason=reason)

    def tick(self, now):
        if self.state == 'NAVIGATING':
            result = self.navigator.poll(now)
            if result is None:
                return
            if result != 'SUCCEEDED':
                self.fail(result)
                return
            self.event('navigation_succeeded')
            self.state = 'INSPECTING'
            self.deadline = now + self.route.get('inspection_seconds', 3.0)
            self.event('inspection_stub_started', simulated=True)
        elif self.state == 'INSPECTING' and now >= self.deadline:
            self.event('inspection_stub_completed', simulated=True,
                       observation='placeholder_only_no_classification_or_eligibility')
            if self.round == self.route.get('rounds', 2):
                self.state = 'TAGGING'
                self.deadline = now + self.route.get('tagging_seconds', 3.0)
                self.event('tagging_stub_started', simulated=True)
            else:
                self._next(now)
        elif self.state == 'TAGGING' and now >= self.deadline:
            self.event('tagging_stub_completed', simulated=True, actuator_command_sent=False)
            self._next(now)

    def _next(self, now):
        self.index += 1
        if self.index == len(self.route['waypoints']):
            self.index = 0
            if self.round == self.route.get('rounds', 2):
                self.state = 'COMPLETED'
                self.emit('mission_completed', {'rounds': self.round, 'placeholders': True})
                return
            self.round += 1
        self._navigate(now)
