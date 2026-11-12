"""Append-only operator evidence and maintenance work; never changes predictions."""
from datetime import datetime, timezone
import uuid

import monitoring

OUTCOMES = ("Unverified", "Failure confirmed", "No failure confirmed")
STATUSES = ("Open", "In progress", "Completed", "Cancelled")
KINDS = ("Inspection", "Maintenance", "Failure report")
OPERATING_SOURCES = ("Manual", "CSV batch")


def migrate(db):
    db.execute("""CREATE TABLE IF NOT EXISTS outcome_revisions (
        sequence INTEGER PRIMARY KEY AUTOINCREMENT,
        id TEXT NOT NULL UNIQUE, run_id TEXT NOT NULL REFERENCES runs(id),
        machine_id TEXT NOT NULL, outcome TEXT NOT NULL
            CHECK(outcome IN ('Unverified','Failure confirmed','No failure confirmed')),
        notes TEXT NOT NULL, operator TEXT NOT NULL, recorded_at TEXT NOT NULL)""")
    db.execute("CREATE INDEX IF NOT EXISTS outcome_run_sequence ON outcome_revisions(run_id, sequence)")
    db.execute("""CREATE TABLE IF NOT EXISTS maintenance_revisions (
        sequence INTEGER PRIMARY KEY AUTOINCREMENT,
        id TEXT NOT NULL UNIQUE, work_id TEXT NOT NULL, machine_id TEXT NOT NULL,
        run_id TEXT REFERENCES runs(id),
        kind TEXT NOT NULL CHECK(kind IN ('Inspection','Maintenance','Failure report')),
        status TEXT NOT NULL CHECK(status IN ('Open','In progress','Completed','Cancelled')),
        description TEXT NOT NULL, notes TEXT NOT NULL, operator TEXT NOT NULL,
        recorded_at TEXT NOT NULL, completed_at TEXT)""")
    db.execute("CREATE INDEX IF NOT EXISTS maintenance_work_sequence ON maintenance_revisions(work_id, sequence)")
    db.execute("CREATE INDEX IF NOT EXISTS maintenance_machine ON maintenance_revisions(machine_id)")


def text(value, label, limit, required=True):
    if not isinstance(value, str):
        raise ValueError(f"{label} must be text.")
    value = value.strip()
    if (required and not value) or len(value) > limit:
        raise ValueError(f"{label}: enter {'1' if required else '0'}–{limit} characters.")
    return value


