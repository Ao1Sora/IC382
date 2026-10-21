"""Map a 2D pixel to a 3D point in the camera frame using a depth value."""
import math


def pixel_to_3d(u, v, depth, fx, fy, cx, cy):
    """Return (x, y, z) in the camera frame, or None for an invalid depth.

    Standard pinhole projection: z = depth, x = (u - cx) * z / fx,
    y = (v - cy) * z / fy.
    """
    if not math.isfinite(depth) or depth <= 0:
        return None
    if not all(math.isfinite(value) for value in (fx, fy, cx, cy)):
        return None
    z = depth
    x = (u - cx) * z / fx
    y = (v - cy) * z / fy
    return (x, y, z)
