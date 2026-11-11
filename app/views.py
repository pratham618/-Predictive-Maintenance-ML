"""Six complete screens composed from reusable UI and model-service functions."""
from datetime import datetime
from io import BytesIO
import hashlib
import numpy as np
import pandas as pd
import altair as alt
import streamlit as st

import services as api
import evaluation
import ui
from reports import pdf_report

RECOMMENDATIONS = {
    "Low": ("Below the watch band", "Continue the scheduled maintenance cycle. Record operating readings and reassess when conditions change."),
    "Medium": ("Worth a closer look", "Increase condition checks. Review cooling, loading, and tool wear with the maintenance team. Inspect if elevated risk persists."),
    "High": ("Inspection recommended", "Arrange a prompt inspection. Review cooling, machine load, and tool condition against specifications before continuing production under your site procedures."),
}


def exports(records, key):
    if not records:
        return
    c1,c2 = st.columns(2)
    c1.download_button("Export CSV", api.export_csv(records), file_name="prediction-runs.csv", mime="text/csv", key=key+"csv", width="stretch")
    c2.download_button("Export PDF" if len(records)<=200 else "PDF · first 200 rows", pdf_report(records[:200]), file_name="prediction-report.pdf", mime="application/pdf", key=key+"pdf", width="stretch")


def overview():
    model, threshold, version = api.assets()
    top, action = st.columns([4,1], vertical_alignment="bottom")
    with top:
        ui.heading("System overview", "Every signal in context. Every decision, informed.", "WORKSPACE / OVERVIEW")
    with action:
        if st.button("Run prediction  →", type="primary", width="stretch", key="overview_run"):
            st.switch_page("app_pages/predict.py")
    demo = st.session_state.get("demo_mode", True)
    records = api.demo_runs(version) if demo else api.history()
    with st.container(horizontal=True, horizontal_alignment="distribute"):
        st.caption("DEMO FEED · Reference samples with illustrative timestamps" if demo else "LIVE WORKSPACE · Your saved prediction runs")
        st.caption("Times shown in IST  ·  Local inference")
    scores = api.metrics()
    actual = api.history()
    single_latency = [r["latency_ms"] for r in actual if r["batch_size"] == 1]
    cols = st.columns(4)
    cols[0].metric("Validation accuracy", f"{scores['accuracy']:.2%}", "2,000 validation samples", delta_color="off", border=True, help="Original notebook split, also used to tune the threshold. Not an independent final test.")
    cols[1].metric("Median inference", f"{np.median(single_latency):.1f} ms" if single_latency else "—", "Real single-snapshot runs" if single_latency else "Run a prediction to measure", delta_color="off", border=True, chart_data=single_latency[-15:] or None)
    cols[2].metric("Prediction runs", f"{len(records):,}", "Demo snapshots" if demo else "Saved locally", delta_color="off", border=True)
    cols[3].metric("Drift monitor", "Not set", "Needs a production baseline", delta_color="off", border=True, help="No live sensor feed or drift detector is configured. This is not a zero-alert claim.")
    st.space("small")
    main, side = st.columns([2.15,1], gap="medium")
    with main, st.container(border=True):
        ui.section("Prediction activity", "Failure probability across analyzed snapshots", "activity", "DEMO · 24 HOURS" if demo else "SAVED RUNS")
        if records:
            ui.risk_chart(records[:200], threshold)
            low = sum(r["risk"] == "Low" for r in records)
            medium = sum(r["risk"] == "Medium" for r in records)
            high = sum(r["risk"] == "High" for r in records)
            st.caption(f"●  Low: {low}      ◇  Medium: {medium}      ▲  High: {high}      ·      Failure threshold {threshold:.0%}")
        else:
            ui.empty("Your timeline starts here", "Run a prediction, or enable the demo feed in the sidebar to explore the overview.")
    with side, st.container(border=True):
        ui.section("Model status", "Connected to your local model", "cpu", "READY")
        st.html(f'<div class="pm-model-visual"><div class="pm-model-node">{ui.svg("database")}</div><div class="pm-model-line"></div><div class="pm-model-node pm-model-core">{ui.svg("cpu",size=28)}</div><div class="pm-model-line"></div><div class="pm-model-node">{ui.svg("activity")}</div></div>')
        ui.key_values([("Engine", "XGBoost classifier"), ("Artifact version", version), ("Decision threshold", f"{threshold:.0%}"), ("Last trained", "Not recorded"), ("Input features", "6 inputs → 8 features")])
        st.page_link("app_pages/performance.py", label="Explore model performance  ↗")
    with st.container(border=True):
        ui.section("Recent activity", "Select a run to inspect its operating snapshot", "history", "DEMO" if demo else "LOCAL HISTORY")
        recent = records[:6]
        selected = ui.runs_table(recent, "overview_table", selectable=True, height=245)
        if selected and selected.selection.rows:
            record = recent[selected.selection.rows[0]]
            with st.expander(f"Inspect {record['id']}", expanded=True):
                st.caption(f"{record['risk']} risk · {record['probability']:.1%} failure probability · {record['source']} source")
                ui.key_values([(k,v) for k,v in record["inputs"].items() if k in api.INPUTS])
                if st.button("Use these inputs", key="recent_reuse"):
                    st.session_state["pending_inputs"] = record["inputs"]
                    st.switch_page("app_pages/predict.py")


