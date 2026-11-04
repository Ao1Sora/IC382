"""Desk eligibility from person proximity and reserved-card detections."""
import math
from dataclasses import dataclass

STATUS_ELIGIBLE = "ELIGIBLE"
STATUS_INELIGIBLE = "INELIGIBLE"
STATUS_UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Eligibility:
    status: str
    reason: str


def evaluate(nearest_person_m, reserved_card_confidence, person_limit_m=1.5,
             reserved_min=0.5, data_fresh=True):
    """A desk is ineligible if someone is seated nearby or a card is present."""
    if not data_fresh:
        return Eligibility(STATUS_UNKNOWN, "stale_perception")
    if nearest_person_m is not None and not _finite(nearest_person_m):
        return Eligibility(STATUS_UNKNOWN, "person_distance_unknown")
    if _finite(reserved_card_confidence) and reserved_card_confidence >= reserved_min:
        return Eligibility(STATUS_INELIGIBLE, "reserved_card")
    if _finite(nearest_person_m) and nearest_person_m <= person_limit_m:
        return Eligibility(STATUS_INELIGIBLE, "person_near_desk")
    return Eligibility(STATUS_ELIGIBLE, "clear")


def _finite(value):
    return (
        value is not None
        and isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )
