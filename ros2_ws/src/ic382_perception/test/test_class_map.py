import unittest
from ic382_perception import class_map


class ClassMapTests(unittest.TestCase):
    def test_ids_map_to_codes(self):
        self.assertEqual(class_map.CLASS_ID_TO_CODE, {0: "A", 1: "B", 2: "C"})

    def test_valid_ids(self):
        self.assertEqual(class_map.VALID_CLASS_IDS, {0, 1, 2})

    def test_default_threshold(self):
        self.assertEqual(class_map.CONF_THRESHOLD, 0.5)

    def test_names(self):
        self.assertEqual(class_map.CLASS_ID_TO_NAME[0], "Class_A_IC_Material")
        self.assertEqual(class_map.CLASS_ID_TO_NAME[1], "Class_B_Personal")
        self.assertEqual(class_map.CLASS_ID_TO_NAME[2], "Class_C_Disposables")


if __name__ == "__main__":
    unittest.main()
