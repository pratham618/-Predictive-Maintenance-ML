from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from streamlit.testing.v1 import AppTest
import services
from test_maintenance import run


def element(app, kind, label):
    return next(widget for widget in getattr(app, kind) if widget.label == label)


class MaintenanceUITests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "runs.db"

    def app(self):
        script = """
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, APP_PATH)
import maintenance_views
import services
with patch.object(services, "DB_PATH", Path(DATABASE_LITERAL)):
    maintenance_views.page()
"""
        return AppTest.from_string(script.replace("APP_PATH", repr(str(Path(services.__file__).parent))).replace("DATABASE_LITERAL", repr(str(self.path))))

    def seed(self):
        with patch.object(services, "DB_PATH", self.path):
            services.save_runs([run(), run("B", "R2", .2), run("A", "SAMPLE", source="Sample")])

    def test_empty_sections_and_create_work(self):
        app = self.app().run(timeout=30)
        self.assertFalse(app.exception)
        app.segmented_control[0].set_value("Confirm outcomes").run()
        self.assertFalse(app.exception)
        self.assertTrue(any("No eligible" in c.value for c in app.caption))
        app.segmented_control[0].set_value("Prediction review").run()
        self.assertTrue(any("No assigned" in c.value for c in app.info))
        app.segmented_control[0].set_value("Work log").run()
        app.text_input(key="work_machine").set_value("NEW-001").run()
        element(app, "text_input", "Work description").set_value("Inspect cooling system")
        element(app, "button", "Save work item").click().run()
        self.assertFalse(app.exception)
        with patch.object(services, "DB_PATH", self.path):
            self.assertEqual(services.work_history()[0]["machine_id"], "NEW-001")

    def test_outcome_acknowledgement_corrections_and_review(self):
        self.seed()
        app = self.app().run(timeout=30)
        app.segmented_control[0].set_value("Confirm outcomes").run()
        self.assertFalse(app.exception)
        self.assertEqual(len(element(app, "selectbox", "Assessment").options), 1)
        element(app, "selectbox", "Verified condition at assessment").set_value("Failure confirmed")
        element(app, "text_area", "Evidence or correction reason").set_value("Inspection confirms failure at assessment")
        element(app, "button", "Save outcome").click().run()
        self.assertTrue(any("Confirm that" in e.value for e in app.error))
        app.checkbox[0].check()
        element(app, "button", "Save outcome").click().run()
        self.assertFalse(app.exception)
        with patch.object(services, "DB_PATH", self.path):
            self.assertEqual(len(services.outcome_history()), 1)
        element(app, "selectbox", "Verified condition at assessment").set_value("Unverified")
        element(app, "text_area", "Evidence or correction reason").set_value("Inspection belongs to another date")
        element(app, "button", "Save outcome").click().run()
        self.assertFalse(app.exception)
        with patch.object(services, "DB_PATH", self.path):
            self.assertEqual(len(services.outcome_history()), 2)
        app.segmented_control[0].set_value("Prediction review").run()
        self.assertFalse(app.exception)
        self.assertTrue(any("0 confirmed of 2" in c.value for c in app.caption))

    def test_status_update_keeps_completed_work_and_audit(self):
        self.seed()
        with patch.object(services, "DB_PATH", self.path):
            services.create_work("A", "Inspection", "Review high risk", "", "Operator", "R1")
        app = self.app().run(timeout=30)
        element(app, "selectbox", "New status").set_value("Completed")
        element(app, "text_area", "Update reason").set_value("Inspection report filed")
        element(app, "button", "Save status update").click().run()
        self.assertFalse(app.exception)
        with patch.object(services, "DB_PATH", self.path):
            self.assertEqual(services.work_history()[0]["status"], "Completed")
            self.assertEqual(len(services.work_history()), 2)
            self.assertEqual(services.outcome_history(), [])
        self.assertEqual(app.metric[1].value, "1")


if __name__ == "__main__":
    unittest.main()
