"""Model boundary: UI calls these functions; replace predict() to use a remote API.

The original pipeline, feature names, units and 0.70 saved threshold are preserved.
Demo telemetry never enters the local SQLite run history.
"""
from pathlib import Path
from datetime import datetime, timedelta, timezone
from time import perf_counter
import hashlib
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager

import joblib
import numpy as np
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = Path(os.environ.get("PREDICTION_DB_PATH", str(ROOT / "data" / "prediction_runs.sqlite3")))
INPUTS = ["Type", "Air temperature [K]", "Process temperature [K]", "Rotational speed [rpm]", "Torque [Nm]", "Tool wear [min]"]
FEATURES = INPUTS + ["Temperature difference", "Power [W]"]
RANGES = {"Air temperature [K]": (250, 350), "Process temperature [K]": (250, 400), "Rotational speed [rpm]": (0, 5000), "Torque [Nm]": (0, 150), "Tool wear [min]": (0, 500)}
SAMPLE = {"Type": "L", "Air temperature [K]": 298.0, "Process temperature [K]": 308.0, "Rotational speed [rpm]": 1500, "Torque [Nm]": 40.0, "Tool wear [min]": 100}
IST = timezone(timedelta(hours=5, minutes=30))


@st.cache_resource
def _load_assets(model_stamp, threshold_stamp):
    path = ROOT / "models/xgboost_model.pkl"
    model = joblib.load(path)
    threshold = float(joblib.load(ROOT / "models/xgboost_threshold.pkl"))
    if not 0 < threshold <= 1:
        raise ValueError("Saved threshold must be greater than 0 and at most 1.")
    version = hashlib.sha256(path.read_bytes()).hexdigest()[:8]
    return model, threshold, version


def assets():
    return _load_assets((ROOT / "models/xgboost_model.pkl").stat().st_mtime_ns,
                        (ROOT / "models/xgboost_threshold.pkl").stat().st_mtime_ns)


def prepare(frame):
    """Validate every input before inference, including uploaded CSVs."""
    if frame.empty:
        raise ValueError("The file has no data rows. Add at least one machine snapshot.")
    if len(frame) > 5000:
        raise ValueError("Use a maximum of 5,000 rows per batch.")
    if frame.columns.duplicated().any():
        raise ValueError("Column names must be unique.")
    missing = [column for column in INPUTS if column not in frame]
    if missing:
        raise ValueError("Missing columns: " + ", ".join(missing))
    data = frame[INPUTS].copy().reset_index(drop=True)
    data["Type"] = data["Type"].astype(str).str.strip().str.upper()
    if not data["Type"].isin(["L", "M", "H"]).all():
        raise ValueError("Machine Type must be L, M, or H on every row.")
    for column, (low, high) in RANGES.items():
        data[column] = pd.to_numeric(data[column], errors="coerce")
        invalid = ~np.isfinite(data[column]) | ~data[column].between(low, high)
        if invalid.any():
            rows = ", ".join(str(int(i) + 2) for i in data.index[invalid][:5])
            raise ValueError(f"{column}: use a finite number from {low} to {high}. Check CSV line(s) {rows}.")
    for column in ["Rotational speed [rpm]", "Tool wear [min]"]:
        if (data[column] % 1 != 0).any():
            raise ValueError(f"{column} must contain whole numbers.")
    data["Temperature difference"] = data["Process temperature [K]"] - data["Air temperature [K]"]
    data["Power [W]"] = data["Torque [Nm]"] * 2 * np.pi * data["Rotational speed [rpm]"] / 60
    return data[FEATURES]


def risk_level(probability, threshold):
    return "High" if probability >= threshold else "Medium" if probability >= threshold / 2 else "Low"


def predict(frame, source="Manual"):
    """API adapter. Returns serializable records ready for the UI or a REST response."""
    data = prepare(frame)
    model, threshold, version = assets()
    started = perf_counter()
    probabilities = model.predict_proba(data)[:, 1]
    elapsed_ms = (perf_counter() - started) * 1000
    if not np.isfinite(probabilities).all() or ((probabilities < 0) | (probabilities > 1)).any():
        raise ValueError("The model returned invalid probabilities.")
    stamp = datetime.now(IST).isoformat()
    batch = uuid.uuid4().hex[:8]
    return [{"id": f"RUN-{uuid.uuid4().hex[:8].upper()}", "timestamp": stamp,
             "source": source, "batch": batch, "inputs": row,
             "probability": float(probability), "risk": risk_level(float(probability), threshold),
             "threshold": threshold, "version": version, "latency_ms": elapsed_ms,
             "batch_size": len(data)}
            for row, probability in zip(data.to_dict("records"), probabilities)]


@contextmanager
def _connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=15)
    try:
        with connection:
            connection.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, timestamp TEXT NOT NULL, payload TEXT NOT NULL)")
            yield connection
    finally:
        connection.close()


def save_runs(records):
    with _connection() as connection:
        connection.executemany("INSERT OR IGNORE INTO runs VALUES (?, ?, ?)",
                               [(r["id"], r["timestamp"], json.dumps(r)) for r in records])


def history():
    with _connection() as connection:
        rows = connection.execute("SELECT payload FROM runs ORDER BY timestamp DESC, rowid DESC").fetchall()
    return [json.loads(row[0]) for row in rows]


@st.cache_data
def reference_data(stamp):
    return pd.read_csv(ROOT / "data/raw/ai4i2020.csv")