def _set_inputs(values):
    for key, col in [("machine_type","Type"),("air","Air temperature [K]"),("process","Process temperature [K]"),("speed","Rotational speed [rpm]"),("torque","Torque [Nm]"),("wear","Tool wear [min]")]:
        value = values[col]
        st.session_state[key] = int(value) if key in ["speed","wear"] else float(value) if key not in ["machine_type"] else value


def _run(frame, source):
    with st.status("Analyzing machine conditions…", expanded=True) as status:
        st.write("Checking input ranges and required fields")
        api.prepare(frame)
        st.write("Running the saved XGBoost pipeline")
        records = api.predict(frame, source)
        st.write("Saving results to local history")
        api.save_runs(records)
        status.update(label=f"Analysis complete · {len(records):,} snapshot(s)", state="complete", expanded=False)
    st.session_state["last_batch"] = records
    st.session_state["current_result"] = records[0]
    st.session_state["switch_to_live"] = True
    st.toast("Prediction complete. Results saved to History.", icon=":material/check_circle:")
    return records


def prediction():
    ui.heading("Run a prediction", "From operating conditions to a clear next step.", "WORKSPACE / INFERENCE")
    mode = st.segmented_control("Input source", ["Manual input", "CSV batch"], default="Manual input", key="input_mode", label_visibility="collapsed")
    if mode == "CSV batch":
        batch_prediction()
        return
    if "pending_inputs" in st.session_state:
        _set_inputs(st.session_state.pop("pending_inputs"))
    if "machine_type" not in st.session_state:
        _set_inputs(api.SAMPLE)
    left, right = st.columns([1.15,1], gap="medium")
    with left:
        with st.container(border=True):
            ui.section("Operating conditions", "One machine. One point in time.", "settings", "6 INPUTS")
            sample_col, sample_button = st.columns([2,1], vertical_alignment="bottom")
            choice = sample_col.selectbox("Sample scenario", ["Normal operation", "Reference failure sample"], key="scenario")
            if sample_button.button("Load sample", width="stretch"):
                _set_inputs(api.SAMPLE if choice == "Normal operation" else api.dataset().query('`Machine failure` == 1').iloc[0].to_dict())
                st.toast("Sample loaded. Select Analyze machine to run it.")
            with st.form("machine_inputs", border=False):
                c1,c2 = st.columns(2)
                with c1:
                    st.selectbox("Machine type", ["L","M","H"], key="machine_type", help="L, M and H are the quality variants from the reference dataset.", persist_state="session")
                    st.number_input("Air temperature · K", min_value=250.,max_value=350.,step=.1,key="air",persist_state="session")
                    st.number_input("Process temperature · K", min_value=250.,max_value=400.,step=.1,key="process",persist_state="session")
                with c2:
                    st.number_input("Rotational speed · rpm", min_value=0,max_value=5000,step=10,key="speed",persist_state="session")
                    st.number_input("Torque · Nm", min_value=0.,max_value=150.,step=.5,key="torque",persist_state="session")
                    st.number_input("Tool wear · min", min_value=0,max_value=500,step=5,key="wear",persist_state="session")
                submitted = st.form_submit_button("Analyze machine  →", type="primary", width="stretch")
            st.caption("Temperature difference and mechanical power are calculated automatically.")
        if submitted:
            frame = pd.DataFrame([{"Type":st.session_state.machine_type,"Air temperature [K]":st.session_state.air,"Process temperature [K]":st.session_state.process,"Rotational speed [rpm]":st.session_state.speed,"Torque [Nm]":st.session_state.torque,"Tool wear [min]":st.session_state.wear}])
            try:
                _run(frame, "Manual")
            except Exception as exc:
                st.session_state.pop("current_result", None)
                st.error(f"Unable to analyze: {exc}")
        with st.expander("Understanding the risk bands"):
            _,threshold,_ = api.assets()
            st.markdown(f"**Low:** below {threshold/2:.0%}. **Medium:** {threshold/2:.0%} to below {threshold:.0%}. **High:** {threshold:.0%} and above.")
            st.caption("Medium is a monitoring convention at half the saved threshold. It is not a separately trained class. Failure probability is not a calibrated confidence score.")
    with right:
        result = st.session_state.get("current_result")
        with st.container(border=True):
            ui.section("Prediction result", "Last completed snapshot", "shield", "READY" if result else "AWAITING INPUT")
            if result:
                result_summary(result)
            else:
                ui.empty("Ready when you are", "Enter operating conditions or load a sample. Your failure estimate and recommended next steps will appear here.", "cpu")
                ui.key_values([("Model", "XGBoost"),("Decision threshold", f"{api.assets()[1]:.0%}"),("Processing", "Local · on demand")])
    if st.session_state.get("current_result"):
        result_details(st.session_state.current_result)


