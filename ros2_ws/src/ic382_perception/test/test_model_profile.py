import unittest
from ic382_perception.model_profile import resolve_profile


class ModelProfileTests(unittest.TestCase):
    def test_steward_maps_by_name_not_id(self):
        names = {
            9: "reserved_card",
            4: "person",
            7: "disposables",
            2: "personal",
            1: "ic_material",
        }
        profile = resolve_profile("steward_v1", names)
        self.assertTrue(profile.tagging_enabled)
        self.assertEqual(profile.role_for(1), "A")
        self.assertEqual(profile.role_for(2), "B")
        self.assertEqual(profile.role_for(7), "C")
        self.assertEqual(profile.role_for(4), "PERSON")
        self.assertEqual(profile.role_for(9), "RESERVED_CARD")
        self.assertEqual(profile.degraded_reason, "")

    def test_bootstrap_only_person_is_in_scope(self):
        profile = resolve_profile("coco_bootstrap", {0: "person", 39: "bottle"})
        self.assertFalse(profile.tagging_enabled)
        self.assertEqual(profile.role_for(0), "PERSON")
        self.assertEqual(profile.role_for(39), "OUT_OF_SCOPE")

    def test_steward_missing_class_degrades_to_observe_only(self):
        names = {0: "ic_material", 1: "personal", 2: "disposables", 3: "person"}
        profile = resolve_profile("steward_v1", names)
        self.assertFalse(profile.tagging_enabled)
        self.assertIn("reserved_card", profile.degraded_reason)

    def test_auto_picks_steward_when_all_names_present(self):
        names = {0: "ic_material", 1: "personal", 2: "disposables",
                 3: "person", 4: "reserved_card"}
        profile = resolve_profile("auto", names)
        self.assertEqual(profile.name, "steward_v1")
        self.assertTrue(profile.tagging_enabled)

    def test_auto_falls_back_to_bootstrap(self):
        profile = resolve_profile("auto", {0: "person", 1: "car"})
        self.assertEqual(profile.name, "coco_bootstrap")
        self.assertFalse(profile.tagging_enabled)

    def test_unknown_profile_rejected(self):
        with self.assertRaises(ValueError):
            resolve_profile("nope", {0: "person"})


if __name__ == "__main__":
    unittest.main()
