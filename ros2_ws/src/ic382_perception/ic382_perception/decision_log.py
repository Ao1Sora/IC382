"""Decision-log writers.

Two formats are supported:
- ``write_entry``: append-only JSON Lines, kept for the original audit path.
- ``SpecDecisionLog``: the single structured JSON document required by the
  master specification at /home/student/dev/decision_log.json.

The mission-level JSON is written by the fair-chance manager only.
"""
import copy
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import tempfile

from ic382_perception.class_map import CLASS_CODE_TO_LABEL


def write_entry(path, entry):
    """Append one JSON entry to the decision log, creating parent dirs as needed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(entry, ensure_ascii=False) + "\n")


def write_json_atomic(path, document):
    """Write JSON via a temporary file in the same directory, then replace."""
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(document, ensure_ascii=False, allow_nan=False, indent=2)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=str(path.parent),
        prefix=path.name + ".", suffix=".tmp", delete=False,
    ) as stream:
        stream.write(payload)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
        temporary = stream.name
    os.replace(temporary, path)


def _utc_now_text():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _clock_text():
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


class SpecDecisionLog:
    """Incrementally maintain the master-spec decision_log.json document."""

    def __init__(self, path, mission_timestamp=None, clock=None):
        self.path = Path(path).expanduser()
        self.clock = clock or _clock_text
        self.mission_timestamp = mission_timestamp or _utc_now_text()
        self._records = {}
        self._order = []
        self.flush()

    def _record(self, desk_id):
        desk_id = str(desk_id)
        if desk_id not in self._records:
            self._records[desk_id] = {
                "desk_id": desk_id,
                "desk_status": "UNKNOWN",
                "round_1_seen": [],
                "round_2_validation": [],
                "anomalous_items": [],
            }
            self._order.append(desk_id)
        return self._records[desk_id]

    def begin_desk(self, desk_id):
        self._record(desk_id)
        self.flush()

    def update_desk_status(self, desk_id, status):
        self._record(desk_id)["desk_status"] = str(status)
        self.flush()

    def record_round1(self, desk_id, item_id, class_code, confidence, timestamp=None):
        self._record(desk_id)["round_1_seen"].append({
            "item_id": int(item_id),
            "class": CLASS_CODE_TO_LABEL.get(str(class_code), str(class_code)),
            "confidence": round(float(confidence), 4),
            "timestamp": timestamp or self.clock(),
        })
        self.flush()

    def record_round2(self, desk_id, item_id, status, action_taken):
        self._record(desk_id)["round_2_validation"].append({
            "item_id": int(item_id),
            "status": str(status),
            "action_taken": str(action_taken),
        })
        self.flush()

    def record_anomaly(self, desk_id, class_name, confidence, reason, timestamp=None):
        self._record(desk_id)["anomalous_items"].append({
            "class": str(class_name),
            "confidence": round(float(confidence), 4),
            "reason": str(reason),
            "timestamp": timestamp or self.clock(),
        })
        self.flush()

    def snapshot(self):
        return copy.deepcopy({
            "mission_timestamp": self.mission_timestamp,
            "desk_records": [self._records[key] for key in self._order],
        })

    def flush(self):
        write_json_atomic(self.path, self.snapshot())

    def finish(self):
        self.flush()
        return self.snapshot()
