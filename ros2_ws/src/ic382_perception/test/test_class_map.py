import unittest
from ic382_perception import class_map


class ClassMapTests(unittest.TestCase):
    def test_ids_map_to_codes(self):
        self.assertEqual(class_map.CLASS_ID_TO_CODE, {0: "A", 1: "B", 2: "C"})

    def test_valid_ids(self):
        self.assertEqual(class_map.VALID_CLASS_IDS, {0, 1, 2})
        self.assertEqual(class_map.TAGGABLE_IDS, {0, 1, 2})

    def test_default_threshold(self):
        self.assertEqual(class_map.CONF_THRESHOLD, 0.5)

    def test_five_class_names(self):
        self.assertEqual(class_map.CLASS_ID_TO_NAME, {
            0: "ic_material",
            1: "personal",
            2: "disposables",
            3: "person",
            4: "reserved_card",
        })

    def test_roles(self):
        self.assertEqual(class_map.CLASS_ID_TO_ROLE[3], "PERSON")
        self.assertEqual(class_map.CLASS_ID_TO_ROLE[4], "RESERVED_CARD")
        self.assertEqual(class_map.ELIGIBILITY_IDS, {3, 4})

    def test_name_aliases(self):
        self.assertEqual(class_map.role_for_class_name("Class_A_IC_Material"), "A")
        self.assertEqual(class_map.role_for_class_name("class_c_disposables"), "C")
        self.assertEqual(class_map.role_for_class_name("RESERVED CARD"), "RESERVED_CARD")
        self.assertEqual(class_map.role_for_class_name("bicycle"), "OUT_OF_SCOPE")

    def test_class_codes(self):
        self.assertEqual(class_map.class_code_for_role("B"), "B")
        self.assertIsNone(class_map.class_code_for_role("PERSON"))


if __name__ == "__main__":
    unittest.main()
