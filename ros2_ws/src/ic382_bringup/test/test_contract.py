import json
from pathlib import Path
import tempfile
import unittest
from ic382_bringup.config import load_nodes
from ic382_bringup.health import has_valid_range, healthy


class ContractTests(unittest.TestCase):
    def load(self, value):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "nodes.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            return load_nodes(path)

    def test_empty_and_valid_manifest(self):
        self.assertEqual(self.load({"nodes": []}), [])
        node = dict(name="mission", package="ic382_mission", executable="mission_node")
        self.assertEqual(self.load({"nodes": [node]}), [node])

    def test_invalid_manifest_rejected(self):
        node = dict(name="mission", package="ic382_mission", executable="mission_node")
        for config in [
            {"nodes": [node, node]}, {"nodes": "bad"}, {"node": []},
            {"nodes": [dict(node, arguments="--bad")]},
            {"nodes": [dict(node, executable="../bad")]},
            {"nodes": [dict(node, enabled="false")]},
            {"nodes": [dict(node, typo=True)]},
        ]:
            with self.subTest(config=config), self.assertRaises(ValueError):
                self.load(config)

    def test_rtx_invalid_returns_do_not_pass(self):
        self.assertFalse(has_valid_range([-1, 0, float("nan"), float("inf"), 700], 1, 600))
        self.assertTrue(has_valid_range([-1, 2.5], 1, 600))

    def test_stopped_clock_and_missing_channels_fail(self):
        counts = dict(clock=5, odom=5, scan=5)
        self.assertTrue(healthy(counts, 0, 10, 3, 1))
        self.assertFalse(healthy(counts, 10, 10, 3, 1))
        self.assertFalse(healthy(dict(counts, scan=0), 0, 10, 3, 1))
        self.assertFalse(healthy(counts, 0, 10, 0, 1))
        self.assertFalse(healthy(counts, 0, 10, 3, 0))

