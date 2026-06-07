"""Streamlit page — geographic distribution map of matched tenders."""
import streamlit as st

from src.resources import load_databases
from src.ui.charts import display_europe_map

db, _, _, _, _ = load_databases()

st.title("🗺️ European Distribution")


def render_map_section(db) -> None:
    """Renders the geographic distribution map for the current search results.

    Reads selected notice IDs from session state, queries country statistics
    for that subset, and displays them as a proportional bubble map scoped
    to Europe. Shows an info prompt if no search has been run yet.

    Args:
        db: Storage backend used to retrieve country statistics for the
            selected notice IDs.
    """
    st.subheader("Geographic distribution of results")

    ids = st.session_state.get("selected_ids", [])

    if not ids:
        st.info(
            "Run a search first on the Search page to see the geographic distribution."
        )
        return

    raw_data = db.get_country_stats(ids)
    if not raw_data:
        st.warning("No geographic data available for current results.")
        return

    display_europe_map(raw_data)


render_map_section(db)
