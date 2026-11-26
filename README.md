# Predictive Maintenance Dashboard

A Streamlit dashboard that uses XGBoost to estimate machine failure risk from temperature, rotational speed, torque, tool wear, and machine type.

## Demo walkthrough

1. Open **Run prediction** and load a sample to see its risk score and feature contributions.
2. Open **History** to review saved assessments and risk trends by machine ID.
3. Open **Maintenance & outcomes** to log an inspection and record what the operator found.
4. Open **Model performance** to review caught failures, missed failures, and false alarms.

## Validation results

At the saved 0.70 threshold, the model caught 58 of 68 failures and raised 15 false alarms across 2,000 validation rows. Failure recall was 85.29% and precision was 79.45%. The synthetic validation split was also used to select the threshold. Independent evaluation with real machine data is pending.

## Run locally

With Python 3.14, run these commands from the repository root.

```sh
python -m pip install -r requirements.txt
python -m streamlit run app/app.py
```

The app accepts manual inputs and CSV uploads. Use synthetic samples for a shared demo because assessment and maintenance records are stored in the app's SQLite database. See the [dashboard guide](DASHBOARD_GUIDE.md) for details.
