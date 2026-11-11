"""Prediction Model: application shell, navigation and shared workspace controls."""
from pathlib import Path
import sys
import importlib
from html import escape

# Resolve imports and assets independently of the launch directory.
APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import streamlit as st

# Refresh edited local helpers in long-lived previews. A normal run reuses them.
for module_name in ["evaluation", "monitoring", "services", "ui", "reports", "views"]:
    module = importlib.import_module(module_name)
    stamp = Path(module.__file__).stat().st_mtime_ns
    if getattr(module, "_preview_source_stamp", None) != stamp:
        module = importlib.reload(module)
        module._preview_source_stamp = stamp
import monitoring
import services as api
import ui

st.set_page_config(page_title="Prediction Model", page_icon=":material/monitoring:", layout="wide", initial_sidebar_state="auto")
for key, default in {"light_mode":False, "demo_mode":True, "operator_name":"Local operator", "show_alerts":True}.items():
    st.session_state.setdefault(key, default)
if st.session_state.pop("switch_to_live", False):
    st.session_state["demo_mode"] = False
ui.inject_style()

PAGES = [
    ("overview", "Overview", "grid"), ("predict", "Run prediction", "play"),
    ("history", "History", "history"), ("performance", "Model performance", "chart"),
    ("datasets", "Datasets", "database"), ("settings", "Settings", "settings"),
]
page = st.navigation([st.Page(f"app_pages/{slug}.py", title=label, url_path=slug, default=slug=="overview") for slug,label,_ in PAGES], position="hidden")

@st.dialog("Search workspace")
def command_palette():
    query = st.text_input("Find a screen", placeholder="Prediction, history, metrics…", key="command_query")
    matches = [(s,l,i) for s,l,i in PAGES if not query or query.casefold() in f"{s} {l} {'metrics accuracy validation' if s=='performance' else ''}".casefold()]
    for slug,label,icon in matches:
        if st.button(ui.icon_label(icon,label), key=f"command_{slug}", width="stretch"):
            st.switch_page(f"app_pages/{slug}.py")
    if not matches:
        st.caption("No screens match. Try prediction, history, or datasets.")

with st.sidebar:
    st.html(f'<div class="pm-brand"><div class="pm-brand-mark">{ui.svg("activity",size=23)}</div><div class="pm-brand-name">prediction<span>model</span></div></div><div class="pm-workspace"><div class="pm-avatar">PM</div><div><strong>Machine intelligence</strong><small>Local workspace</small></div></div>')
    st.html('<div class="pm-navlabel">WORKSPACE</div>')
    for slug,label,icon in PAGES[:3]:
        with st.container(key=f"nav_{slug}"):
            st.page_link(f"app_pages/{slug}.py",label=ui.icon_label(icon,label))
    st.html('<div class="pm-navlabel">MANAGE</div>')
    for slug,label,icon in PAGES[3:]:
        with st.container(key=f"nav_{slug}"):
            st.page_link(f"app_pages/{slug}.py",label=ui.icon_label(icon,label))
    st.space("medium")
    st.toggle("Demo overview feed", key="demo_mode", help="Illustrative timeline from reference data. Demo predictions are never saved to History.")
    st.caption("Preview data is labeled throughout.")
    try:
        _, threshold, version = api.assets()
        st.html(f'<div class="pm-side-status"><span class="pm-dot"></span> Model connected<p>XGBoost · {version}</p><p>Local inference / {threshold:.0%} threshold</p></div>')
    except Exception:
        st.error("Model unavailable. Check the local model files.")

current_slug = next(s for s,l,_ in PAGES if l == page.title)
st.html(f'<style>.st-key-nav_{current_slug} a {{background:color-mix(in srgb,var(--pm-accent) 9%,transparent)!important;border:1px solid color-mix(in srgb,var(--pm-accent) 20%,transparent)!important;}} .st-key-nav_{current_slug} p {{color:var(--pm-accent)!important;}}</style>')

with st.container(key="topbar"):
    breadcrumb, search, bell, profile = st.columns([2.2,2,1,1.1], vertical_alignment="center")
    breadcrumb.html(f'<div class="pm-topbar">Workspace <span>/</span><strong>{escape(page.title)}</strong></div>')
    with search:
        if st.button("Search workspace",key="search",shortcut="Ctrl+K",width="stretch"):
            command_palette()
    with bell, st.popover("Alerts", width="stretch"):
        st.markdown("**Workspace alerts**")
        if st.session_state.show_alerts:
            try:
                alerts = [s for s in monitoring.summarize(api.history()) if s["alerts"]]
                if alerts:
                    st.warning(f"{len(alerts)} machine(s) need attention.")
                    for machine in alerts[:3]:
                        st.caption(f"{machine['machine_id']} · {'; '.join(machine['alerts'])}")
                    st.page_link("app_pages/history.py", label="Review machine monitoring →")
                else:
                    st.caption("No machine alerts in saved assessments. Unassigned runs are excluded.")
            except Exception as exc:
                st.error(f"Could not read alerts: {exc}")
        else:
            st.caption("Machine notifications are muted in Settings.")
        st.caption("Alerts reflect saved assessments, not a live sensor feed.")
    with profile, st.popover("Operator",width="stretch"):
        st.markdown(f"**{escape(st.session_state.operator_name)}**")
        st.caption("Local workspace · session profile")
        st.page_link("app_pages/settings.py",label="Appearance & settings →")
# A keyboard-only action is available without adding a second primary action.
with st.container(key="quick_prediction"):
    if st.button("New prediction",shortcut="Ctrl+Shift+P",type="tertiary",key="quick_predict"):
        st.switch_page("app_pages/predict.py")
st.html('<style>.st-key-quick_prediction { position:absolute; width:1px; height:1px; overflow:hidden; clip-path:inset(50%); } .st-key-quick_prediction:focus-within { position:relative; width:auto; height:auto; clip-path:none; }</style>')

try:
    api.assets()
    page.run()
except Exception as exc:
    st.error(f"This view could not be loaded: {exc}")
    st.caption("Check that the saved model and reference dataset are available, then refresh the page.")

st.html('<div class="pm-footer"><span>prediction model / machine intelligence</span><span>Local inference · All times IST</span></div>')

