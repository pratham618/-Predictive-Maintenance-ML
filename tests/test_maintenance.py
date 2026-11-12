from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
import maintenance
import monitoring
import services


def run(identity="A", run_id="R1", probability=.8, source="Manual", threshold=.7, version="v1"):
    return dict(id=run_id, machine_id=identity, source=source, probability=probability,
                threshold=threshold, version=version, timestamp="2026-11-10T10:00:00+05:30",
                inputs={"Type":"L"})


class MaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        self.db.execute("PRAGMA foreign_keys = ON")
        monitoring.migrate(self.db)
        maintenance.migrate(self.db)
        self.record = run()
        for record in [self.record, run("B", "R2"), run("A", "SAMPLE", source="Sample"), run(None, "UNASSIGNED")]:
            self.db.execute("INSERT INTO runs(id,timestamp,payload,machine_id) VALUES (?,?,?,?)",
                            (record["id"], record["timestamp"], json.dumps(record), record["machine_id"]))

    def test_migration_preserves_predictions_and_is_repeatable(self):
        before = self.db.execute("SELECT * FROM runs").fetchall()
        maintenance.migrate(self.db)
        maintenance.migrate(self.db)
        self.assertEqual(self.db.execute("SELECT * FROM runs").fetchall(), before)
        self.assertEqual(maintenance.work_history(self.db), [])
        self.assertEqual(maintenance.outcome_history(self.db), [])

    def test_outcome_corrections_preserve_evidence_and_prediction(self):
        before = self.db.execute("SELECT payload FROM runs WHERE id='R1'").fetchone()
        maintenance.confirm_outcome(self.db, "R1", "Failure confirmed", "Inspection report 12", "Operator")
        maintenance.confirm_outcome(self.db, "R1", "No failure confirmed", "Corrected report 12", "Reviewer")
        audit = maintenance.outcome_history(self.db, "R1")
        self.assertEqual(len(audit), 2)
        self.assertEqual(audit[0]["outcome"], "No failure confirmed")
        self.assertEqual(audit[1]["notes"], "Inspection report 12")
        self.assertEqual(self.db.execute("SELECT payload FROM runs WHERE id='R1'").fetchone(), before)
        maintenance.confirm_outcome(self.db, "R1", "Unverified", "Evidence withdrawn", "Reviewer")
        counts, _ = maintenance.review([self.record], maintenance.outcome_history(self.db))
        self.assertEqual(counts["unverified"], 1)
        self.assertEqual(counts["confirmed"], 0)

    def test_outcomes_reject_unknown_sample_unassigned_and_empty_evidence(self):
        for identity in ["missing", "SAMPLE", "UNASSIGNED"]:
            with self.assertRaises(ValueError):
                maintenance.confirm_outcome(self.db, identity, "Failure confirmed", "evidence", "Operator")
        for outcome, note, operator in [
            ("Healthy", "evidence", "Operator"), ("Failure confirmed", "", "Operator"),
            ("Failure confirmed", "evidence", ""), ("Failure confirmed", "x"*2001, "Operator")
        ]:
            with self.assertRaises(ValueError):
                maintenance.confirm_outcome(self.db, "R1", outcome, note, operator)
        self.assertEqual(maintenance.outcome_history(self.db), [])

    def test_work_lifecycle_keeps_revisions_and_does_not_label_outcome(self):
        work = maintenance.create_work(self.db, "A", "Inspection", "Check cooling", "Alert follow-up", "Operator", "R1")
        maintenance.update_work(self.db, work["work_id"], "In progress", "Started inspection", "Operator")
        completed = maintenance.update_work(self.db, work["work_id"], "Completed", "Inspection complete", "Operator")
        self.assertIsNotNone(completed["completed_at"])
        reopened = maintenance.update_work(self.db, work["work_id"], "Open", "Further check needed", "Reviewer")
        self.assertIsNone(reopened["completed_at"])
        history = maintenance.work_history(self.db, work["work_id"])
        self.assertEqual([w["status"] for w in history], ["Open", "Completed", "In progress", "Open"])
        self.assertEqual(len(maintenance.latest(history, "work_id")), 1)
        self.assertEqual(maintenance.outcome_history(self.db), [])

    def test_work_links_and_status_inputs_are_validated(self):
        for identity, linked in [("A","R2"), ("A","SAMPLE"), ("A","UNASSIGNED"), ("A","missing"), ("","R1")]:
            with self.assertRaises(ValueError):
                maintenance.create_work(self.db, identity, "Inspection", "Inspect", "", "Operator", linked)
        work = maintenance.create_work(self.db, "NEW-001", "Maintenance", "Scheduled service", "", "Operator")
        self.assertIsNone(work["run_id"])
        for key, status, notes, operator in [
            ("missing", "Completed", "Done", "Operator"), (work["work_id"], "Unknown", "Done", "Operator"),
            (work["work_id"], "Open", "No change", "Operator"), (work["work_id"], "Completed", "", "Operator"),
            (work["work_id"], "Completed", "Done", "")
        ]:
            with self.assertRaises(ValueError):
                maintenance.update_work(self.db, key, status, notes, operator)
        maintenance.update_work(self.db, work["work_id"], "Cancelled", "Work no longer required", "Operator")
        self.assertEqual(maintenance.work_history(self.db)[0]["status"], "Cancelled")

    def test_review_counts_latest_labels_threshold_boundaries_and_unknowns(self):
        records = [run(run_id="caught", probability=.7), run(run_id="missed", probability=.2),
                   run(run_id="false", probability=.8), run(run_id="normal", probability=.1),
                   run(run_id="unknown"), run(run_id="sample", source="Sample"), run(None, "blank")]
        revisions = [
            {"run_id":"caught","outcome":"Failure confirmed"},
            {"run_id":"caught","outcome":"No failure confirmed"},
            {"run_id":"missed","outcome":"Failure confirmed"},
            {"run_id":"false","outcome":"No failure confirmed"},
            {"run_id":"normal","outcome":"No failure confirmed"},
        ]
        counts, details = maintenance.review(records, revisions)
        self.assertEqual(counts, dict(caught=1, missed=1, false_alarms=1, correct_normal=1,
                                      unverified=1, confirmed=4, eligible=5))
        self.assertEqual(len(details), 5)

    def test_timestamp_ties_use_revision_sequence(self):
        with patch.object(maintenance, "stamp", return_value="2026-11-12T10:00:00Z"):
            maintenance.confirm_outcome(self.db, "R1", "Failure confirmed", "First evidence", "Operator")
            maintenance.confirm_outcome(self.db, "R1", "Unverified", "Withdrawal", "Operator")
        self.assertEqual(maintenance.latest(maintenance.outcome_history(self.db), "run_id")[0]["outcome"], "Unverified")


