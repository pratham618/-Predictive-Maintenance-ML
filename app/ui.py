"""Reusable display components and chart styling for Prediction Model."""
from pathlib import Path
from datetime import datetime
from html import escape
import base64
import altair as alt
import pandas as pd
import streamlit as st

# Lucide's open-source 24px stroke geometry, rendered locally (no icon CDN).
ICONS = {
    "activity": '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
    "grid": '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
    "play": '<polygon points="6 3 20 12 6 21 6 3"/>',
    "history": '<path d="M3 12a9 9 0 1 0 2.7-6.4L3 8"/><path d="M3 3v5h5M12 7v5l4 2"/>',
    "chart": '<path d="M3 3v18h18M7 14l4-4 4 3 6-7"/>',
    "database": '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14c0 1.7 4 3 9 3s9-1.3 9-3V5M3 12c0 1.7 4 3 9 3s9-1.3 9-3"/>',
    "settings": '<path d="M9 3h6l1 3 3 1 2 5-2 5-3 1-1 3H9l-1-3-3-1-2-5 2-5 3-1z"/><circle cx="12" cy="12" r="3"/>',
    "cpu": '<rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M9 1v3M15 1v3M9 20v3M15 20v3M1 9h3M1 15h3M20 9h3M20 15h3"/>',
    "search": '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    "bell": '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/>',
    "layers": '<path d="m12 3 10 5-10 5L2 8l10-5ZM2 12l10 5 10-5M2 16l10 5 10-5"/>',
    "shield": '<path d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11Z"/><path d="m9 12 2 2 4-4"/>',
}


def _svg(name, color="currentColor", size=20):
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{ICONS.get(name, ICONS["activity"])}</svg>'


def svg(name, color="currentColor", size=20):
    # CSS image avoids st.html's SVG sanitization, while remaining decorative.
    return f'<span class="pm-icon pm-icon-{name}" style="width:{size}px;height:{size}px" aria-hidden="true"></span>'


def icon_label(name, label):
    color = "#52657a" if st.session_state.get("light_mode") else "#97a3b7"
    uri = base64.b64encode(_svg(name, color).encode()).decode()
    return f"![](data:image/svg+xml;base64,{uri}) {label}"


def inject_style():
    css = (Path(__file__).parent / "styles.css").read_text(encoding="utf-8")
    if st.session_state.get("light_mode"):
        css += '\n:root {--pm-bg:#f4f6f9;--pm-surface:#ffffff;--pm-raised:#edf1f6;--pm-text:#182334;--pm-muted:#536276;--pm-border:#d8dfe8;--pm-accent:#08758b;--pm-accent-ink:#ffffff;--pm-secondary:#7466bc;--pm-green:#157448;--pm-amber:#8d580a;--pm-red:#b63143;}\n'
    color = "#08758b" if st.session_state.get("light_mode") else "#66cbb8"
    css += '\n.pm-icon { display:inline-block; flex-shrink:0; background-position:center; background-size:contain; background-repeat:no-repeat; }\n'
    for name in ICONS:
        uri = base64.b64encode(_svg(name, color).encode()).decode()
        css += f'.pm-icon-{name} {{ background-image:url("data:image/svg+xml;base64,{uri}"); }}\n'
    st.html(f"<style>{css}</style>")


def heading(title, subtitle, eyebrow="PREDICTIVE MAINTENANCE"):
    st.caption(eyebrow)
    st.title(title)
    st.caption(subtitle)


def section(title, subtitle="", icon="activity", chip=""):
    st.markdown(f"**{title}**")
    if subtitle or chip:
        st.caption(" · ".join(part for part in (subtitle, chip) if part))


def key_values(values):
    st.html(''.join(f'<div class="pm-kv"><span>{escape(str(k))}</span><span>{escape(str(v))}</span></div>' for k,v in values))


def empty(title, message, icon="activity"):
    st.html(f'<div class="pm-empty">{svg(icon, size=34)}<strong>{escape(title)}</strong>{escape(message)}</div>')


def note(message):
    st.html(f'<div class="pm-note">{escape(message)}</div>')


def chart_style(chart, height=220):
    light = st.session_state.get("light_mode", False)
    fg, grid = ("#536276", "#e1e6ed") if light else ("#97a3b7", "#242a35")
    return chart.properties(height=height, background="transparent").configure_view(strokeWidth=0).configure_axis(
        gridColor=grid, domain=False, tickColor=grid, labelColor=fg, titleColor=fg, labelFont="Segoe UI", titleFont="Segoe UI", titleFontWeight=400, labelFontSize=12, titleFontSize=12, labelPadding=9, titlePadding=12
    ).configure_legend(labelColor=fg, titleColor=fg, labelFont="Segoe UI", titleFont="Segoe UI", orient="bottom")