def result_summary(record):
    ui.gauge(record["probability"], record["risk"])
    title, recommendation = RECOMMENDATIONS[record["risk"]]
    st.markdown(f"**{title}**")
    st.caption(recommendation)
    ui.key_values([("Failure threshold", f"{record['threshold']:.0%}"), ("Inference duration", f"{record['latency_ms']:.2f} ms"), ("Run", record["id"])])
    if record["batch_size"] > 1:
        st.caption(f"Duration covers the complete {record['batch_size']:,}-row batch.")


def result_details(record):
    row = record["inputs"]
    st.space("small")
    cols = st.columns(4)
    cols[0].metric("Temperature difference", f"{row['Temperature difference']:.1f} K", border=True)
    cols[1].metric("Mechanical power", f"{row['Power [W]']/1000:.2f} kW", border=True)
    cols[2].metric("Rotational speed", f"{row['Rotational speed [rpm]']:,.0f} rpm", border=True)
    cols[3].metric("Tool wear", f"{row['Tool wear [min]']:.0f} min", border=True)
    if row["Temperature difference"] < 0:
        st.warning("Process temperature is below air temperature. Verify these readings before using the assessment.")
    left,right = st.columns([1.65,1], gap="medium")
    with left, st.container(border=True):
        ui.section("What shaped this prediction?", "Exact feature contributions from the saved model", "chart", "TREE SHAP")
        try:
            frame, baseline = api.explain(record)
            ui.feature_chart(frame)
            st.caption("Cyan lowers the model's failure score; red raises it. Contributions are in log-odds and describe the model, not physical causes.")
            with st.expander("Explanation details"):
                st.caption(f"Baseline log-odds: {baseline:.4f}. Contributions plus baseline reconstruct the raw model score.")
                st.dataframe(frame, hide_index=True, alt="Exact signed TreeSHAP contributions")
        except Exception as exc:
            st.warning(f"Explanation unavailable: {exc}")
    with right, st.container(border=True):
        ui.section("Snapshot details", "Reproducible inputs and exports", "layers")
        ui.key_values([("Machine type",row["Type"]),("Air temperature",f"{row['Air temperature [K]']:.1f} K"),("Process temperature",f"{row['Process temperature [K]']:.1f} K"),("Torque",f"{row['Torque [Nm]']:.1f} Nm"),("Model version",record["version"])])
        st.caption("Results always refer to the last completed snapshot. Analyze again after editing inputs.")
        exports([record],"result_")


