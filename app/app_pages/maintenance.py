import maintenance_views
import streamlit as st

if notice := st.session_state.pop("maintenance_notice", None):
    st.success(notice)
maintenance_views.page()
