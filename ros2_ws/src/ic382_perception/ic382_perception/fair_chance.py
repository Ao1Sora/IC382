"""Pure two-round fair-chance association logic.

Round 1 records candidate items. Round 2 matches them again; only items still
present after the dwell period become CONFIRMED_ABANDONED.
"""
import math
from dataclasses import dataclass

STATUS_CONFIRMED = "CONFIRMED_ABANDONED"
STATUS_OWNER_RETURNED = "OWNER_RETURNED"
STATUS_OCCUPIED = "DESK_NOW_OCCUPIED"
STATUS_NEW = "NEW_ITEM_ANOMALOUS"

ACTION_TAGGED = "TAGGED_CLASS_{}"
ACTION_OWNER_RETURNED = "NO_TAG_OWNER_RETURNED"
ACTION_OCCUPIED = "NO_TAG_DESK_OCCUPIED"
ACTION_ANOMALOUS = "NO_TAG_ANOMALOUS"
ACTION_INELIGIBLE = "NO_TAG_INELIGIBLE"
ACTION_UNKNOWN = "NO_TAG_UNKNOWN"


@dataclass(frozen=True)
class DetectionRecord:
    class_code: str
    class_name: str
    confidence: float
    bbox: tuple
    position_m: tuple = None          # map frame, used for association
    base_position_m: tuple = None     # base_link at capture, used for tagging
    point_id: str = ""


@dataclass(frozen=True)
class Item:
    item_id: int
    class_code: str
    class_name: str
    confidence: float
    bbox: tuple
    position_m: tuple = None
    first_point_id: str = ""
    last_seen_ns: int = 0


@dataclass(frozen=True)
class Round2Result:
    item_id: int
    status: str
    action_taken: str
    item: Item


def _finite_position(position):
    if position is None:
        return None
    try:
        values = tuple(float(value) for value in position)
    except (TypeError, ValueError):
        return None
    if len(values) != 3 or not all(math.isfinite(value) for value in values):
        return None
    return values


def iou_xywh(a, b):
    """IoU for (cx, cy, w, h) boxes."""
    ax, ay, aw, ah = (float(value) for value in a)
    bx, by, bw, bh = (float(value) for value in b)
    a_left, a_top = ax - aw / 2.0, ay - ah / 2.0
    b_left, b_top = bx - bw / 2.0, by - bh / 2.0
    left, top = max(a_left, b_left), max(a_top, b_top)
    right = min(a_left + aw, b_left + bw)
    bottom = min(a_top + ah, b_top + bh)
    if right <= left or bottom <= top:
        return 0.0
    intersection = (right - left) * (bottom - top)
    union = max(1e-9, aw * ah + bw * bh - intersection)
    return intersection / union


def center_distance_ratio(a, b):
    """Centre distance normalised by the average box size."""
    ax, ay, aw, ah = (float(value) for value in a)
    bx, by, bw, bh = (float(value) for value in b)
    distance = math.hypot(ax - bx, ay - by)
    size = max(1e-9, 0.5 * (aw + ah + bw + bh) / 2.0)
    return distance / size


def _position_distance(a, b):
    if a is None or b is None:
        return math.inf
    return math.sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)))


def _same_class(left, right):
    return str(left).strip().upper() == str(right).strip().upper()


def _match_score(item, detection, iou_min, center_ratio_max, position_m):
    """Return a sortable score or None when the pair does not match.

    When both sides have a map-frame position, that position is authoritative;
    pixel IoU across different viewpoints is not comparable and is only used as
    a fallback when 3D is unavailable.
    """
    if not _same_class(item.class_code, detection.class_code):
        return None
    distance = _position_distance(item.position_m, _finite_position(detection.position_m))
    iou = iou_xywh(item.bbox, detection.bbox)
    ratio = center_distance_ratio(item.bbox, detection.bbox)
    if math.isfinite(distance):
        if distance > position_m:
            return None
        return (distance, ratio, -iou)
    if iou < iou_min and ratio > center_ratio_max:
        return None
    # Lower is better: normalised centre distance dominates, then IoU.
    return (0.0, ratio, -iou)


