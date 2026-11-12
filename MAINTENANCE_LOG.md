# Maintenance and actual-outcome records

Open **Maintenance & outcomes** in the sidebar. The saved model, prediction
threshold, input preparation and existing machine alerts are unchanged.
Nothing in this workflow retrains the model.

## Work log

Create an Inspection, Maintenance or Failure report item with a case-sensitive
Machine ID, description, optional notes and recorder name. Work can exist before
the first prediction for an asset. An optional linked assessment must be a saved
actual operating assessment from the same machine. Sample, reference, demo and
unassigned assessments cannot be linked.

New work starts Open. Update it to In progress, Completed or Cancelled. Completed
or cancelled work can be reopened with a reason. Every status change appends a
revision; earlier notes are retained. The latest revision determines the state.
Completion records when the status was saved. For retrospective work, include
the actual activity date and evidence in Notes.

Filter by machine or status and export the current table to CSV. Complete work
audit JSON includes notes on all revisions. Completing work or recording a Failure
report does not label a prediction, clear a risk alert or establish repair success.
Run a fresh assessment when appropriate.

## Confirm outcomes

Select a machine and one of its saved actual operating assessments:

- Unverified: unknown, not investigated or evidence withdrawn.
- Failure confirmed: evidence establishes failure at the original assessment.
- No failure confirmed: evidence establishes absence of failure at that assessment.

The label concerns the condition at assessment time. A failure happening later
does not automatically validate a previous prediction; record it in the work log.
The form requires acknowledgement of this scope, evidence/reason and recorder
name. These are operator assertions, not automatically verified sensor labels.
Recorder names are text and are not authenticated identities.

Corrections append revisions and preserve earlier evidence. Unverified withdraws
a label without deleting it. Confirmation time is when the entry was saved;
the run retains its original assessment time. Original probability, risk, model,
inputs and threshold never change. Unlabeled assessments are not assumed healthy.

## Prediction review

Review groups results by saved model version and threshold, with an optional
machine filter. Only the latest outcome revision per run is used. It reports
caught failures, missed failures, false alarms and correct normal snapshots,
confirmed/eligible coverage and the count left unverified.

This is a descriptive comparison on selectively recorded operator evidence.
It is not an independent final test, future forecast horizon, remaining useful
life, calibrated confidence or proof of unseen-data performance. Low coverage,
inconsistent labels, repeated snapshots and selective inspection can bias counts.
No automatic retraining or accuracy claim is made. Export the comparison CSV
and filtered outcome audit JSON for review.

## Storage and compatibility

Both logs use the existing PREDICTION_DB_PATH database. First access creates
outcome_revisions and maintenance_revisions and indexes in the existing migration
transaction. Existing runs and monitoring data are preserved. Foreign keys
protect linked run references.

An increasing sequence orders revisions, including same-timestamp entries.
Existing SQLite transactions serialize writes; exceptions roll back an operation.
The app has no audit deletion or overwrite route. This is not tamper-proof
against direct database edits.

Back up the database before deploying. Reverting application code does not remove
the new tables. The app still has no authentication or external notifications.

## Verification

Run python -m unittest discover -s tests -v and python -m compileall -q app.
Tests cover migration preservation, persistent storage, transaction rollback,
outcome correction/withdrawal, same-time ordering, machine-link checks,
sample/reference rejection, work-state changes, unverified outcomes and UI flows.
