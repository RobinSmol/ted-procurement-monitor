"""Streamlit home page — date range selection and data loading controls."""
import os
from datetime import datetime, timedelta

import streamlit as st

os.environ["TRANSFORMERS_VERBOSITY"] = "error"

from src.core.logger import setup_logger  # noqa: E402
from src.core.utils import get_date_range, get_missing_dates  # noqa: E402
from src.resources import load_databases  # noqa: E402

logger = setup_logger()

st.set_page_config(page_title="TED Explorer", page_icon="🌍", layout="wide")

db, chroma, pipeline, search_service, profile_search_service = load_databases()

st.title("🌍 European Public Market Dashboard")
st.markdown("Welcome. Use the sidebar to navigate between pages.")
st.markdown("Start by selecting a timeframe below to load tender data.")


def render_data_loading_section(db, pipeline) -> None:
    """Renders the data loading section on the home page.

    Displays a date range picker and compares the selected range against
    already-fetched dates. If gaps exist, shows a download button that
    runs the pipeline sequentially for each missing date with a live
    progress indicator.

    Args:
        db: Storage backend used to retrieve the set of already-fetched dates.
        pipeline: Data pipeline used to fetch and process each missing date.
    """
    st.subheader("Choose the working Timeframe:")

    today = datetime.now()
    seven_days_ago = today - timedelta(7)

    if "home_date_range" not in st.session_state:
        st.session_state["home_date_range"] = (seven_days_ago.date(), today.date())

    date_range = st.date_input(
        label="Data timeframe",
        value=st.session_state["home_date_range"],
        max_value=today,
        key="home_date_input",
    )

    if not isinstance(date_range, (list, tuple)) or len(date_range) != 2:
        st.info("Please select both a start and end date.")
        st.stop()

    st.session_state["home_date_range"] = date_range
    start, end = date_range

    wanted_dates = get_date_range(start, end)
    missing = get_missing_dates(wanted_dates, db.get_fetched_dates())

    if missing:
        st.info(f"{len(missing)} day(s) of data not yet downloaded.")
        if st.button("⬇️ Load missing data"):
            progress_bar = st.progress(0, text="Starting download...")
            for i, d in enumerate(missing):
                date_display = d.strftime("%Y-%m-%d")
                counter = f"{i + 1}/{len(missing)}"
                progress_bar.progress(
                    (i + 1) / len(missing),
                    text=f"Fetching {date_display} ({counter})...",
                )
                pipeline.run(d)
            progress_bar.empty()
            st.success("✅ All data loaded!")
            st.rerun()
    else:
        st.success("✅ All data for this period is already loaded.")


render_data_loading_section(db, pipeline)
