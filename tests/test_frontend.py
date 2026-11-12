"""Operations-first overview and navigation regressions."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))
import services


def assessment(identity, run_id, probability, source="Manual", hours=0):
    return dict(id=run_id, machine_id=identity,
                timestamp=(datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat(),
                source=source, inputs={**services.SAMPLE, "Temperature difference": 10., "Power [W]": 6283.185},
                probability=probability, risk=services.risk_level(probability, .7),
                threshold=.7, version="test", latency_ms=1., batch_size=1, batch="test")


class FrontendTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "runs.db"

    def test_empty_overview_defaults_to_saved_data_and_all_routes_work(self):
        with patch.dict(os.environ, {"PREDICTION_DB_PATH": str(self.path)}), patch.object(services, "DB_PATH", self.path):
            app = AppTest.from_file(str(APP / "app.py")).run(timeout=60)
            self.assertFalse(app.exception)
            self.assertFalse(app.error)
            self.assertFalse(app.session_state["demo_mode"])
            self.assertEqual([m.value for m in app.metric[:4]], ["0", "0", "0", "0"])
            self.assertTrue(any("No live sensor" in c.value for c in app.caption))
            for slug in ["predict", "history", "maintenance", "datasets", "settings", "performance"]:
                app.switch_page(f"app_pages/{slug}.py").run(timeout=60)
                self.assertFalse(app.exception, slug)
                self.assertFalse(app.error, slug)

    def test_overview_uses_latest_operating_assessments_and_current_work(self):
        with patch.dict(os.environ, {"PREDICTION_DB_PATH": str(self.path)}), patch.object(services, "DB_PATH", self.path):
            app = AppTest.from_file(str(APP / "app.py")).run(timeout=60)
            records = [
                assessment("A", "A-old", .9, hours=1), assessment("A", "A-new", .1),
                assessment("B", "B-new", .8), assessment("S", "sample", .99, source="Sample"),
                assessment("REF", "reference", .99, source="Reference CSV"), assessment(None, "unassigned", .99),
            ]
            services.save_runs(records)
            done = services.create_work("A", "Inspection", "Completed inspection", "", "Tester")
            services.update_work(done["work_id"], "Completed", "Done", "Tester")
            pending = services.create_work("B", "Maintenance", "Check cooling", "", "Tester")
            services.update_work(pending["work_id"], "In progress", "Started", "Tester")
            app.run(timeout=60)
            self.assertFalse(app.exception)
            self.assertFalse(app.error)
            self.assertEqual([m.value for m in app.metric[:4]], ["2", "1", "1", "1"])
            self.assertEqual(set(app.dataframe[0].value["Machine"]), {"A", "B"})
            with patch.object(services, "demo_runs", return_value=[assessment(None, "DEMO-1", .99, source="Demo")]):
                app.toggle(key="demo_mode").set_value(True).run(timeout=60)
            self.assertFalse(app.exception)
            self.assertEqual([m.value for m in app.metric[:4]], ["2", "1", "1", "1"])
            self.assertTrue(any("Reference demo only" in w.value for w in app.warning))

    def test_real_sample_prediction_keeps_provenance_and_details_are_lazy(self):
        with patch.dict(os.environ, {"PREDICTION_DB_PATH": str(self.path)}), patch.object(services, "DB_PATH", self.path):
            app = AppTest.from_file(str(APP / "app.py")).run(timeout=60)
            app.switch_page("app_pages/predict.py").run(timeout=60)
            app.text_input(key="asset_id").set_value("TEST-001")
            with patch.object(services, "explain") as explain:
                next(b for b in app.button if b.label == "Analyze machine  →").click().run(timeout=60)
                self.assertFalse(app.exception)
                self.assertFalse(app.error)
                self.assertEqual(services.history()[0]["source"], "Sample")
                self.assertEqual(services.history()[0]["machine_id"], "TEST-001")
                explain.assert_not_called()
            self.assertTrue(any("Sample / reference" in b.value for b in app.markdown))
            saved = services.history()[0]
            app.session_state[f"details_{saved['id']}"] = True
            explanation = pd.DataFrame({"Feature": ["Tool wear"], "Contribution": [.1], "Effect": ["Raises risk"]})
            with patch.object(services, "explain", return_value=(explanation, 0.)) as explain:
                app.run(timeout=60)
                self.assertFalse(app.exception)
                self.assertFalse(app.error)
                explain.assert_called_once()
            app.switch_page("app_pages/overview.py").run(timeout=60)
            self.assertEqual([m.value for m in app.metric[:4]], ["0", "0", "0", "0"])


if __name__ == "__main__":
    unittest.main()
