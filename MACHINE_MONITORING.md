# Machine monitoring

Run the dashboard as before: install requirements-dashboard.txt and run
`streamlit run app/app.py`. Open **History** for machine monitoring.

## Asset identity and history

Enter an optional **Machine ID** on the manual form or supply a **Machine ID**
CSV column. Use your existing asset identifier consistently, for example
`PRESS-001`. IDs are case-sensitive text, trimmed, 1–64 characters, using
letters, digits, dots, underscores, colons and hyphens. Leading zeroes are
preserved in CSV imports. Blank IDs remain unassigned. Machine type, run ID,
AI4I Product ID and dataset row numbers are never treated as asset identities.
Reusing a saved run keeps its machine ID.

Every analysis records its assessment timestamp, model version, threshold,
inputs and probability. The timestamp is the time of inference, not the
sensor acquisition time. Repeated IDs append snapshots; they do not overwrite
previous results. Machine IDs are metadata and never enter model features.
The saved model, feature engineering, risk bands and decision threshold
remain unchanged.

The machine selector shows history, a probability timeline and CSV/PDF exports.
The run log still includes all records; search also matches machine IDs.
Charts separate model versions and thresholds to avoid misleading comparisons.

## Alerts and trends

Alerts describe the latest saved assessment for each assigned machine:

- High risk: probability at or above that run's saved threshold; arrange
  prompt inspection under site procedures.
- Watch: probability at least half the threshold; increase condition checks.
- Rising: increase of at least 0.10 (10 percentage points) from the previous
  distinct assessment time using the same model version and threshold.
- Stale: latest assessment is more than 24 hours old. This is a workspace
  convention, not a maintenance interval inferred by the model.

One snapshot has no trend. Same-time batch rows do not establish a trend;
ties choose the lexically greatest run ID deterministically. A subsequent
low-risk snapshot clears an earlier high-risk alert. Stale results keep
their risk warning with the stale warning shown alongside it.
Alerts are computed on page refresh and do not send notifications externally.
They are advisory model estimates, not confirmed failures or calibrated
confidence. The Settings notification toggle controls the Alerts popover.

## Data provenance

There is no live sensor connection. The overview demo uses synthetic AI4I
reference samples with illustrative times and is explicitly labeled. Demo
records cannot be saved through save_runs and are excluded from machine
monitoring. Sample scenarios and uploaded reference rows remain reference
data even if you choose to analyze and save them. The manual form and CSV
batch default to a sample/reference declaration; clear it only for actual
asset readings. Sample and Reference CSV sources are excluded from machine
monitoring, while remaining visible in the run log. Only assign an asset ID
when the readings actually belong to that asset. Unassigned records do not
generate machine alerts.

## Existing SQLite databases

The first database access automatically adds a nullable machine_id column
and an index to runs in a transaction. Migration is idempotent, preserves
original payloads and timestamps, and leaves all old rows unassigned.
No machine IDs or historical observation times are fabricated. Existing
three-column inserts were replaced with explicit column lists. Duplicate
run IDs remain idempotent. Back up the local database before deployment.
Use PREDICTION_DB_PATH to select a database (set before starting the app).

## Verification

Run `python -m unittest discover -s tests -v`. Tests cover migration,
asset separation, identity validation, persistence, demo rejection,
trend rules, staleness and unchanged prediction features/probabilities.
