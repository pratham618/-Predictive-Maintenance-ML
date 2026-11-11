import importlib.util
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from contextlib import closing

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
import services


class FakeModel:
    def predict_proba(self, frame):
        self.seen = frame.copy()
        return np.array([[.2, .8]] * len(frame))


class ServicesTests(unittest.TestCase):
    def test_identity_does_not_change_model_features_or_scores(self):
        model = FakeModel()
        with patch.object(services, "assets", return_value=(model, .7, "test")):
            plain = pd.DataFrame([services.SAMPLE])
            before = services.predict(plain)[0]
            expected = model.seen.copy()
            plain["Machine ID"] = [" 001 "]
            after = services.predict(plain)[0]
            pd.testing.assert_frame_equal(model.seen, expected)
            self.assertEqual(after["probability"], before["probability"])
            self.assertEqual(after["risk"], "High")
            self.assertEqual(after["machine_id"], "001")
            self.assertEqual(list(model.seen.columns), services.FEATURES)
            plain["Machine ID"] = ["bad id"]
            with self.assertRaises(ValueError):
                services.predict(plain)

    def test_legacy_database_save_filter_idempotence_and_demo_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runs.db"
            with closing(sqlite3.connect(path)) as db, db:
                db.execute("CREATE TABLE runs (id TEXT PRIMARY KEY, timestamp TEXT NOT NULL, payload TEXT NOT NULL)")
                db.execute("INSERT INTO runs VALUES (?, ?, ?)", ("legacy", "2020-01-01", json.dumps({"id":"legacy"})))
            with patch.object(services, "DB_PATH", path), patch.object(services, "assets", return_value=(FakeModel(), .7, "test")):
                self.assertIsNone(services.history()[0]["machine_id"])
                frame = pd.DataFrame([{**services.SAMPLE, "Machine ID": "A"}, {**services.SAMPLE, "Machine ID": "B"}])
                runs = services.predict(frame)
                services.save_runs(runs)
                services.save_runs(runs)
                self.assertEqual(len(services.history()), 3)
                self.assertEqual([r["machine_id"] for r in services.history("A")], ["A"])
                self.assertEqual(len(services.history("unknown")), 0)
                demo = services.predict(frame, "Demo")
                with self.assertRaises(ValueError):
                    services.save_runs(demo)
                self.assertEqual(len(services.history()), 3)
                self.assertIn("machine_id", services.export_csv(runs).decode())

    def test_csv_leading_zero_and_sample_exclusion(self):
        from io import BytesIO
        frame = pd.read_csv(BytesIO(b"Machine ID,Type\n001,L\nNA,M\n"), dtype={"Machine ID": str}, keep_default_na=False)
        self.assertEqual(frame["Machine ID"].tolist(), ["001", "NA"])
        import monitoring
        sample = {"machine_id":"A", "source":"Sample"}
        reference = {"machine_id":"B", "source":"Reference CSV"}
        self.assertEqual(monitoring.summarize([sample, reference]), [])


if __name__ == "__main__":
    unittest.main()