def dataset():
    path = ROOT / "data/raw/ai4i2020.csv"
    return reference_data(path.stat().st_mtime_ns)


@st.cache_data(show_spinner=False)
def validation(version, threshold, dataset_stamp):
    """Reproduce notebook split. This split was also used for threshold tuning."""
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, confusion_matrix, roc_curve, precision_recall_curve
    df = dataset()
    _, test = train_test_split(df, test_size=0.20, random_state=42, stratify=df["Machine failure"])
    model, _, _ = assets()
    x = prepare(test)
    y = test["Machine failure"].to_numpy()
    p = model.predict_proba(x)[:, 1]
    pred = (p >= threshold).astype(int)
    fpr, tpr, _ = roc_curve(y, p)
    precision, recall, _ = precision_recall_curve(y, p)
    return {"accuracy": accuracy_score(y, pred), "precision": precision_score(y, pred, zero_division=0),
            "recall": recall_score(y, pred, zero_division=0), "f1": f1_score(y, pred, zero_division=0),
            "auc": roc_auc_score(y, p), "matrix": confusion_matrix(y, pred).tolist(), "n": len(y),
            "roc": pd.DataFrame({"False positive rate": fpr, "True positive rate": tpr}),
            "pr": pd.DataFrame({"Recall": recall, "Precision": precision})}


def metrics():
    _, threshold, version = assets()
    return validation(version, threshold, (ROOT / "data/raw/ai4i2020.csv").stat().st_mtime_ns)


@st.cache_data(show_spinner=False)
def validation_rows(version, dataset_stamp):
    """Row-level replay for inspection; IDs identify source rows, not physical machines."""
    from sklearn.model_selection import train_test_split
    df = dataset()
    _, held = train_test_split(df, test_size=.20, random_state=42, stratify=df["Machine failure"])
    rows = held[INPUTS].copy().reset_index(drop=True)
    rows.insert(0, "Dataset row", held.index.to_numpy() + 2)
    rows["Actual failure"] = held["Machine failure"].to_numpy()
    rows["Failure probability"] = assets()[0].predict_proba(prepare(held))[:, 1]
    return rows


def evaluation_rows():
    return validation_rows(assets()[2], (ROOT / "data/raw/ai4i2020.csv").stat().st_mtime_ns)


def explain(record):
    """Exact TreeSHAP from XGBoost; signed contributions in log-odds, not percentages."""
    import xgboost as xgb
    model, _, _ = assets()
    if record["version"] != assets()[2]:
        raise ValueError("This run used an older model artifact. Re-run it for a current explanation.")
    preprocessor = model.named_steps["preprocessor"]
    data = prepare(pd.DataFrame([record["inputs"]]))
    transformed = preprocessor.transform(data)
    values = model.named_steps["classifier"].get_booster().predict(xgb.DMatrix(transformed), pred_contribs=True)[0]
    names = preprocessor.get_feature_names_out()
    merged = {}
    for name, value in zip(names, values[:-1]):
        label = "Machine type" if name.startswith("cat__") else name.replace("num__", "")
        merged[label] = merged.get(label, 0.0) + float(value)
    frame = pd.DataFrame({"Feature": list(merged), "Contribution": list(merged.values())})
    frame["Effect"] = np.where(frame["Contribution"] >= 0, "Raises risk", "Lowers risk")
    return frame.sort_values("Contribution", key=lambda s: s.abs(), ascending=False), float(values[-1])


def importance():
    model, _, _ = assets()
    names = model.named_steps["preprocessor"].get_feature_names_out()
    values = model.named_steps["classifier"].feature_importances_
    frame = pd.DataFrame({"Feature": ["Machine type" if n.startswith("cat__") else n.replace("num__", "") for n in names], "Importance": values})
    return frame.groupby("Feature", as_index=False).sum().sort_values("Importance", ascending=False)


@st.cache_data(show_spinner=False)
def _demo_runs(version, threshold, dataset_stamp):
    """Actual reference-row scores, with explicitly illustrative timestamps and IDs."""
    df = dataset()
    selected = pd.concat([df[df["Machine failure"] == 0].sample(40, random_state=9), df[df["Machine failure"] == 1].sample(8, random_state=21)]).sample(frac=1, random_state=3)
    records = predict(selected, source="Demo")
    start = datetime.now(IST).replace(minute=0, second=0, microsecond=0) - timedelta(hours=24)
    for i, record in enumerate(records):
        record["id"] = f"DEMO-{i + 1:04d}"
        record["timestamp"] = (start + timedelta(minutes=30 * i)).isoformat()
    return list(reversed(records))


def demo_runs(version):
    return _demo_runs(version, assets()[1], (ROOT / "data/raw/ai4i2020.csv").stat().st_mtime_ns)


def table(records):
    return pd.DataFrame([{"Run ID": r["id"], "Time (IST)": datetime.fromisoformat(r["timestamp"]).astimezone(IST).strftime("%d %b %H:%M:%S"),
                          "Type": r["inputs"]["Type"], "Risk": r["risk"], "Failure probability": r["probability"],
                          "Source": r["source"], "Inference (ms)": round(r["latency_ms"], 2), "Batch size": r["batch_size"]} for r in records])


def export_csv(records):
    """Flat, reproducible export including the original inputs and derived features."""
    rows = [{**{k: v for k, v in r.items() if k != "inputs"}, **r["inputs"]} for r in records]
    return pd.DataFrame(rows).to_csv(index=False).encode("utf-8")
