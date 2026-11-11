# Evaluation improvements

Model performance now reports caught failures, missed failures, false alarms,
an always-normal baseline, average precision, and approximate 95% Wilson intervals
for precision and recall. The threshold explorer is read-only: it never writes
model artifacts or adds validation rows to prediction history.

## Current evidence

The original notebook used a stratified 80/20 split with random state 42.
Its 2,000 validation rows were also used for model comparison and threshold
selection. At the saved 0.70 threshold, replay yields:

| Outcome | Count |
|---|---:|
| Caught failures | 58 |
| Missed failures | 10 |
| False alarms | 15 |
| Correct normal predictions | 1,917 |

Recall is 85.29%; precision is 79.45%; accuracy is 98.75%.
Always predicting no failure gives 96.60% accuracy but zero failure recall.
Intervals reflect finite sample counts, not selection bias or deployment uncertainty.

## Independent evaluation status

No independently held-out final test is available for the existing model.
Repartitioning this already-explored dataset does not create new external evidence.
Future experiments should fit preprocessing and the model only on training data,
select the threshold on separate validation data, then freeze both before final
evaluation. Do not repeatedly tune against the final split. Collect new labeled
operating data for external evaluation; use machine/time separation when appropriate.
The source dataset is synthetic, and current run history lacks actual outcome labels.

## Files and checks

- `app/evaluation.py`: pure count, interval, threshold-table and outcome helpers.
- `app/services.py`: cached row-level replay of the original validation split.
- `app/views.py`: evaluation panel, read-only preview and CSV/JSON downloads.
- `tests/test_evaluation.py`: boundary, undefined-precision, invalid-input and immutability checks.

Run tests with the project virtual environment:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

Row identifiers in evaluation exports refer to CSV line numbers, not physical machines.
Machine IDs and longitudinal risk tracking are a separate next improvement.
