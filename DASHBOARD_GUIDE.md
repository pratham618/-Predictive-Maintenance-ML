# Prediction Model — dashboard guide

## Design rationale

The interface uses a near-black #0B0D12 canvas, #12151C cards, and #1A1E27 controls to create depth without visual noise. Electric cyan #61D9EF highlights the primary action and key data. Muted violet provides a secondary accent; green, amber, and red always accompany written risk labels.

Inter handles interface text; JetBrains Mono distinguishes metrics and machine values. The sidebar separates daily work from model/data management. A compact top bar provides workspace search, alerts, and the local operator menu. Most actions are one or two clicks away. CSS tokens centralize colors, spacing, corners, and typography. Hover/focus transitions last 180 ms and respect reduced-motion preferences. Charts and input controls retain accessible names and keyboard support.

## Working screens

| Screen | Implemented behavior |
| --- | --- |
| Overview | Validation accuracy, measured single-run latency, run count, explicit drift-monitor status, probability timeline, model record, selectable recent activity. A labeled demo feed makes the charts explorable without creating fake history. |
| Run prediction | Six validated machine inputs, sample loading, real XGBoost inference, risk gauge, recommendations, derived power/temperature metrics, exact TreeSHAP feature contributions, CSV/PDF exports. |
| CSV batch | Drag-and-drop upload, downloadable template, row validation, batch inference, selectable results, CSV/PDF exports. Up to 5,000 rows and 10 MB. |
| History | Persistent local SQLite history, risk/source filters, text search, sortable table, row inspection, reuse inputs, exports following the current filters. |
| Model performance | Reproduced validation metrics, confusion matrix, precision-recall curve, global feature importance, artifact version, known metadata limits. |
| Datasets | Reference dataset and session CSV uploads, data-quality counts, search/type filters, sortable preview, filtered export, hand-off to batch inference. |
| Settings | Light appearance toggle, session operator name, notification preference, inference configuration and shortcut reference. |

## Reusable components and source layout

- `app/app.py`: application shell, six-page routing, sidebar, command palette, alerts and operator menu.
- `app/app_pages/`: small page entry points.
- `app/views.py`: the screen layouts and user workflows.
- `app/ui.py`: brand/icons, page headers, section headers, key-value lists, empty states, notes, chart styling, feature chart, probability gauge and run table.
- `app/styles.css`: design tokens, dark/light styling, focus states, reduced motion and responsive layout rules.
- `app/services.py`: model loading, validation, feature engineering, prediction, TreeSHAP, validation metrics, demo feed and history persistence.
- `app/reports.py`: paginated PDF reports.
- `.streamlit/config.toml`: dark native theme and upload settings.
- `requirements-dashboard.txt`: tested dependency versions.

## Start locally

From `C:\Users\prath\OneDrive\Desktop\Predictive_Maintenance_Project`:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app/app.py
```

Open the local URL printed by Streamlit, normally http://localhost:8501. The existing virtual environment now includes ReportLab for PDF export. To restore the dashboard dependencies in another environment:

```powershell
python -m pip install -r requirements-dashboard.txt
```

Model and dataset paths are resolved from the project directory, independently of where the command is launched. Launch from the project root to load the theme configuration as well.

## Model connection / API boundary

The real model is already connected. `services.predict(frame, source)` accepts the six input columns and returns a list of JSON-serializable records. The UI calls this boundary from one place, `views._run()`.

To connect an external model API later, replace the body of `services.predict()` with an authenticated request to your endpoint, retaining server-side validation and this response contract:

```json
{
  "id": "RUN-unique-id",
  "timestamp": "2026-10-14T00:00:00+05:30",
  "source": "Manual",
  "batch": "batch-id",
  "inputs": {
    "Type": "L",
    "Air temperature [K]": 298.0,
    "Process temperature [K]": 308.0,
    "Rotational speed [rpm]": 1500,
    "Torque [Nm]": 40.0,
    "Tool wear [min]": 100,
    "Temperature difference": 10.0,
    "Power [W]": 6283.185307
  },
  "probability": 0.0007755,
  "risk": "Low",
  "threshold": 0.7,
  "version": "artifact-hash",
  "latency_ms": 6.0,
  "batch_size": 1
}
```

Use deployment secrets for credentials. Point `assets()`, `metrics()`, `importance()` and `explain()` at matching versioned API metadata/explanation endpoints when moving the model off this computer; do not mix a remote predictor with explanations from a different local artifact.

## Data meaning and limits

- The working saved pipeline, feature names, formulas and 70% failure threshold remain the source of truth.
- Low risk is below 35%; Medium is 35% to below 70%; High is at least 70%. Medium is a UI monitoring convention.
- Failure probability is not a separately calibrated confidence score.
- Validation reproduces the notebook's 80/20 stratified split, random state 42. The same split was used to tune the threshold, so the displayed 98.75% accuracy is not an independent final-test result.
- Demo scores are real model outputs on reference samples. Demo IDs and timestamps are illustrative, clearly labeled, and never inserted into History.
- Training date, calibration metadata and drift monitoring are not recorded/configured. The interface says so explicitly.
- Inference duration is measured around the prediction call. For a batch it refers to the whole batch, not each row.
- History lives at `data/prediction_runs.sqlite3`. Appearance and profile preferences are browser-session settings. Uploaded datasets remain in the session unless their predictions are saved.
- CSV exports include all filtered runs and inputs. PDF exports include up to 200 filtered runs, with this limit indicated on the button.
- This is a working local application. Multi-user deployment would additionally require authentication, shared storage and operational monitoring.

## Shortcuts

- Ctrl/Cmd + K: command palette.
- Ctrl/Cmd + Shift + P: Run prediction.
- Esc: close dialog.
- Tab/Shift+Tab: move through interactive controls.

## Verification

All six screens were tested with Streamlit AppTest. Real single and batch predictions, input rejection, threshold boundaries, persistent history, filtering, appearance changes and exports were exercised. Exact TreeSHAP contributions were checked against the model probability. PDF output was rendered and reviewed. Browser checks cover the actual rendered interface; this is not a formal WCAG conformance audit.

Backups: the original app remains in `app/app.py.bak`, and the preceding light dashboard is in `app/app.light-dashboard.py.bak`.
## Machine monitoring update

See [MACHINE_MONITORING.md](MACHINE_MONITORING.md) for asset IDs, timestamped
history, risk trends, alerts, sample-data declarations and SQLite migration.

