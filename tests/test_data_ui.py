"""UI checks for the settings data-management and history cleanup controls."""
from datetime import datetime, timezone
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))
import services


def assessment(identity, run_id):
    return dict(id=run_id, machine_id=identity, timestamp=datetime.now(timezone.utc).isoformat(),
                source="Manual", inputs={**services.SAMPLE, "Temperature difference": 10., "Power [W]": 6283.185},
                probability=.8, risk="High", threshold=.7, version="test", latency_ms=1.,
                batch_size=1, batch="test")


class DataManagementUITests(unittest.TestCase):
    def test_settings_clear_history_requires_confirmation_and_backs_up(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runs.db"
            with patch.dict(os.environ, {"PREDICTION_DB_PATH": str(path)}), \
                    patch.object(services, "DB_PATH", path):
                services.save_runs([assessment("A", "RUN-A"), assessment("B", "RUN-B")])
                app = AppTest.from_file(str(APP / "app.py")).run(timeout=60)
                app.switch_page("app_pages/settings.py").run(timeout=60)
                self.assertFalse(app.exception)
                self.assertFalse(app.error)

                button = next(item for item in app.button if item.key == "clear_history_button")
                self.assertTrue(button.disabled)
                self.assertEqual(len(services.history()), 2)

                next(item for item in app.text_input if item.key == "clear_history_confirm").set_value("CLEAR HISTORY")
                app.run(timeout=60)
                next(item for item in app.button if item.key == "clear_history_button").click().run(timeout=60)
                self.assertFalse(app.exception)
                self.assertFalse(app.error)
                self.assertEqual(services.history(), [])
                self.assertTrue(any("Cleared 2" in item.value for item in app.success))
                self.assertTrue(any((path.parent / "backups").glob("prediction_runs-*.sqlite3")))


if __name__ == "__main__":
    unittest.main()
