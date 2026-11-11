import json
import sqlite3
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from contextlib import closing

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
import monitoring


def record(identity="A", p=.2, stamp="2026-11-11T10:00:00+00:00", **extra):
    return dict(id=stamp, machine_id=identity, probability=p, timestamp=stamp,
                version="v1", threshold=.7, source="Manual", **extra)


class MonitoringTests(unittest.TestCase):
    def test_identity_is_stable_and_case_sensitive(self):
        self.assertEqual(monitoring.machine_id(" 001-A "), "001-A")
        self.assertNotEqual(monitoring.machine_id("a"), monitoring.machine_id("A"))
        self.assertIsNone(monitoring.machine_id(""))
        for invalid in ["a b", "<script>", "a"*65, 123]:
            with self.assertRaises(ValueError):
                monitoring.machine_id(invalid)

    def test_migration_preserves_original_rows_and_is_repeatable(self):
        with closing(sqlite3.connect(":memory:")) as db, db:
            db.execute("CREATE TABLE runs (id TEXT PRIMARY KEY, timestamp TEXT NOT NULL, payload TEXT NOT NULL)")
            payload = json.dumps({"inputs": {"Type": "L"}, "probability": .6})
            db.execute("INSERT INTO runs VALUES ('old', 'old-time', ?)", (payload,))
            monitoring.migrate(db)
            monitoring.migrate(db)
            self.assertEqual(db.execute("SELECT * FROM runs").fetchone(), ("old", "old-time", payload, None))
            db.execute("INSERT INTO runs VALUES ('new', 'new-time', '{}', 'A')")
            self.assertEqual(db.execute("SELECT count(*) FROM runs").fetchone()[0], 2)

    def test_latest_per_machine_clears_old_high_risk(self):
        rows = [record(p=.9, stamp="2026-11-11T09:00:00Z"), record(p=.1), record("B", .8)]
        result = monitoring.summarize(rows, datetime(2026,11,11,11,tzinfo=timezone.utc))
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["alerts"], [])
        self.assertTrue(result[1]["alerts"][0].startswith("High risk"))

    def test_offsets_and_trend_boundaries(self):
        rows = [record(p=.4, stamp="2026-11-11T14:00:00+05:30"), record(p=.7)]
        summary = monitoring.summarize(rows, datetime(2026,11,11,11,tzinfo=timezone.utc))[0]
        self.assertAlmostEqual(summary["delta"], .3)
        self.assertEqual(len(summary["alerts"]), 2)

    def test_no_cross_model_threshold_or_same_time_trend(self):
        for change in [{"version":"v2"}, {"threshold":.6}, {"timestamp":"2026-11-11T10:00:00Z"}]:
            old = record(p=.1, stamp="2026-11-11T09:00:00Z")
            old.update(change)
            summary = monitoring.summarize([old, record(p=.9)])[0]
            self.assertIsNone(summary["delta"])

    def test_demo_unassigned_and_stale(self):
        demo = record("D")
        demo["source"] = "Demo"
        rows = [demo, record(None), record()]
        result = monitoring.summarize(rows, datetime(2026,11,12,11,tzinfo=timezone.utc))
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0]["stale"])
        exact = monitoring.summarize([record()], datetime(2026,11,12,10,tzinfo=timezone.utc))[0]
        self.assertFalse(exact["stale"])


if __name__ == "__main__":
    unittest.main()
