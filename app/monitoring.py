"""Machine identity, additive SQLite migration and saved-assessment monitoring."""
from datetime import datetime, timedelta, timezone
import re


def machine_id(value):
    """Case-sensitive operator asset ID; never infer identity from dataset rows."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Machine ID must be text.")
    value = value.strip()
    if not value:
        return None
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}", value):
        raise ValueError("Machine ID: use 1–64 letters, numbers, dots, underscores, colons or hyphens.")
    return value


def migrate(connection):
    """Idempotent, transactional, non-destructive migration of the original table."""
    connection.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, timestamp TEXT NOT NULL, payload TEXT NOT NULL)")
    columns = {row[1] for row in connection.execute("PRAGMA table_info(runs)")}
    if "machine_id" not in columns:
        connection.execute("ALTER TABLE runs ADD COLUMN machine_id TEXT")
    connection.execute("CREATE INDEX IF NOT EXISTS runs_machine_time ON runs(machine_id, timestamp)")


def instant(record):
    stamp = datetime.fromisoformat(record["timestamp"])
    # Original records were IST. Interpret old naive timestamps consistently.
    return stamp.replace(tzinfo=timezone(timedelta(hours=5, minutes=30))) if stamp.tzinfo is None else stamp


def summarize(records, now=None):
    """Latest assessment per asset; no demo, unassigned or cross-model trends."""
    now = now or datetime.now(timezone.utc)
    groups = {}
    for record in records:
        identity = record.get("machine_id")
        if identity and record.get("source") not in ("Demo", "Sample", "Reference CSV"):
            groups.setdefault(identity, []).append(record)
    result = []
    for identity, history in sorted(groups.items()):
        history.sort(key=lambda r: (instant(r), r["id"]))
        latest = history[-1]
        comparable = [r for r in history if r["version"] == latest["version"] and r["threshold"] == latest["threshold"]]
        # Same-time batch rows are snapshots, not evidence of change over time.
        previous = next((r for r in reversed(comparable[:-1]) if instant(r) < instant(latest)), None)
        delta = latest["probability"] - previous["probability"] if previous else None
        alerts = []
        if latest["probability"] >= latest["threshold"]:
            alerts.append("High risk: arrange prompt inspection")
        elif latest["probability"] >= latest["threshold"] / 2:
            alerts.append("Watch: increase condition checks")
        if delta is not None and delta >= .10 - 1e-12:
            alerts.append("Rising risk: up at least 10 percentage points")
        stale = now - instant(latest) > timedelta(hours=24)
        if stale:
            alerts.append("Stale: no assessment in over 24 hours")
        result.append({"machine_id": identity, "latest": latest, "history": history,
                       "delta": delta, "stale": stale, "alerts": alerts})
    return result