def read_upload(uploaded):
    if uploaded.size > 10*1024*1024:
        raise ValueError("Please use a CSV smaller than 10 MB.")
    frame = pd.read_csv(BytesIO(uploaded.getvalue()))
    api.prepare(frame)
    return frame


def batch_prediction():
    with st.container(border=True):
        ui.section("Batch inference", "Upload up to 5,000 operating snapshots", "database", "CSV")
        st.download_button("Download CSV template",pd.DataFrame([api.SAMPLE]).to_csv(index=False),file_name="machine-input-template.csv",mime="text/csv")
        upload=st.file_uploader("Drop a CSV here or browse files",type=["csv"],key="batch_upload",help="Required columns match the template. Extra columns are ignored; derived features are recalculated.")
        frame=None
        if upload:
            fingerprint=hashlib.sha256(upload.getvalue()).hexdigest()
            if fingerprint != st.session_state.get("batch_fingerprint"):
                st.session_state.pop("batch_results",None)
                st.session_state["batch_fingerprint"]=fingerprint
            try:
                frame=read_upload(upload)
                st.success(f"Validated {len(frame):,} rows · Ready for inference")
                st.dataframe(frame[api.INPUTS].head(10),hide_index=True,alt="First ten validated CSV snapshots")
            except Exception as exc:
                st.error(f"CSV needs attention: {exc}")
        elif "uploaded_dataset" in st.session_state:
            if st.button("Use dataset from Datasets"):
                st.session_state["batch_dataset"] = st.session_state["uploaded_dataset"].copy()
        if frame is None and not upload and "batch_dataset" in st.session_state:
            frame=st.session_state["batch_dataset"]
            st.caption(f"Using uploaded dataset · {len(frame):,} rows")
        if st.button("Analyze batch  →",type="primary",disabled=frame is None,width="stretch"):
            try:
                st.session_state["batch_results"]=_run(frame,"CSV batch")
            except Exception as exc:
                st.session_state.pop("batch_results",None)
                st.error(f"Unable to analyze batch: {exc}")
    results=st.session_state.get("batch_results")
    if results:
        with st.container(border=True):
            ui.section("Batch results", "Select a row to inspect its prediction", "activity")
            selected=ui.runs_table(results,"batch_table",True,320)
            exports(results,"batch_")
            if selected and selected.selection.rows:
                record=results[selected.selection.rows[0]]
                st.session_state["current_result"]=record
                result_summary(record)
                result_details(record)


def history_page():
    ui.heading("Prediction history", "A traceable record of every machine assessment.", "WORKSPACE / HISTORY")
    records=api.history()
    with st.container(border=True):
        ui.section("Run log", "Saved on this computer · Demo feed excluded", "history", f"{len(records):,} RUNS")
        c1,c2,c3=st.columns([2,1,1])
        search=c1.text_input("Search runs",placeholder="Run ID, machine type, source…")
        risk=c2.selectbox("Risk level",["All","Low","Medium","High"])
        source=c3.selectbox("Source",["All","Manual","CSV batch"])
        filtered=[r for r in records if (risk=="All" or r["risk"]==risk) and (source=="All" or r["source"]==source) and (not search or search.casefold() in f"{r['id']} {r['inputs']['Type']} {r['source']} {r['timestamp']}".casefold())]
        if not filtered and records:
            ui.empty("No matching runs", "Try another search or clear the filters.","search")
        else:
            selected=ui.runs_table(filtered,"history_table",True,360)
            st.caption("Click a column header to sort. Select a row for details and reuse. Exports follow the current filters.")
            exports(filtered,"history_")
            if selected and selected.selection.rows:
                record=filtered[selected.selection.rows[0]]
                ui.section(f"Run {record['id']}","Selected snapshot", "cpu")
                if st.button("Reuse inputs in a new prediction",key="history_reuse"):
                    st.session_state["pending_inputs"]=record["inputs"]
                    st.switch_page("app_pages/predict.py")
                result_summary(record)
                result_details(record)


