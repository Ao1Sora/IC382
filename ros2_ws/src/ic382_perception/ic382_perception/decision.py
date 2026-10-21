"""Pure decision logic: classify detections into TAG or LOG_ONLY actions.

The "anomalous protocol": a confident, in-scope detection is tagged; anything
else (low confidence or an unknown/out-of-scope class) is logged only, with no
tag command issued, so unknown property is never altered.
"""
from dataclasses import dataclass
from enum import Enum


class Action(Enum):
    TAG = "tag"
    LOG_ONLY = "log_only"


@dataclass(frozen=True)
class Detection:
    bbox: tuple          # (x_center, y_center, width, height) in pixels
    class_id: int
    confidence: float

    @property
    def x_center(self):
        return self.bbox[0]

    @property
    def y_center(self):
        return self.bbox[1]

    @property
    def width(self):
        return self.bbox[2]

    @property
    def height(self):
        return self.bbox[3]


def classify(detection, conf_threshold, valid_class_ids):
    """Return Action.TAG for a confident in-scope object, else Action.LOG_ONLY."""
    if detection.confidence >= conf_threshold and detection.class_id in valid_class_ids:
        return Action.TAG
    return Action.LOG_ONLY


def reason(detection, conf_threshold, valid_class_ids):
    """Human-readable reason a detection is logged only (for the decision log)."""
    if detection.confidence < conf_threshold:
        return "low_confidence"
    return "out_of_scope"


def classify_all(detections, conf_threshold, valid_class_ids):
    """Map every detection to its action, preserving order."""
    return [classify(d, conf_threshold, valid_class_ids) for d in detections]
