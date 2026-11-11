import sys
import unittest
from pathlib import Path
from io import BytesIO
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from streamlit.testing.v1 import AppTest
import services
import views


class MonitoringUITests(unittest.TestCase):
    def test_manual_form_and_batch_form_render(self):
        script = """
import sys
sys.path.insert(0, APP_PATH)
import views
views.api.assets = lambda: (None, .7, "test")
views.prediction()
"""
        app = AppTest.from_string(script.replace("APP_PATH", repr(str(Path(services.__file__).parent))))
        app.run(timeout=30)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.text_input[0].label, "Machine ID (optional)")
        self.assertTrue(app.checkbox[0].value)
        app.segmented_control[0].set_value("CSV batch").run()
        self.assertEqual(len(app.exception), 0)
        self.assertTrue(app.checkbox[0].value)

    def test_upload_preserves_identity_and_validates_it(self):
        import pandas as pd
        for identity in ["001", "NA", ""]:
            data = pd.DataFrame([{**services.SAMPLE, "Machine ID": identity}]).to_csv(index=False).encode()
            upload = SimpleNamespace(size=len(data), getvalue=lambda: data)
            self.assertEqual(views.read_upload(upload)["Machine ID"].iloc[0], identity or None)

    def test_machine_panel_empty_and_populated(self):
        script = """
import sys
sys.path.insert(0, APP_PATH)
import views
records = RECORDS
views.machine_monitor(records)
"""
        asset = {
            "id": "RUN-TEST", "machine_id": "PRESS-001", "timestamp": "2026-11-11T10:00:00+05:30",
            "source": "Manual", "batch": "test", "inputs": {**services.SAMPLE, "Temperature difference":10., "Power [W]":6283.},
            "probability": .8, "risk":"High", "threshold":.7, "version":"test",
            "latency_ms":1., "batch_size":1
        }
        for records in [[], [asset]]:
            app = AppTest.from_string(script.replace("APP_PATH", repr(str(Path(services.__file__).parent))).replace("RECORDS", repr(records)))
            app.run(timeout=30)
            self.assertEqual(len(app.exception), 0)
            if records:
                self.assertEqual(app.selectbox[0].value, "PRESS-001")
                self.assertTrue(any("High risk" in item.value for item in app.warning))
            else:
                self.assertEqual(len(app.info), 1)


if __name__ == "__main__":
    unittest.main()
