import unittest
from ic382_perception.decision import Action, Detection, classify, reason


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


if __name__ == "__main__":
    unittest.main()