class MaintenancePersistenceTests(unittest.TestCase):
    def test_existing_database_transaction_rollback_and_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runs.db"
            record = run()
            with closing(sqlite3.connect(path)) as db, db:
                db.execute("CREATE TABLE runs(id TEXT PRIMARY KEY,timestamp TEXT NOT NULL,payload TEXT NOT NULL)")
                db.execute("INSERT INTO runs VALUES(?,?,?)", ("legacy", record["timestamp"], json.dumps(run(None, "legacy"))))
            with patch.object(services, "DB_PATH", path):
                self.assertEqual(len(services.history()), 1)
                services.save_runs([record])
                job = services.create_work("A", "Inspection", "Inspect torque", "", "Operator", "R1")
                services.confirm_outcome("R1", "Failure confirmed", "Inspection evidence", "Operator")
                with self.assertRaises(RuntimeError):
                    with services._connection() as db:
                        maintenance.update_work(db, job["work_id"], "Completed", "Done", "Operator")
                        raise RuntimeError("cancel transaction")
                self.assertEqual(services.work_history()[0]["status"], "Open")
                services.update_work(job["work_id"], "Completed", "Checked", "Operator")
                self.assertEqual(len(services.work_history()), 2)
                self.assertEqual(len(services.outcome_history()), 1)
                self.assertEqual(len(services.history()), 2)


if __name__ == "__main__":
    unittest.main()
