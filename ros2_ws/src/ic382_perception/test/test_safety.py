import math
import unittest
from ic382_perception.safety import (
    STATE_CLEAR,
    STATE_PAUSE,
    STATE_SENSOR_STALE,
    PersonSafetyGovernor,
    estimate_distance_from_height,
)


class SafetyTests(unittest.TestCase):
    def test_stop_after_confirm_frames_and_release_after_clear_frames(self):
        governor = PersonSafetyGovernor(confirm_frames=3, clear_frames=5)
        now = 0.0
        for _ in range(2):
            self.assertFalse(governor.update(0.7, True, now).stop)
            now += 0.1
        self.assertTrue(governor.update(0.7, True, now).stop)
        self.assertEqual(governor.state, STATE_PAUSE)
        for _ in range(4):
            decision = governor.update(1.3, True, now)
            self.assertTrue(decision.stop)
            now += 0.1
        decision = governor.update(1.3, True, now)
        self.assertFalse(decision.stop)
        self.assertEqual(decision.state, STATE_CLEAR)

    def test_hysteresis_band_holds_state(self):
        governor = PersonSafetyGovernor(confirm_frames=1, clear_frames=1)
        self.assertTrue(governor.update(0.7, True, 0.0).stop)
        decision = governor.update(1.0, True, 0.1)
        self.assertTrue(decision.stop)
        self.assertEqual(decision.state, STATE_PAUSE)

    def test_no_person_clears(self):
        governor = PersonSafetyGovernor(confirm_frames=1, clear_frames=2)
        governor.update(0.7, True, 0.0)
        governor.update(None, True, 0.1)
        decision = governor.update(None, True, 0.2)
        self.assertFalse(decision.stop)

    def test_stale_sensor_fails_safe(self):
        governor = PersonSafetyGovernor(sensor_timeout=0.5, fail_safe_on_stale=True)
        governor.update(None, True, 0.0)
        decision = governor.tick(2.0)
        self.assertTrue(decision.stop)
        self.assertEqual(decision.state, STATE_SENSOR_STALE)

    def test_stale_sensor_can_be_non_blocking_for_simulation(self):
        governor = PersonSafetyGovernor(sensor_timeout=0.5, fail_safe_on_stale=False)
        governor.update(None, True, 0.0)
        decision = governor.tick(2.0)
        self.assertFalse(decision.stop)

    def test_unknown_distance_stops_when_configured(self):
        governor = PersonSafetyGovernor(confirm_frames=1, unknown_distance_stop=True)
        decision = governor.update(math.nan, True, 0.0)
        self.assertTrue(decision.stop)

    def test_height_fallback(self):
        self.assertAlmostEqual(estimate_distance_from_height(500.0, 100.0, 1.7), 8.5)
        self.assertIsNone(estimate_distance_from_height(0.0, 100.0))
        self.assertIsNone(estimate_distance_from_height(500.0, 0.0))


if __name__ == "__main__":
    unittest.main()
