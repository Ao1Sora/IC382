import math
import unittest
from ic382_perception.eligibility import (
    STATUS_ELIGIBLE,
    STATUS_INELIGIBLE,
    STATUS_UNKNOWN,
    evaluate,
)


class EligibilityTests(unittest.TestCase):
    def test_clear_desk_is_eligible(self):
        self.assertEqual(evaluate(3.0, 0.0).status, STATUS_ELIGIBLE)

    def test_person_near_desk_is_ineligible(self):
        self.assertEqual(evaluate(1.0, 0.0).status, STATUS_INELIGIBLE)

    def test_reserved_card_is_ineligible(self):
        self.assertEqual(evaluate(3.0, 0.9).status, STATUS_INELIGIBLE)

    def test_stale_perception_is_unknown(self):
        self.assertEqual(evaluate(3.0, 0.0, data_fresh=False).status, STATUS_UNKNOWN)

    def test_unknown_person_distance_is_unknown(self):
        self.assertEqual(evaluate(math.nan, 0.0).status, STATUS_UNKNOWN)

    def test_no_person_data_with_fresh_perception_is_eligible(self):
        self.assertEqual(evaluate(None, 0.0).status, STATUS_ELIGIBLE)


if __name__ == "__main__":
    unittest.main()