def performance():
    ui.heading("Model performance", "Measure what matters. Understand the trade-offs.", "MODEL / VALIDATION")
    m=api.metrics()
    _,threshold,version=api.assets()
    ui.note("Reproduces the notebook's stratified 80/20 split (random state 42). The 2,000-row validation split was also used for threshold tuning; these are not independent final-test metrics.")
    evaluation_panel(threshold, version)
    cols=st.columns(4)
    for col,label,value in zip(cols,["Accuracy","Failure precision","Failure recall","ROC–AUC"],[m["accuracy"],m["precision"],m["recall"],m["auc"]]):
        col.metric(label,f"{value:.2%}" if label!="ROC–AUC" else f"{value:.4f}",border=True)
    left,right=st.columns(2)
    with left,st.container(border=True):
        ui.section("Confusion matrix",f"Decision threshold {threshold:.0%} · {m['n']:,} samples","grid")
        matrix=pd.DataFrame([{"Actual":a,"Predicted":p,"Samples":m["matrix"][i][j]} for i,a in enumerate(["No failure","Failure"]) for j,p in enumerate(["No failure","Failure"])])
        base=alt.Chart(matrix).encode(x=alt.X("Predicted:N",sort=["No failure","Failure"]),y=alt.Y("Actual:N",sort=["No failure","Failure"]))
        rect=base.mark_rect(cornerRadius=6).encode(color=alt.Color("Samples:Q",scale=alt.Scale(range=["#173038","#18849a"]),legend=None),tooltip=["Actual","Predicted","Samples"])
        text=base.mark_text(color="#ffffff",font="JetBrains Mono",fontSize=25).encode(text="Samples:Q")
        st.altair_chart(ui.chart_style(rect+text,220),theme=None,alt="Confusion matrix for the reproduced validation split")
    with right,st.container(border=True):
        ui.section("Precision & recall", "Trade-off across decision thresholds", "chart",f"F1 {m['f1']:.3f}")
        chart=alt.Chart(m["pr"]).mark_line(color="#61d9ef",strokeWidth=2).encode(x=alt.X("Recall:Q",scale=alt.Scale(domain=[0,1]),axis=alt.Axis(format="%")),y=alt.Y("Precision:Q",scale=alt.Scale(domain=[0,1]),axis=alt.Axis(format="%")),tooltip=[alt.Tooltip("Recall:Q",format=".1%"),alt.Tooltip("Precision:Q",format=".1%")])
        st.altair_chart(ui.chart_style(chart,220),theme=None,alt="Precision recall curve; increasing recall generally reduces precision")
    left,right=st.columns([1.5,1])
    with left,st.container(border=True):
        ui.section("Global feature importance","Relative model use across decision trees","layers")
        ui.feature_chart(api.importance(),local=False)
        st.caption("Global importance does not explain an individual prediction. Use the prediction screen for signed local contributions.")
    with right,st.container(border=True):
        ui.section("Model record","Traceability and known limits","shield")
        ui.key_values([("Artifact version",version),("Algorithm","XGBoost · 300 trees"),("Validation samples",f"{m['n']:,}"),("Failure samples",str(sum(m['matrix'][1]))),("Last trained","Not recorded"),("Probability calibration","Not recorded"),("Drift monitoring","Not configured")])
        st.download_button("Download validation metrics",pd.DataFrame([{k:v for k,v in m.items() if k not in ["matrix","roc","pr"]}]).to_csv(index=False),file_name="validation-metrics.csv",mime="text/csv",width="stretch")


