"""Pure pedestrian safety governor with distance hysteresis.

The governor never publishes anything; safety_monitor converts its decisions
into /ic382/safety_stop.
"""
import math
from dataclasses import dataclass

STATE_CLEAR = "CLEAR"
STATE_PAUSE = "PAUSE"
STATE_SENSOR_STALE = "SENSOR_STALE"
STATE_DISABLED = "DISABLED"


@dataclass(frozen=True)
class SafetyDecision:
    state: str
    stop: bool
    nearest_person_m: float


def estimate_distance_from_height(fy, bbox_height_px, person_height_m=1.7):
    """Fallback RGB range estimate: distance ~= fy * real_height / pixel_height."""
    if not all(math.isfinite(value) for value in (fy, bbox_height_px, person_height_m)):
        return None
    if fy <= 0 or bbox_height_px <= 0 or person_height_m <= 0:
        return None
    return fy * person_height_m / bbox_height_px


class PersonSafetyGovernor:
    """0.8 m stop / 1.2 m release with frame confirmation and sensor watchdog."""

    def __init__(self, stop_distance_m=0.8, clear_distance_m=1.2,
                 confirm_frames=3, clear_frames=5, sensor_timeout=0.5,
                 fail_safe_on_stale=True, unknown_distance_stop=True):
        if not (0 < stop_distance_m < clear_distance_m):
            raise ValueError("stop distance must be positive and below clear distance")
        if confirm_frames < 1 or clear_frames < 1:
            raise ValueError("frame counts must be positive")
        self.stop_distance_m = float(stop_distance_m)
        self.clear_distance_m = float(clear_distance_m)
        self.confirm_frames = int(confirm_frames)
        self.clear_frames = int(clear_frames)
        self.sensor_timeout = float(sensor_timeout)
        self.fail_safe_on_stale = bool(fail_safe_on_stale)
        self.unknown_distance_stop = bool(unknown_distance_stop)
        self.state = STATE_CLEAR
        self.stop = False
        self.nearest_person_m = math.nan
        self.last_update = None
        self._stop_count = 0
        self._clear_count = 0

    def decision(self):
        return SafetyDecision(self.state, self.stop, self.nearest_person_m)

    def _set_stop(self, state=STATE_PAUSE):
        self.state = state
        self.stop = True

    def _set_clear(self):
        self.state = STATE_CLEAR
        self.stop = False

    def update(self, distance_m, sensor_ok, now):
        """Feed one detector frame. ``distance_m=None`` means no person seen."""
        self.last_update = now
        if not sensor_ok:
            self._stop_count = 0
            self._clear_count = 0
            if self.fail_safe_on_stale:
                self._set_stop(STATE_SENSOR_STALE)
            else:
                self.state = STATE_SENSOR_STALE
                self.stop = False
            return self.decision()

        if distance_m is None:
            self.nearest_person_m = math.nan
            self._stop_count = 0
            self._clear_count += 1
            if self._clear_count >= self.clear_frames:
                self._set_clear()
            return self.decision()

        if not math.isfinite(distance_m):
            self.nearest_person_m = math.nan
            self._clear_count = 0
            if self.unknown_distance_stop:
                self._stop_count += 1
                if self._stop_count >= self.confirm_frames:
                    self._set_stop()
            return self.decision()

        self.nearest_person_m = float(distance_m)
        if distance_m <= self.stop_distance_m:
            self._clear_count = 0
            self._stop_count += 1
            if self._stop_count >= self.confirm_frames:
                self._set_stop()
        elif distance_m > self.clear_distance_m:
            self._stop_count = 0
            self._clear_count += 1
            if self._clear_count >= self.clear_frames:
                self._set_clear()
        else:
            # Inside the hysteresis band: hold the current state.
            self._stop_count = 0
            self._clear_count = 0
        return self.decision()

    def tick(self, now):
        """Watchdog check for missing detector frames."""
        stale = self.last_update is None or now - self.last_update > self.sensor_timeout
        if stale:
            if self.fail_safe_on_stale:
                self._set_stop(STATE_SENSOR_STALE)
            elif self.state != STATE_DISABLED:
                self.state = STATE_SENSOR_STALE
                self.stop = False
        return self.decision()
