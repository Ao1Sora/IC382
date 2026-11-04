import unittest
from ic382_perception.decision import Action, Detection, classify, decide, reason


def detection(confidence, class_id=0):
    return Detection(bbox=(100.0, 100.0, 20.0, 30.0), class_id=class_id, confidence=confidence)


class DecisionTests(unittest.TestCase):
    def test_confident_in_scope_tags(self):
        self.assertEqual(classify(detection(0.9, 0), 0.5, {0, 1, 2}), Action.TAG)

    def test_low_confidence_logs_only(self):
        self.assertEqual(classify(detection(0.4, 0), 0.5, {0, 1, 2}), Action.LOG_ONLY)

    def test_out_of_scope_class_logs_only(self):
        self.assertEqual(classify(detection(0.9, 9), 0.5, {0, 1, 2}), Action.LOG_ONLY)

    def test_threshold_boundary_tags(self):
        self.assertEqual(classify(detection(0.5, 1), 0.5, {0, 1, 2}), Action.TAG)

    def test_reason_low_confidence(self):
        self.assertEqual(reason(detection(0.4), 0.5, {0, 1, 2}), "low_confidence")

    def test_reason_out_of_scope(self):
        self.assertEqual(reason(detection(0.9, 7), 0.5, {0, 1, 2}), "out_of_scope")


class DecideTests(unittest.TestCase):
    def test_low_confidence_is_anomaly(self):
        self.assertEqual(decide("A", 0.4), (Action.ANOMALY, "low_confidence"))

    def test_out_of_scope_is_anomaly(self):
        self.assertEqual(decide("OUT_OF_SCOPE", 0.9),
                         (Action.ANOMALY, "out_of_scope"))

    def test_person_is_log_only_not_anomaly(self):
        self.assertEqual(decide("PERSON", 0.9), (Action.LOG_ONLY, "person"))

    def test_tagging_disabled_is_log_only(self):
        self.assertEqual(decide("C", 0.9, tagging_enabled=False),
                         (Action.LOG_ONLY, "tagging_disabled"))

    def test_invalid_position_is_log_only(self):
        self.assertEqual(
            decide("A", 0.9, position_valid=False, projection_reason="tf_unavailable"),
            (Action.LOG_ONLY, "tf_unavailable"))

    def test_unconfirmed_is_log_only(self):
        self.assertEqual(decide("B", 0.9, confirmed=False),
                         (Action.LOG_ONLY, "not_confirmed"))

    def test_confirmed_taggable_is_tag(self):
        self.assertEqual(decide("C", 0.5), (Action.TAG, "confirmed_abandoned"))


if __name__ == "__main__":
    unittest.main()