def evaluation_panel(threshold, version):
    rows = api.evaluation_rows()
    score = evaluation.summarize(rows["Actual failure"], rows["Failure probability"], threshold)
    with st.container(border=True):
        ui.section("Does it catch failures?", "Saved model at its live decision threshold", "shield", "VALIDATION REPLAY")
        cols = st.columns(3)
        cols[0].metric("Failures caught", str(score["caught"]), border=True,
                       help="Actual failures that triggered a failure prediction.")
        cols[1].metric("Failures missed", str(score["missed"]), border=True,
                       help="Actual failures scored below the saved threshold.")
        cols[2].metric("False alarms", str(score["false_alarms"]), border=True,
                       help="Snapshots labeled no failure that triggered a failure prediction.")
        st.markdown(f"Of **{score['caught'] + score['missed']} actual failures**, your model caught **{score['caught']}** "
                    f"and missed **{score['missed']}**. **{score['false_alarms']}** normal snapshots raised an alarm.")
        st.caption(f"Always predicting 'no failure' would score {score['baseline_accuracy']:.2%} accuracy "
                   f"while catching zero failures. Your model scores {score['accuracy']:.2%}; failure recall is {score['recall']:.1%}.")
        a,b = st.columns(2)
        for col, label, value, interval in [(a,"Failure recall",score["recall"],score["recall_interval"]),
                                             (b,"Failure precision",score["precision"],score["precision_interval"])]:
            with col:
                st.caption(f"{label}: {value:.1%} · Approx. 95% interval: {interval[0]:.1%}–{interval[1]:.1%}" if interval else f"{label}: unavailable")
        st.caption("Intervals reflect the small sample count on this fixed split. They do not correct threshold-selection bias or prove real-world performance.")
        st.caption(f"Average precision: {score['average_precision']:.3f} · Failure prevalence: {score['prevalence']:.1%}. "
                   "Average precision summarizes ranking quality across thresholds; higher is better.")

    with st.expander("Explore threshold trade-offs and inspect mistakes", expanded=False):
        st.caption("Preview only. Changing this control does not change the saved threshold or predictions elsewhere in the app.")
        percent = st.slider("Preview failure threshold (%)", min_value=1, max_value=99,
                            value=min(99, max(1, round(threshold*100))), step=1, key="evaluation_threshold")
        preview = percent/100
        simulated = evaluation.summarize(rows["Actual failure"], rows["Failure probability"], preview)
        cols = st.columns(3)
        for col,label,key in zip(cols,["Caught at preview", "Missed at preview", "False alarms at preview"],["caught","missed","false_alarms"]):
            col.metric(label,str(simulated[key]),border=True)
        st.caption(f"Live threshold remains {threshold:.0%}. Lower thresholds usually catch more failures and generate more false alarms.")
        tradeoffs = evaluation.threshold_table(rows, threshold)
        st.dataframe(tradeoffs,hide_index=True,height=230,alt="Validation counts and precision recall at different preview thresholds")
        filter_name = st.selectbox("Inspect outcomes", ["All mistakes", "Missed failure", "False alarm", "Caught failure", "Correct normal", "All rows"], key="evaluation_outcome")
        details = evaluation.outcomes(rows, preview)
        if filter_name == "All mistakes":
            details = details[details["Outcome"].isin(["Missed failure", "False alarm"])]
        elif filter_name != "All rows":
            details = details[details["Outcome"].eq(filter_name)]
        st.caption(f"{len(details):,} matching snapshots · Dataset row is the CSV line number, not a machine ID.")
        st.dataframe(details,hide_index=True,height=260,alt="Validation snapshots with operating inputs, actual labels, probabilities, and outcome")
        st.download_button("Export inspected snapshots", details.to_csv(index=False), file_name="validation-inspection.csv", mime="text/csv")

    with st.expander("Evaluation evidence and next test", expanded=False):
        st.markdown("**Independent final test: not available.** The notebook trained on 8,000 rows and used the other 2,000 to compare models and choose a threshold.")
        st.markdown("For the next training experiment, separate training, threshold-selection validation, and final evaluation data before fitting. Fit preprocessing only on training data; freeze the model and threshold before scoring the final split. A new split of this already-explored dataset is an internal experiment, not new external evidence.")
        st.caption("The AI4I data is synthetic. Fresh labeled operating data, separated by machine or time where appropriate, is needed to assess deployment performance. Live prediction history has no outcome labels yet and cannot serve as a test set.")
        import json
        report = {"model_version":version,"dataset":"AI4I 2020 local CSV", "split":"stratified 80/20; seed 42",
                  "evaluation_type":"validation replay; reused for threshold selection", "independent_final_test":False,
                  "metrics":score, "limitations":["Synthetic data", "Threshold-selection bias", "No independently collected labeled test data"]}
        st.download_button("Download evaluation report",json.dumps(report,indent=2),file_name="evaluation-report.json",mime="application/json")


