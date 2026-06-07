"""Streamlit page — email alert creation and management."""
import json
import uuid

import pandas as pd
import streamlit as st

from src.core.enums import AlertField
from src.resources import load_databases

db, _, _, _, _ = load_databases()

st.title("🔔 Email Alerts")

DAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]


def _init_alert_session_state() -> None:
    """Initializes alert form session state keys with default values.

    Pre-fills email, query, CPV codes, and threshold from alert_prefill
    if the user arrived via the 'Save as Alert' button on the search page.
    Falls back to empty defaults otherwise. Uses setdefault-style logic
    so existing values are never overwritten on rerun.
    """
    if "alert_email" not in st.session_state:
        st.session_state["alert_email"] = ""
    if "alert_query" not in st.session_state:
        saved = st.session_state.get("alert_prefill", {})
        st.session_state["alert_query"] = saved.get("query", "")
    if "alert_cpv_df" not in st.session_state:
        saved = st.session_state.get("alert_prefill", {})
        default_cpv = saved.get("cpv_codes", [])
        st.session_state["alert_cpv_df"] = pd.DataFrame(
            {"CPV Code": pd.Series(default_cpv, dtype=str)}
        )
    if "alert_threshold" not in st.session_state:
        saved = st.session_state.get("alert_prefill", {})
        st.session_state["alert_threshold"] = float(saved.get("threshold", 0.5))


def render_existing_alerts(db) -> None:
    """Renders the list of all saved alert configurations.

    Displays each alert as a formatted row showing recipient email, query,
    CPV codes, scheduled send days, and last sent date. Provides a delete
    button per alert that removes it and reruns the page immediately.

    Args:
        db: Storage backend used to retrieve and delete alert records.
    """
    st.subheader("My Alerts")
    alerts = db.get_all_alerts()

    if not alerts:
        st.info("No alerts configured yet. Create one below.")
        return

    for alert in alerts:
        col1, col2 = st.columns([5, 1])
        with col1:
            cpv_display = ""
            if alert[AlertField.CPV_CODES]:
                codes = json.loads(alert[AlertField.CPV_CODES])
                cpv_display = f" — CPV: `{', '.join(codes)}`"
            st.markdown(
                f"📧 **{alert[AlertField.EMAIL]}** — "
                f"Query: `{alert[AlertField.QUERY] or 'None'}` "
                f"{cpv_display} — "
                f"Days: `{alert[AlertField.SEND_DAYS]}` — "
                f"Last sent: `{alert[AlertField.LAST_SENT] or 'Never'}`"
            )
        with col2:
            if st.button("🗑️", key=f"del_{alert[AlertField.ID]}", help="Delete alert"):
                db.delete_alert(alert[AlertField.ID])
                st.rerun()


def render_create_alert(db) -> None:
    """Renders the form for creating a new email alert.

    Collects recipient email, send-day checkboxes, search query, CPV codes,
    and relevance threshold. Validates all inputs before persisting, clears
    prefill state on success, and reruns the page to reflect the new alert.

    Args:
        db: Storage backend used to persist the new alert configuration.
    """
    st.subheader("Create New Alert")
    _init_alert_session_state()

    email = st.text_input(
        "Email address",
        value=st.session_state["alert_email"],
        key="alert_email_input",
    )
    st.session_state["alert_email"] = email

    st.write("Send on these days:")
    cols = st.columns(7)
    selected_days = []
    for i, day in enumerate(DAYS):
        with cols[i]:
            if st.checkbox(day, key=f"day_{day}"):
                selected_days.append(day)

    query = st.text_input(
        "Search query",
        value=st.session_state["alert_query"],
        key="alert_query_input",
        placeholder="e.g. laboratory equipment, IT services...",
    )
    st.session_state["alert_query"] = query

    edited_df = st.data_editor(
        st.session_state["alert_cpv_df"],
        num_rows="dynamic",
        key="alert_cpv_editor",
        column_config={
            "CPV Code": st.column_config.TextColumn(
                "CPV Code",
                help="8-digit CPV code e.g. 72000000",
                max_chars=8,
            )
        },
    )
    st.session_state["alert_cpv_df"] = edited_df

    threshold = st.slider(
        "Relevance threshold",
        min_value=0.0,
        max_value=1.0,
        value=st.session_state["alert_threshold"],
        key="alert_threshold_widget",
    )
    st.session_state["alert_threshold"] = threshold

    if st.button("💾 Save Alert"):
        if not email:
            st.error("Email address is required.")
            return
        if not selected_days:
            st.error("Select at least one send day.")
            return

        cpv_list = [c for c in edited_df["CPV Code"].dropna().tolist() if c]

        if not query and not cpv_list:
            st.error("Enter a search query or at least one CPV code.")
            return

        invalid = [c for c in cpv_list if not c.isdigit() or len(c) != 8]
        if invalid:
            st.error(
                f"Invalid CPV codes: {', '.join(invalid)}. "
                "CPV codes must be exactly 8 digits."
            )
            return

        alert = {
            AlertField.ID: str(uuid.uuid4()),
            AlertField.EMAIL: email,
            AlertField.QUERY: query or None,
            AlertField.CPV_CODES: json.dumps(cpv_list) if cpv_list else None,
            AlertField.THRESHOLD: threshold,
            AlertField.SEND_DAYS: ",".join(selected_days),
        }
        db.save_alert(alert)

        st.session_state.pop("alert_prefill", None)
        st.session_state.pop("alert_email", None)
        st.session_state.pop("alert_query", None)
        st.session_state.pop("alert_cpv_df", None)
        st.session_state.pop("alert_threshold", None)

        st.success("✅ Alert saved successfully!")
        st.rerun()


render_existing_alerts(db)
st.divider()
render_create_alert(db)
