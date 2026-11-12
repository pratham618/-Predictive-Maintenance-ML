"""Maintenance workflow, operator evidence and descriptive prediction comparisons."""
from datetime import datetime
import json

import pandas as pd
import streamlit as st

import maintenance
import services as api
import ui


def local_time(value):
    return datetime.fromisoformat(value).astimezone(api.IST).strftime("%Y-%m-%d %H:%M:%S IST") if value else ""


def work_table(items):
    return pd.DataFrame([{
        "Work ID": w["work_id"], "Machine ID": w["machine_id"], "Type": w["kind"],
        "Status": w["status"], "Description": w["description"],
        "Latest notes": w["notes"],
        "Linked run": w["run_id"] or "", "Updated": local_time(w["recorded_at"]),
        "Completed": local_time(w["completed_at"]), "Recorded by": w["operator"],
    } for w in items])


def page():
    ui.heading("Maintenance & outcomes", "Record work and evidence against actual machine assessments.", "WORKSPACE / MAINTENANCE")
    st.caption("Operator-entered records · no automatic diagnosis, sensor verification or retraining.")
    records = api.history()
    eligible = [r for r in records if maintenance.eligible(r)]
    revisions = api.work_history()
    work = maintenance.latest(revisions, "work_id")
    outcomes = api.outcome_history()
    current_outcomes = maintenance.latest(outcomes, "run_id")
    confirmed = sum(r["outcome"] != "Unverified" for r in current_outcomes)
    a, b, c = st.columns(3)
    a.metric("Open work", sum(w["status"] in ("Open", "In progress") for w in work), border=True)
    b.metric("Completed work", sum(w["status"] == "Completed" for w in work), border=True)
    c.metric("Confirmed assessments", confirmed, border=True)
    section = st.segmented_control(
        "Maintenance section", ["Work log", "Confirm outcomes", "Prediction review"],
        default="Work log", key="maintenance_section",
    )
    if section == "Confirm outcomes":
        outcome_form(eligible, outcomes)
    elif section == "Prediction review":
        prediction_review(eligible, outcomes)
    else:
        work_log(eligible, work, revisions)


def work_log(records, work, revisions):
    st.subheader("Work log")
    identities = sorted({r["machine_id"] for r in records} | {w["machine_id"] for w in work})
    a, b = st.columns(2)
    identity_filter = a.selectbox("Machine filter", ["All"] + identities)
    status_filter = b.selectbox("Work status", ["All"] + list(maintenance.STATUSES))
    filtered = [w for w in work if (identity_filter == "All" or w["machine_id"] == identity_filter)
                and (status_filter == "All" or w["status"] == status_filter)]
    if filtered:
        st.dataframe(work_table(filtered), hide_index=True, alt="Maintenance work matching machine and status filters")
        st.download_button("Export work CSV", work_table(filtered).to_csv(index=False),
                           file_name="maintenance-work.csv", mime="text/csv")
    else:
        st.info("No matching work items. Create an inspection or maintenance item below.")

    with st.expander("Create work item", expanded=not work):
        identity = st.text_input("Machine ID", max_chars=64, key="work_machine",
                                 help="Use the same case-sensitive asset ID as your predictions. A new asset can have work before its first prediction.")
        options = [None] + [r["id"] for r in records if r["machine_id"] == identity.strip()]
        linked = st.selectbox("Link an assessment (optional)", options,
                              format_func=lambda x: x or "No linked assessment", key="work_link")
        with st.form("create_work"):
            kind = st.selectbox("Work type", maintenance.KINDS)
            description = st.text_input("Work description", max_chars=500)
            notes = st.text_area("Notes", max_chars=2000)
            operator = st.text_input("Recorded by", value=st.session_state.get("operator_name", "Local operator"), max_chars=60, key="work_operator")
            submitted = st.form_submit_button("Save work item", type="primary")
        if submitted:
            try:
                api.create_work(identity, kind, description, notes, operator, linked)
                st.session_state["maintenance_notice"] = "Work item saved."
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

    if work:
        with st.expander("Update work status"):
            work_id = st.selectbox("Work item", [w["work_id"] for w in work],
                                   format_func=lambda x: next(f"{w['work_id']} · {w['machine_id']} · {w['description']}" for w in work if w["work_id"] == x))
            current = next(w for w in work if w["work_id"] == work_id)
            st.caption(f"Current status: {current['status']}. Work status does not confirm a prediction outcome.")
            with st.form("update_work"):
                status = st.selectbox("New status", [s for s in maintenance.STATUSES if s != current["status"]])
                reason = st.text_area("Update reason", max_chars=2000)
                operator = st.text_input("Recorded by", value=st.session_state.get("operator_name", "Local operator"), max_chars=60, key="update_operator")
                submitted = st.form_submit_button("Save status update")
            if submitted:
                try:
                    api.update_work(work_id, status, reason, operator)
                    st.session_state["maintenance_notice"] = "Status update saved."
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
            audit = [r for r in revisions if r["work_id"] == work_id]
            st.dataframe(pd.DataFrame([{
                "Recorded": local_time(r["recorded_at"]), "Status": r["status"],
                "Notes": r["notes"], "Recorded by": r["operator"],
            } for r in audit]), hide_index=True, alt="Append-only status history for the selected work item")
    if revisions:
        st.download_button("Export complete work audit JSON", json.dumps(revisions, indent=2),
                           file_name="maintenance-audit.json", mime="application/json")


