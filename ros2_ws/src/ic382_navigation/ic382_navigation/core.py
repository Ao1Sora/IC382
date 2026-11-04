"""Motion authorization and freshness watchdog."""
from dataclasses import dataclass
import math


def positive(value, name, allow_zero=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{name} must be a number')
    if not math.isfinite(value) or value < 0 or (not allow_zero and value == 0):
        raise ValueError(f'{name} must be finite and positive')
    return float(value)


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
    safety_stop: bool = False
    safety_at: float = -math.inf
    require_safety: bool = False
    safety_timeout: float = 0.5

    def reason(self, now):
        if self.safety_stop:
            return 'safety_stop'
        if self.require_safety and now - self.safety_at > self.safety_timeout:
            return 'safety_stale'
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