def datasets():
    ui.heading("Datasets", "Inspect the data behind your machine intelligence.", "DATA / LIBRARY")
    source=st.segmented_control("Dataset source",["Reference dataset","Upload dataset"],default="Reference dataset",label_visibility="collapsed")
    if source=="Upload dataset":
        upload=st.file_uploader("Upload an operating dataset",type=["csv"],key="dataset_upload")
        if upload:
            try:
                frame=read_upload(upload)
                st.session_state["uploaded_dataset"]=frame
                st.success(f"Dataset validated · {len(frame):,} rows")
            except Exception as exc:
                st.error(str(exc))
                return
        else:
            ui.empty("Bring your operating data", "Upload a CSV using the six machine-input columns. Use the template from Run prediction → CSV batch.", "database")
            return
    else:
        frame=api.dataset()
    cols=st.columns(4)
    cols[0].metric("Rows",f"{len(frame):,}",border=True)
    cols[1].metric("Columns",str(len(frame.columns)),border=True)
    cols[2].metric("Missing cells",f"{frame.isna().sum().sum():,}",border=True)
    cols[3].metric("Machine types",str(frame["Type"].nunique()),border=True)
    with st.container(border=True):
        ui.section("Data explorer","Filter, sort, and inspect operating snapshots","database","AI4I 2020" if source=="Reference dataset" else "SESSION UPLOAD")
        a,b=st.columns([2,1])
        search=a.text_input("Search data",placeholder="Search any cell…",key="dataset_search")
        kind=b.multiselect("Machine type",["L","M","H"],default=["L","M","H"])
        filtered=frame[frame["Type"].isin(kind)]
        if search:
            filtered=filtered[filtered.astype(str).apply(lambda col:col.str.contains(search,case=False,regex=False)).any(axis=1)]
        st.caption(f"Showing {len(filtered):,} matching rows. Column headers sort; table headers remain visible while scrolling.")
        st.dataframe(filtered,hide_index=True,height=350,alt="Searchable machine operating dataset")
        st.download_button("Export filtered CSV",filtered.to_csv(index=False),file_name="machine-data.csv",mime="text/csv")
    if source=="Upload dataset":
        if st.button("Use in batch prediction  →",type="primary"):
            st.session_state["batch_dataset"]=frame
            st.session_state["input_mode"]="CSV batch"
            st.switch_page("app_pages/predict.py")
    else:
        st.caption("Source: local ai4i2020.csv · Synthetic predictive-maintenance reference dataset. Failure labels are available for validation, not production monitoring.")


def settings():
    ui.heading("Workspace settings", "A focused environment, tuned to you.", "WORKSPACE / PREFERENCES")
    left,right=st.columns([1.3,1])
    with left,st.container(border=True):
        ui.section("Appearance","Dark by default. A lighter view when you need it.","settings")
        st.toggle("Use light appearance",key="light_mode",on_change=lambda:None)
        st.caption("Applies immediately and remains active for this browser session. Charts follow the selected appearance.")
        st.divider()
        ui.section("Operator profile","Local workspace identity · no sign-in required","shield")
        with st.form("preferences",border=False):
            name=st.text_input("Display name",value=st.session_state.get("operator_name","Local operator"),max_chars=60)
            notifications=st.checkbox("Show high-risk run notifications",value=st.session_state.get("show_alerts",True))
            if st.form_submit_button("Save preferences",type="primary"):
                st.session_state["operator_name"]=name.strip() or "Local operator"
                st.session_state["show_alerts"]=notifications
                st.toast("Workspace preferences saved.")
        st.caption("Preferences are session-local. Prediction history persists on this computer.")
    with right,st.container(border=True):
        ui.section("Inference configuration","Current model connection","cpu")
        _,threshold,version=api.assets()
        ui.key_values([("Provider","Local saved pipeline"),("Artifact version",version),("Failure threshold",f"{threshold:.0%}"),("Medium watch band",f"{threshold/2:.0%}–{threshold:.0%}"),("Batch limit","5,000 rows / 10 MB"),("Time zone","Asia/Kolkata"),("Storage","Local SQLite")])
        st.caption("The decision threshold comes from the saved model artifact. Change it only after validation in the training workflow.")
        st.divider()
        ui.section("Keyboard shortcuts","Navigate without leaving the keyboard","layers")
        ui.key_values([("Search workspace","Ctrl / Cmd + K"),("New prediction","Ctrl / Cmd + Shift + P"),("Close dialog","Esc"),("Move between controls","Tab / Shift + Tab")])
