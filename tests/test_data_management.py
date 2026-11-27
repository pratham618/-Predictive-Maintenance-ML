import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
import monitoring
import services


class FakeModel:
    def predict_proba(self, frame):
        return np.array([[.2, .8]] * len(frame))


class DataManagementTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "runs.db"
        self.patches = [
            patch.object(services, "DB_PATH", self.db),
            patch.object(services, "assets", return_value=(FakeModel(), .7, "test")),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in self.patches:
            item.stop()
        self.tmp.cleanup()

    def run_one(self, machine="A"):
        frame = pd.DataFrame([{**services.SAMPLE, "Machine ID": machine}])
        record = services.predict(frame)[0]
        services.save_runs([record])
        return record

    def test_nan_machine_id_is_treated_as_unassigned(self):
        self.assertIsNone(monitoring.machine_id(float("nan")))
        frame = pd.DataFrame([{**services.SAMPLE, "Machine ID": float("nan")}])
        record = services.predict(frame)[0]
        self.assertIsNone(record["machine_id"])
        services.save_runs([record])
        self.assertIsNone(services.history()[0]["machine_id"])

    def test_info_backup_and_clear_history(self):
        first = self.run_one("A")
        second = self.run_one("B")
        services.confirm_outcome(first["id"], "Failure confirmed", "Bearing inspection", "tester")
        services.create_work("A", "Inspection", "Check bearing", "Noise reported", "tester", first["id"])

        info = services.database_info()
        self.assertEqual(info["runs"], 2)
        self.assertEqual(info["outcomes"], 1)
        self.assertEqual(info["work"], 1)
        self.assertEqual(info["machines"], 2)
        self.assertEqual(info["integrity"], "ok")
        self.assertGreater(info["size_bytes"], 0)

        backup = services.backup_database()
        self.assertTrue(backup.exists())
        with closing(sqlite3.connect(backup)) as database:
            self.assertEqual(database.execute("SELECT COUNT(*) FROM runs").fetchone()[0], 2)

        removed = services.clear_history()
        self.assertEqual(removed, 2)
        self.assertEqual(services.history(), [])
        self.assertEqual(services.outcome_history(), [])
        work = services.work_history()
        self.assertEqual(len(work), 1)
        self.assertIsNone(work[0]["run_id"])
        self.assertEqual(services.database_info()["runs"], 0)

    def test_delete_runs_preserves_other_runs_and_work(self):
        first = self.run_one("A")
        second = self.run_one("B")
        services.confirm_outcome(first["id"], "No failure confirmed", "Checked at assessment", "tester")
        services.create_work("A", "Maintenance", "Replace filter", "Routine", "tester", first["id"])

        removed = services.delete_runs([first["id"]])
        self.assertEqual(removed, 1)
        self.assertEqual([row["id"] for row in services.history()], [second["id"]])
        self.assertEqual(services.outcome_history(first["id"]), [])
        work = services.work_history()
        self.assertEqual(len(work), 1)
        self.assertIsNone(work[0]["run_id"])

    def test_reset_workspace_clears_every_table(self):
        record = self.run_one("A")
        services.confirm_outcome(record["id"], "Failure confirmed", "Evidence", "tester")
        services.create_work("A", "Inspection", "Check", "Notes", "tester", record["id"])

        result = services.reset_workspace()
        self.assertEqual(result, {"runs": 1, "outcomes": 1, "work": 1})
        self.assertEqual(services.history(), [])
        self.assertEqual(services.outcome_history(), [])
        self.assertEqual(services.work_history(), [])
        self.assertEqual(services.database_info()["runs"], 0)

    def test_empty_operations_are_safe(self):
        self.assertEqual(services.delete_runs([]), 0)
        self.assertEqual(services.clear_history(), 0)
        self.assertEqual(services.backup_bytes()[:15], b"SQLite format 3")


if __name__ == "__main__":
    unittest.main()
