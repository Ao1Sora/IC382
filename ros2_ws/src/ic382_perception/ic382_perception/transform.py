"""Map 2D image detections to 3D points using a depth image and intrinsics."""
import math
import statistics


def valid_intrinsics(fx, fy):
    """Intrinsics are usable only when both focal lengths are positive."""
    return (
        math.isfinite(fx) and math.isfinite(fy) and fx > 0.0 and fy > 0.0
    )


def pixel_to_3d(u, v, depth, fx, fy, cx, cy):
    """Return (x, y, z) in the camera frame, or None for an invalid depth.

    Standard pinhole projection: z = depth, x = (u - cx) * z / fx,
    y = (v - cy) * z / fy.
    """
    if not math.isfinite(depth) or depth <= 0:
        return None
    if not all(math.isfinite(value) for value in (fx, fy, cx, cy)):
        return None
    if not valid_intrinsics(fx, fy):
        return None
    z = depth
    x = (u - cx) * z / fx
    y = (v - cy) * z / fy
    return (x, y, z)


def sample_depth_patch(depth, u, v, patch_radius=2, min_valid=3):
    """Median of valid depth values around (u, v), or None if too few pixels.

    ``depth`` is any 2D indexable array (numpy in the node, nested lists in
    tests). Zero, negative, NaN and infinite values are ignored.
    """
    try:
        height, width = depth.shape[:2]
    except AttributeError:
        try:
            height, width = len(depth), len(depth[0])
        except (TypeError, IndexError):
            return None
    except (TypeError, ValueError):
        return None
    if width <= 0 or height <= 0:
        return None
    center_u, center_v = int(round(u)), int(round(v))
    radius = max(0, int(patch_radius))
    u_min, u_max = max(0, center_u - radius), min(width - 1, center_u + radius)
    v_min, v_max = max(0, center_v - radius), min(height - 1, center_v + radius)
    if u_min > u_max or v_min > v_max:
        return None
    values = []
    for row in range(v_min, v_max + 1):
        for column in range(u_min, u_max + 1):
            value = float(depth[row][column])
            if math.isfinite(value) and value > 0:
                values.append(value)
    if len(values) < max(1, int(min_valid)):
        return None
    return statistics.median(values)


def project_detection(detection, depth, fx, fy, cx, cy, depth_scale=0.001,
                      min_depth_m=0.1, max_depth_m=10.0, patch_radius=2):
    """Project a detection to the camera frame.

    Tries the bbox centre first, then the lower-centre area (common for objects
    standing on a table). Returns ``(point_or_none, reason)``.
    """
    if not valid_intrinsics(fx, fy):
        return None, "invalid_intrinsics"
    candidates = [
        (detection.x_center, detection.y_center),
        (detection.x_center, detection.y_center + 0.3 * detection.height),
    ]
    reasons = []
    for u, v in candidates:
        raw = sample_depth_patch(depth, u, v, patch_radius=patch_radius)
        if raw is None:
            reasons.append("missing_depth")
            continue
        distance = raw * depth_scale
        if not math.isfinite(distance) or distance <= 0:
            reasons.append("invalid_depth")
            continue
        if distance < min_depth_m or distance > max_depth_m:
            reasons.append("depth_out_of_range")
            continue
        point = pixel_to_3d(u, v, distance, fx, fy, cx, cy)
        if point is None:
            reasons.append("invalid_depth")
            continue
        return point, "ok"
    if "depth_out_of_range" in reasons:
        return None, "depth_out_of_range"
    if "missing_depth" in reasons:
        return None, "missing_depth"
    return None, reasons[0] if reasons else "invalid_depth"
