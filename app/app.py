"""Prediction Model: operations-first navigation and shared workspace controls."""
from pathlib import Path
import sys
import importlib

APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import streamlit as st

st.set_page_config(page_title="Prediction Model", page_icon=":material/monitoring:", layout="wide", initial_sidebar_state="auto")
for module_name in ["evaluation", "monitoring", "maintenance", "services", "ui", "reports", "views", "maintenance_views"]:
    module = importlib.import_module(module_name)
    stamp = Path(module.__file__).stat().st_mtime_ns
    if getattr(module, "_preview_source_stamp", None) != stamp:
        module = importlib.reload(module)
        module._preview_source_stamp = stamp
import monitoring
import services as api
import ui

for key, default in {"light_mode": False, "demo_mode": False, "operator_name": "Local operator", "show_alerts": True}.items():
    st.session_state.setdefault(key, default)
if st.session_state.pop("switch_to_live", False):
    st.session_state["demo_mode"] = False
ui.inject_style()

PAGES = [
    ("overview", "Overview", "dashboard"), ("predict", "Run prediction", "play_arrow"),
    ("history", "Machines & history", "history"), ("maintenance", "Maintenance", "build"),
    ("performance", "Model performance", "analytics"), ("datasets", "Datasets", "database"),
    ("settings", "Settings", "settings"),
]
page = st.navigation([
    st.Page(f"app_pages/{slug}.py", title=label, icon=f":material/{icon}:",
            url_path=slug, default=slug == "overview") for slug, label, icon in PAGES
], position="hidden")

@st.dialog("Search workspace")
def command_palette():
    query = st.text_input("Find a screen", placeholder="Machine, prediction, maintenance…", key="command_query")
    matches = [(s, l, i) for s, l, i in PAGES if not query or query.casefold() in f"{s} {l} {'metrics accuracy validation' if s == 'performance' else ''}".casefold()]
    for slug, label, icon in matches:
        if st.button(label, icon=f":material/{icon}:", key=f"command_{slug}", width="stretch"):
            st.switch_page(f"app_pages/{slug}.py")
    if not matches:
        st.caption("No screens match. Try prediction, history, or maintenance.")

with st.sidebar:
    st.subheader("Prediction Model", icon=":material/monitoring:")
    st.caption("Maintenance workspace")
    if st.button("New assessment", type="primary", icon=":material/add:", key="quick_predict", shortcut="Ctrl+Shift+P", width="stretch"):
        st.switch_page("app_pages/predict.py")
    for group, pages in [("OPERATIONS", PAGES[:4]), ("MODEL & DATA", PAGES[4:6]), ("PREFERENCES", PAGES[6:])]:
        st.caption(group)
        for slug, label, icon in pages:
            st.page_link(f"app_pages/{slug}.py", label=label, icon=f":material/{icon}:")
    st.space("medium")
    with st.container(border=True):
        try:
            _, threshold, version = api.assets()
            st.caption("LOCAL MODEL")
            st.markdown("**XGBoost**")
            st.caption(f"Failure threshold {threshold:.0%} · {version}")
        except Exception:
            st.error("Model unavailable. Check the saved model files.")
    st.caption("Saved assessments · no live feed")

with st.container(key="topbar"):
    breadcrumb, actions = st.columns([2, 1], vertical_alignment="center")
    breadcrumb.caption(f"Workspace / {page.title}")
    with actions, st.container(horizontal=True, horizontal_alignment="right"):
        if st.button("Search", icon=":material/search:", key="search", shortcut="Ctrl+K"):
            command_palette()
        with st.popover("Alerts", icon=":material/notifications:"):
            st.markdown("**Machine alerts**")
            if st.session_state.show_alerts:
                try:
                    alerts = [s for s in monitoring.summarize(api.history()) if s["alerts"]]
                    if alerts:
                        st.warning(f"{len(alerts)} machine(s) need attention.")
                        for machine in alerts[:3]:
                            st.markdown(f"**{machine['machine_id']}**")
                            st.caption("; ".join(machine["alerts"]))
                        st.page_link("app_pages/history.py", label="Review machine histories")
                    else:
                        st.caption("No machine alerts in saved assessments. Sample and unassigned readings are excluded.")
                except Exception as exc:
                    st.error(f"Could not read alerts: {exc}")
            else:
                st.caption("Machine notifications are muted in Settings.")
            st.caption("Latest saved assessments, not a live sensor feed.")

try:
    api.assets()
    page.run()
except Exception as exc:
    st.error(f"This view could not be loaded: {exc}")
    st.caption("Check the saved model, dataset and local database, then refresh.")

st.caption("Prediction Model · Local inference · Assessment times in IST")