def associate(previous_items, current_detections, iou_min=0.3,
              center_ratio_max=0.6, position_m=0.25, require_class=True):
    """Greedy one-to-one matching; returns {item_id: DetectionRecord}."""
    candidates = []
    for item in previous_items:
        for index, detection in enumerate(current_detections):
            if require_class:
                score = _match_score(item, detection, iou_min, center_ratio_max, position_m)
            else:
                score = _match_score(
                    Item(item.item_id, detection.class_code, detection.class_name,
                         detection.confidence, detection.bbox, detection.position_m),
                    detection, iou_min, center_ratio_max, position_m,
                )
            if score is not None:
                candidates.append((score, item.item_id, index))
    candidates.sort(key=lambda entry: entry[0])
    matches = {}
    used_detections = set()
    for _, item_id, index in candidates:
        if item_id in matches or index in used_detections:
            continue
        matches[item_id] = current_detections[index]
        used_detections.add(index)
    return matches


def merge_across_views(existing_items, detections, next_id,
                       iou_min=0.3, center_ratio_max=0.6, position_m=0.25):
    """Merge round-1 detections from several viewpoints into stable items."""
    items = list(existing_items)
    next_identifier = int(next_id)
    for detection in detections:
        position = _finite_position(detection.position_m)
        best_index, best_score = None, None
        for index, item in enumerate(items):
            if not _same_class(item.class_code, detection.class_code):
                continue
            distance = _position_distance(item.position_m, position)
            iou = iou_xywh(item.bbox, detection.bbox)
            ratio = center_distance_ratio(item.bbox, detection.bbox)
            if math.isfinite(distance):
                if distance > position_m:
                    continue
                score = (distance, ratio, -iou)
            else:
                if iou < iou_min and ratio > center_ratio_max:
                    continue
                score = (0.0, ratio, -iou)
            if best_score is None or score < best_score:
                best_index, best_score = index, score
        if best_index is None:
            items.append(Item(
                item_id=next_identifier,
                class_code=detection.class_code,
                class_name=detection.class_name,
                confidence=float(detection.confidence),
                bbox=tuple(detection.bbox),
                position_m=position,
                first_point_id=detection.point_id,
                last_seen_ns=0,
            ))
            next_identifier += 1
        else:
            item = items[best_index]
            items[best_index] = Item(
                item_id=item.item_id,
                class_code=item.class_code,
                class_name=item.class_name,
                confidence=max(item.confidence, float(detection.confidence)),
                bbox=tuple(detection.bbox),
                position_m=position if position is not None else item.position_m,
                first_point_id=item.first_point_id or detection.point_id,
                last_seen_ns=0,
            )
    return items, next_identifier


def validate_round2(items, matches, occupied=False, tagging_enabled=True):
    """Turn round-1 items plus round-2 matches into statuses and actions."""
    results = []
    for item in items:
        if occupied:
            results.append(Round2Result(
                item.item_id, STATUS_OCCUPIED, ACTION_OCCUPIED, item))
            continue
        if item.item_id not in matches:
            results.append(Round2Result(
                item.item_id, STATUS_OWNER_RETURNED, ACTION_OWNER_RETURNED, item))
            continue
        if tagging_enabled and item.class_code in ("A", "B", "C"):
            action = ACTION_TAGGED.format(item.class_code)
        else:
            action = ACTION_UNKNOWN
        results.append(Round2Result(
            item.item_id, STATUS_CONFIRMED, action, item))
    return results


def new_items(detections, next_id, start_index=0):
    """Create anomalous results for items first seen in round 2."""
    results = []
    next_identifier = int(next_id)
    for offset, detection in enumerate(detections):
        item = Item(
            item_id=next_identifier + offset,
            class_code=detection.class_code,
            class_name=detection.class_name,
            confidence=float(detection.confidence),
            bbox=tuple(detection.bbox),
            position_m=_finite_position(detection.position_m),
            first_point_id=detection.point_id,
        )
        results.append(Round2Result(item.item_id, STATUS_NEW, ACTION_ANOMALOUS, item))
    return results, next_identifier + len(detections)
