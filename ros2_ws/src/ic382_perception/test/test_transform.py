import unittest
from ic382_perception.decision import Detection
from ic382_perception.transform import (
    pixel_to_3d,
    project_detection,
    sample_depth_patch,
    valid_intrinsics,
)


class TransformTests(unittest.TestCase):
    def test_center_pixel_straight_ahead(self):
        x, y, z = pixel_to_3d(320, 240, 2.0, 500, 500, 320, 240)
        self.assertAlmostEqual(x, 0.0)
        self.assertAlmostEqual(y, 0.0)
        self.assertAlmostEqual(z, 2.0)

    def test_offset_pixel(self):
        x, y, z = pixel_to_3d(420, 340, 2.0, 500, 500, 320, 240)
        self.assertAlmostEqual(x, (420 - 320) * 2.0 / 500)
        self.assertAlmostEqual(y, (340 - 240) * 2.0 / 500)
        self.assertAlmostEqual(z, 2.0)

    def test_zero_depth_is_invalid(self):
        self.assertIsNone(pixel_to_3d(320, 240, 0.0, 500, 500, 320, 240))

    def test_nonfinite_depth_is_invalid(self):
        self.assertIsNone(pixel_to_3d(320, 240, float("inf"), 500, 500, 320, 240))
        self.assertIsNone(pixel_to_3d(320, 240, float("nan"), 500, 500, 320, 240))

    def test_zero_focal_length_is_invalid(self):
        self.assertFalse(valid_intrinsics(0.0, 500.0))
        self.assertIsNone(pixel_to_3d(320, 240, 2.0, 0.0, 500.0, 320, 240))

    def test_sample_depth_patch_median_ignores_invalid(self):
        depth = [
            [0, 0, 0],
            [0, 1000, 2000],
            [0, 0, 0],
        ]
        self.assertEqual(
            sample_depth_patch(depth, 1, 1, patch_radius=1, min_valid=2), 1500.0)

    def test_sample_depth_patch_requires_enough_pixels(self):
        depth = [[0, 0], [0, 1000]]
        self.assertIsNone(sample_depth_patch(depth, 0, 0, patch_radius=1, min_valid=3))

    def test_project_detection_uses_depth(self):
        detection = Detection(bbox=(320.0, 240.0, 40.0, 40.0),
                              class_id=0, confidence=0.9)
        depth = [[1000 for _ in range(640)] for _ in range(480)]
        point, reason = project_detection(
            detection, depth, 500, 500, 320, 240, depth_scale=0.001)
        self.assertEqual(reason, "ok")
        self.assertAlmostEqual(point[2], 1.0)

    def test_project_detection_reports_missing_depth(self):
        detection = Detection(bbox=(320.0, 240.0, 40.0, 40.0),
                              class_id=0, confidence=0.9)
        depth = [[0 for _ in range(640)] for _ in range(480)]
        point, reason = project_detection(detection, depth, 500, 500, 320, 240)
        self.assertIsNone(point)
        self.assertEqual(reason, "missing_depth")


if __name__ == "__main__":
    unittest.main()
