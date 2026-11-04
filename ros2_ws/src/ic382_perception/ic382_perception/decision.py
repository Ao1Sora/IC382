"""Pure decision logic for classified detections.

The ``decide`` function is the only place that turns a role, confidence and
position validity into TAG / LOG_ONLY / ANOMALY. TAG here means "eligible for
tagging once the fair-chance manager has confirmed abandonment"; the classifier
itself never publishes a tag command.
"""
from dataclasses import dataclass
from enum import Enum

from ic382_perception.class_map import (
    ELIGIBILITY_ROLES,
    ROLE_OUT_OF_SCOPE,
    TAGGABLE_ROLES,
)


class Action(Enum):
    TAG = "tag"
    LOG_ONLY = "log_only"
    ANOMALY = "anomaly"


@dataclass(frozen=True)
class Detection:
    bbox: tuple          # (x_center, y_center, width, height) in pixels
    class_id: int
    confidence: float
    class_name: str = ""

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
    """Legacy three-class helper retained for existing tests."""
    if detection.confidence >= conf_threshold and detection.class_id in valid_class_ids:
        return Action.TAG
    return Action.LOG_ONLY


def reason(detection, conf_threshold, valid_class_ids):
    """Human-readable reason a legacy detection is logged only."""
    if detection.confidence < conf_threshold:
        return "low_confidence"
    return "out_of_scope"


def decide(role, confidence, tagging_enabled=True, position_valid=True,
           confirmed=True, conf_threshold=0.5, projection_reason=""):
    """Return (Action, reason) for a classified detection.

    Order matters: an unknown or low-confidence detection is an anomaly even
    when tagging is enabled; safety classes are never anomalies but are never
    tagged either.
    """
    if confidence < conf_threshold:
        return Action.ANOMALY, "low_confidence"
    if role is None or role == ROLE_OUT_OF_SCOPE:
        return Action.ANOMALY, "out_of_scope"
    if role in ELIGIBILITY_ROLES:
        return Action.LOG_ONLY, str(role).lower()
    if not tagging_enabled:
        return Action.LOG_ONLY, "tagging_disabled"
    if not position_valid:
        return Action.LOG_ONLY, projection_reason or "missing_position"
    if not confirmed:
        return Action.LOG_ONLY, "not_confirmed"
    if role in TAGGABLE_ROLES:
        return Action.TAG, "confirmed_abandoned"
    return Action.ANOMALY, "out_of_scope"


def classify_all(detections, conf_threshold, valid_class_ids):
    """Map every detection to its action, preserving order."""
    return [classify(d, conf_threshold, valid_class_ids) for d in detections]