def rows(db, table, **filters):
    # Table and filter names come only from the fixed functions below.
    where = " AND ".join(f"{key} = ?" for key in filters) or "1"
    cursor = db.execute(f"SELECT * FROM {table} WHERE {where} ORDER BY sequence DESC", tuple(filters.values()))
    names = [c[0] for c in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def eligible(record):
    return bool(record.get("machine_id")) and record.get("source") in OPERATING_SOURCES and not record["id"].startswith("DEMO-")


def validate_link(db, identity, run_id):
    if run_id is None:
        return
    row = db.execute("SELECT payload, machine_id FROM runs WHERE id = ?", (run_id,)).fetchone()
    if row is None:
        raise ValueError("The linked assessment does not exist.")
    import json
    record = {**json.loads(row[0]), "machine_id": row[1]}
    if not eligible(record):
        raise ValueError("Link an assigned operating assessment, not sample/reference or unassigned data.")
    if record["machine_id"] != identity:
        raise ValueError("The linked assessment belongs to a different machine.")


def stamp():
    return datetime.now(timezone.utc).isoformat()


def confirm_outcome(db, run_id, outcome, notes, operator):
    if outcome not in OUTCOMES:
        raise ValueError("Choose a supported outcome.")
    row = db.execute("SELECT machine_id FROM runs WHERE id = ?", (run_id,)).fetchone()
    if row is None:
        raise ValueError("The assessment does not exist.")
    identity = row[0]
    validate_link(db, identity, run_id)
    notes = text(notes, "Evidence or correction reason", 2000)
    operator = text(operator, "Recorded by", 60)
    revision = {
        "id": uuid.uuid4().hex, "run_id": run_id, "machine_id": identity,
        "outcome": outcome, "notes": notes, "operator": operator, "recorded_at": stamp()
    }
    insert(db, "outcome_revisions", revision)
    return revision


def insert(db, table, values):
    keys = ", ".join(values)
    placeholders = ", ".join("?" for _ in values)
    db.execute(f"INSERT INTO {table} ({keys}) VALUES ({placeholders})", tuple(values.values()))


def outcome_history(db, run_id=None):
    return rows(db, "outcome_revisions", **({"run_id": run_id} if run_id else {}))


def work_history(db, work_id=None):
    return rows(db, "maintenance_revisions", **({"work_id": work_id} if work_id else {}))


def latest(revisions, key):
    """The database supplies descending immutable sequence order, including ties."""
    seen = set()
    result = []
    for revision in revisions:
        if revision[key] not in seen:
            seen.add(revision[key])
            result.append(revision)
    return result


def create_work(db, identity, kind, description, notes, operator, run_id=None):
    identity = monitoring.machine_id(identity)
    if identity is None:
        raise ValueError("A Machine ID is required.")
    if kind not in KINDS:
        raise ValueError("Choose a supported work type.")
    validate_link(db, identity, run_id)
    revision = {
        "id": uuid.uuid4().hex, "work_id": "WORK-" + uuid.uuid4().hex[:12].upper(),
        "machine_id": identity, "run_id": run_id, "kind": kind, "status": "Open",
        "description": text(description, "Work description", 500),
        "notes": text(notes, "Notes", 2000, required=False),
        "operator": text(operator, "Recorded by", 60), "recorded_at": stamp(),
        "completed_at": None,
    }
    insert(db, "maintenance_revisions", revision)
    return revision


def update_work(db, work_id, status, notes, operator):
    if status not in STATUSES:
        raise ValueError("Choose a supported status.")
    revisions = work_history(db, work_id)
    if not revisions:
        raise ValueError("The work item does not exist.")
    old = revisions[0]
    if status == old["status"]:
        raise ValueError("Choose a different status.")
    revision = {k: v for k, v in old.items() if k != "sequence"}
    revision.update(
        id=uuid.uuid4().hex, status=status,
        notes=text(notes, "Update reason", 2000), operator=text(operator, "Recorded by", 60),
        recorded_at=stamp(),
    )
    revision["completed_at"] = revision["recorded_at"] if status == "Completed" else None
    insert(db, "maintenance_revisions", revision)
    return revision


def review(records, revisions):
    """Descriptive operator labels at assessment time, never a future forecast test."""
    outcomes = {r["run_id"]: r for r in latest(revisions, "run_id")}
    counts = dict(caught=0, missed=0, false_alarms=0, correct_normal=0,
                  unverified=0, confirmed=0, eligible=0)
    details = []
    for record in records:
        if not eligible(record):
            continue
        counts["eligible"] += 1
        revision = outcomes.get(record["id"])
        label = revision["outcome"] if revision else "Unverified"
        predicted = record["probability"] >= record["threshold"]
        outcome = "Unverified"
        if label == "Unverified":
            counts["unverified"] += 1
        else:
            failure = label == "Failure confirmed"
            key, outcome = (
                ("caught", "Caught failure") if failure and predicted else
                ("missed", "Missed failure") if failure else
                ("false_alarms", "False alarm") if predicted else
                ("correct_normal", "Correct normal")
            )
            counts[key] += 1
            counts["confirmed"] += 1
        details.append({
            "Run ID": record["id"], "Machine ID": record["machine_id"],
            "Assessed at": record["timestamp"], "Model version": record["version"],
            "Saved threshold": record["threshold"], "Failure probability": record["probability"],
            "Operator label": label, "Comparison": outcome,
        })
    return counts, details