def risk_chart(records, threshold):
    df = pd.DataFrame({"Time": [r["timestamp"] for r in records], "Failure probability": [r["probability"] for r in records], "Run": [r["id"] for r in records]})
    df["Time"] = pd.to_datetime(df["Time"], utc=True, format="mixed").dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)
    base = alt.Chart(df.sort_values("Time")).encode(x=alt.X("Time:T", title=None, axis=alt.Axis(format="%d %b %H:%M", tickCount=4, labelOverlap=True)), y=alt.Y("Failure probability:Q", scale=alt.Scale(domain=[0,1]), axis=alt.Axis(format="%"), title=None))
    area = base.mark_area(color="#66cbb8", opacity=.08)
    line = base.mark_line(color="#66cbb8", strokeWidth=2, point=alt.OverlayMarkDef(size=18)).encode(tooltip=[alt.Tooltip("Time:T", format="%d %b %H:%M"), "Run:N", alt.Tooltip("Failure probability:Q", format=".1%")])
    rule = alt.Chart(pd.DataFrame({"Threshold": [threshold]})).mark_rule(color="#f4c16b", strokeDash=[4,5], opacity=.65).encode(y="Threshold:Q", tooltip=[alt.Tooltip("Threshold:Q", format=".0%")])
    st.altair_chart(chart_style(area + line + rule, 220), theme=None, alt="Failure probability by run time in IST. Dashed amber line is the saved failure threshold.")


def feature_chart(frame, local=True):
    value = "Contribution" if local else "Importance"
    colors = alt.Color("Effect:N", scale=alt.Scale(domain=["Raises risk", "Lowers risk"], range=["#ff8893", "#66cbb8"]), title=None) if local else alt.value("#66cbb8")
    chart = alt.Chart(frame).mark_bar(cornerRadiusEnd=3, size=13).encode(
        y=alt.Y("Feature:N", sort=frame["Feature"].tolist(), title=None, axis=alt.Axis(labelLimit=210)),
        x=alt.X(f"{value}:Q", title="Contribution to failure log-odds" if local else "Relative importance", axis=alt.Axis(format=".2f" if local else ".0%")),
        color=colors, tooltip=["Feature:N", alt.Tooltip(f"{value}:Q", format=".3f")])
    st.altair_chart(chart_style(chart, 220), theme=None, alt="Signed feature contributions to this prediction" if local else "Global model feature importance; larger bars indicate greater model use")


def gauge(probability, risk):
    st.metric("Failure probability", f"{probability:.1%}")
    st.progress(float(probability))
    st.badge(f"{risk} risk", color={"Low": "green", "Medium": "orange", "High": "red"}[risk])


def time_label(value):
    from services import IST
    stamp = datetime.fromisoformat(value)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=IST)
    return stamp.astimezone(IST).strftime("%d %b %Y · %H:%M IST")


def machine_table(summaries, key):
    frame = pd.DataFrame([{
        "Machine": s["machine_id"], "Risk": s["latest"]["risk"],
        "Failure probability": s["latest"]["probability"],
        "Assessment": time_label(s["latest"]["timestamp"]),
        "Alerts": "; ".join(s["alerts"]) or "No elevated risk in latest snapshot",
    } for s in summaries])
    st.dataframe(frame, key=key, hide_index=True, height=min(330, 40 + 36 * len(frame)),
                 column_config={"Failure probability": st.column_config.ProgressColumn(format="percent", min_value=0, max_value=1)},
                 alt="Latest saved machine risks, assessment times and alerts")


def runs_table(records, key, selectable=False, height=245):
    from services import table
    frame = table(records)
    if frame.empty:
        empty("No runs yet", "Run a prediction to start building your local history.", "history")
        return None
    kwargs = {"on_select": "rerun", "selection_mode": "single-row"} if selectable else {}
    return st.dataframe(frame, hide_index=True, width="stretch", height=height, key=key,
                        column_config={"Failure probability": st.column_config.ProgressColumn("Failure probability", format="percent", min_value=0,max_value=1),
                                       "Inference (ms)": st.column_config.NumberColumn(format="%.2f")},
                        alt="Prediction runs with risk, failure probability, source, and inference duration. Select a row for details.", **kwargs)