def outcome_form(records, revisions):
    st.subheader("Confirm assessment outcomes")
    st.info("Confirm the condition at the original assessment time only when you have matching evidence. A failure that happened later is a separate maintenance event. Unknown outcomes remain unverified.")
    if not records:
        st.caption("No eligible assessments. Save actual operating readings with a Machine ID first. Sample/reference and unassigned records cannot receive outcome labels.")
        return
    identity = st.selectbox("Outcome machine", sorted({r["machine_id"] for r in records}))
    matching = [r for r in records if r["machine_id"] == identity]
    run_id = st.selectbox("Assessment", [r["id"] for r in matching],
                         format_func=lambda x: next(f"{r['id']} · {local_time(r['timestamp'])} · {r['probability']:.1%}" for r in matching if r["id"] == x))
    record = next(r for r in matching if r["id"] == run_id)
    audit = [r for r in revisions if r["run_id"] == run_id]
    st.caption(f"Saved prediction: {record['probability']:.1%} · threshold {record['threshold']:.0%} · model {record['version']}")
    st.markdown(f"Current operator label: **{audit[0]['outcome'] if audit else 'Unverified'}**")
    with st.form("confirm_outcome"):
        outcome = st.selectbox("Verified condition at assessment", maintenance.OUTCOMES)
        notes = st.text_area("Evidence or correction reason", max_chars=2000,
                             help="Describe the inspection, record or other evidence that establishes the condition at this assessment. Required for corrections too.")
        operator = st.text_input("Recorded by", value=st.session_state.get("operator_name", "Local operator"), max_chars=60, key="outcome_operator")
        acknowledged = st.checkbox("I am recording evidence about the condition at this assessment, not a later failure.")
        submitted = st.form_submit_button("Save outcome", type="primary")
    if submitted:
        if not acknowledged:
            st.error("Confirm that the evidence refers to the original assessment.")
        else:
            try:
                api.confirm_outcome(run_id, outcome, notes, operator)
                st.session_state["maintenance_notice"] = "Outcome saved. Original prediction preserved."
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
    if audit:
        st.dataframe(pd.DataFrame([{
            "Recorded": local_time(r["recorded_at"]), "Outcome": r["outcome"],
            "Evidence": r["notes"], "Recorded by": r["operator"],
        } for r in audit]), hide_index=True, alt="Outcome confirmations and corrections for this assessment")
        st.download_button("Export assessment evidence JSON", json.dumps(audit, indent=2),
                           file_name="assessment-evidence.json", mime="application/json")


def prediction_review(records, revisions):
    st.subheader("Prediction review")
    st.warning("Descriptive comparison of selected operator-confirmed snapshots. This is not an independent test, a calibrated forecast, or proof of future failure detection. Unverified assessments are excluded from outcome counts.")
    if not records:
        st.info("No assigned operating assessments available for review.")
        return
    machine = st.selectbox("Review machine", ["All"] + sorted({r["machine_id"] for r in records}))
    versions = list(dict.fromkeys(r["version"] for r in records))
    version = st.selectbox("Review model version", versions)
    thresholds = sorted({r["threshold"] for r in records if r["version"] == version})
    threshold = st.selectbox("Review saved threshold", thresholds, format_func=lambda x: f"{x:.0%}")
    selected = [r for r in records if r["version"] == version and r["threshold"] == threshold
                and (machine == "All" or r["machine_id"] == machine)]
    counts, details = maintenance.review(selected, revisions)
    st.caption(f"{counts['confirmed']} confirmed of {counts['eligible']} eligible assessments · {counts['unverified']} unverified. Operator labels can be incomplete or selectively recorded.")
    cols = st.columns(4)
    for col, label, key in zip(cols, ["Caught failures", "Missed failures", "False alarms", "Correct normal"], ["caught", "missed", "false_alarms", "correct_normal"]):
        col.metric(label, counts[key])
    if counts["confirmed"] == 0:
        st.info("Record matching assessment evidence before interpreting outcome comparisons.")
    if details:
        st.dataframe(pd.DataFrame(details), hide_index=True, alt="Saved predictions compared with latest operator-confirmed assessment labels")
        st.download_button("Export prediction review CSV", pd.DataFrame(details).to_csv(index=False),
                           file_name="operator-prediction-review.csv", mime="text/csv")
    st.download_button("Export filtered outcome audit JSON", json.dumps(
        [r for r in revisions if r["run_id"] in {p["id"] for p in selected}], indent=2),
        file_name="outcome-audit.json", mime="application/json")
