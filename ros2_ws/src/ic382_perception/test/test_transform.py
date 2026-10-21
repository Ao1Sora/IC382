import unittest
from ic382_perception.transform import pixel_to_3d


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


if __name__ == "__main__":
    unittest.main()
