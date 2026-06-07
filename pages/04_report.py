"""Streamlit page — full alert report accessed via email link."""
import json
from datetime import date

import pandas as pd
import streamlit as st

from src.core.enums import AlertField, NoticeField
from src.core.utils import date_to_api_str
from src.resources import load_databases

db, _, _, search_service, _ = load_databases()

st.title("📊 Alert Report")

DISPLAY_COLUMNS = [
    NoticeField.ID,
    NoticeField.TITLE,
    NoticeField.COUNTRY,
    NoticeField.PUB_DATE,
    NoticeField.ESTIMATED_VALUE_EUR,
    NoticeField.CPV,
    "combined_score",
]


def render_report() -> None:
    """Renders a full search report for a specific alert.

    Reads the alert_id query parameter from the URL, retrieves the matching
    alert configuration, and reruns the saved search for the period between
    the alert's last send date and today. Displays result metrics, a full
    results table, and a back button to the main dashboard. Shows an error
    if the alert_id is missing or the alert has been deleted.
    """
    params = st.query_params
    alert_id = params.get("alert_id")

    if not alert_id:
        st.error("No alert ID provided. Please access this page via an alert email.")
        return

    alerts = db.get_all_alerts()
    alert = next((a for a in alerts if a[AlertField.ID] == alert_id), None)

    if not alert:
        st.error("Alert not found. It may have been deleted.")
        return

    st.subheader(f"Results for: `{alert[AlertField.QUERY] or 'No query'}`")
    st.caption(
        f"📧 {alert[AlertField.EMAIL]} — "
        f"Days: {alert[AlertField.SEND_DAYS]} — "
        f"Last sent: {alert[AlertField.LAST_SENT] or 'Never'}"
    )

    cpv_codes = (
        json.loads(alert[AlertField.CPV_CODES]) if alert[AlertField.CPV_CODES] else None
    )
    start_date = alert[AlertField.LAST_SENT] or date_to_api_str(date.today())
    end_date = date_to_api_str(date.today())

    with st.spinner("Loading results..."):
        results = search_service.search(
            query=alert[AlertField.QUERY] or "",
            cpv_codes=cpv_codes,
            start_date=start_date,
            end_date=end_date,
            threshold=alert[AlertField.THRESHOLD],
            k=200,
        )

    if not results.notices:
        st.info("No results found for this alert in the current period.")
        return

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Results", results.total_count)
    with col2:
        st.metric(
            f"Total value ({results.valid_eur_count} tenders)",
            f"€{results.total_eur_value:,.0f}" if results.total_eur_value else "N/A",
        )
    with col3:
        avg_display = (
            f"€{results.average_eur_value:,.0f}" if results.average_eur_value else "N/A"
        )
        st.metric(
            f"Average value ({results.valid_eur_count} tenders)",
            avg_display,
        )

    display_cols = [c for c in DISPLAY_COLUMNS if c in results.notices[0]]
    st.dataframe(
        pd.DataFrame(results.notices)[display_cols],
        width="stretch",
    )

    if st.button("🔙 Back to Dashboard"):
        st.switch_page("app.py")


render_report()
