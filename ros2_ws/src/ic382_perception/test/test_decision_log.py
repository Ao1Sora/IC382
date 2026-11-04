import json
import tempfile
import unittest
from pathlib import Path

from ic382_perception.decision_log import (
    SpecDecisionLog,
    write_entry,
    write_json_atomic,
)


class DecisionLogTests(unittest.TestCase):
    def test_spec_document_shape(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "decision_log.json"
            log = SpecDecisionLog(path)
            log.begin_desk("T02")
            log.update_desk_status("T02", "ELIGIBLE")
            log.record_round1("T02", 1, "C", 0.92, timestamp="14:31:05")
            log.record_round2("T02", 1, "CONFIRMED_ABANDONED", "TAGGED_CLASS_C")
            log.record_anomaly("T02", "bottle", 0.4, "low_confidence")
            document = log.finish()

            on_disk = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(on_disk, document)
            self.assertIn("mission_timestamp", on_disk)
            record = on_disk["desk_records"][0]
            self.assertEqual(record["desk_id"], "T02")
            self.assertEqual(record["desk_status"], "ELIGIBLE")
            self.assertEqual(record["round_1_seen"][0]["class"],
                             "Class_C_Disposables")
            self.assertEqual(record["round_1_seen"][0]["confidence"], 0.92)
            self.assertEqual(record["round_2_validation"][0]["status"],
                             "CONFIRMED_ABANDONED")
            self.assertEqual(record["anomalous_items"][0]["reason"],
                             "low_confidence")

    def test_atomic_writer_replaces_existing_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "nested" / "log.json"
            write_json_atomic(path, {"a": 1})
            write_json_atomic(path, {"a": 2})
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"a": 2})
            self.assertEqual(list(path.parent.glob("*.tmp")), [])

    def test_jsonl_writer_keeps_legacy_format(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "audit.jsonl"
            write_entry(path, {"event": "one"})
            write_entry(path, {"event": "two"})
            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertEqual([json.loads(line)["event"] for line in lines],
                             ["one", "two"])


if __name__ == "__main__":
    unittest.main()
