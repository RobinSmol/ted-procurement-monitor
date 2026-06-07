"""Streamlit page — semantic search and profile-based search interface."""
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st
import json

from src.core.enums import NoticeField, ProfileField
from src.core.utils import date_to_api_str
from src.resources import load_databases
from src.ui.charts import display_publication_per_day

db, chroma, pipeline, search_service, profile_search_service = load_databases()

st.title("🔍 Semantic Search")

DISPLAY_COLUMNS = [
    NoticeField.ID,
    NoticeField.TITLE,
    NoticeField.COUNTRY,
    NoticeField.PUB_DATE,
    NoticeField.ESTIMATED_VALUE_EUR,
    NoticeField.CPV,
    "combined_score",
]


def _init_session_state() -> None:
    """Initializes search page session state keys with default values.

    Sets defaults for query string, threshold, date range, CPV code
    table, last results, last search parameters, selected IDs, and search
    mode. Uses setdefault-style logic so existing values are never
    overwritten on rerun.
    """
    today = datetime.now()
    seven_days_ago = today - timedelta(7)
    defaults = {
        "search_query": "",
        "search_threshold": 0.5,
        "search_date_range": (seven_days_ago.date(), today.date()),
        "search_cpv_df": pd.DataFrame(
            {
                "CPV Code": pd.Series(
                    [
                        "30232100",
                        "30232110",
                        "38000000",
                        "38341100",
                        "38636100",
                        "38636110",
                        "42610000",
                        "42900000",
                        "42990000",
                    ],
                    dtype=str,
                )
            }
        ),
        "last_results": None,
        "last_search_params": {},
        "selected_ids": [],
        "search_mode": "Manual Search",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _render_threshold_help(threshold: float) -> None:
    """Renders a contextual caption beneath the relevance threshold slider.

    Maps threshold ranges to color-coded guidance messages to help users
    understand the trade-off between precision and recall at the current
    setting.

    Args:
        threshold: Current threshold value from the relevance slider.
    """
    if threshold < 0.3:
        st.caption("🟡 Very broad — shows almost everything, expect noise.")
    elif threshold < 0.5:
        st.caption("🟢 Broad — good for exploration and discovering new categories.")
    elif threshold < 0.7:
        st.caption("🔵 Balanced — recommended default for daily use.")
    else:
        st.caption("🔴 Strict — only strong matches. Good for focused alerts.")


def render_search_section() -> None:
    """Renders the full search interface, handling both search modes.

    Displays a mode selector (Manual Search or any saved company profile),
    a date range picker, a recency toggle, and a relevance threshold slider.
    In profile mode, runs ProfileSearchService with multi-keyword scoring.
    In manual mode, exposes a CPV code editor and a free-text query field
    backed by SearchService. Shared result display covers metrics, a preview
    table, a publication-per-day chart, a full results expander, and a
    shortcut to save the current search as an alert.
    """
    _init_session_state()

    profiles = db.get_all_profiles()
    profile_names = ["Manual Search"] + [p[ProfileField.NAME] for p in profiles]

    search_mode = st.selectbox(
        "Search mode",
        options=profile_names,
        index=profile_names.index(st.session_state["search_mode"])
        if st.session_state["search_mode"] in profile_names
        else 0,
        key="search_mode_select",
        help="Select a company profile for intelligent multi-keyword matching, "
        "or use Manual Search for a custom query.",
    )
    st.session_state["search_mode"] = search_mode

    today = datetime.now()
    date_range = st.date_input(
        label="Date range",
        value=st.session_state["search_date_range"],
        max_value=today,
        key="search_date_input",
    )

    if not isinstance(date_range, (list, tuple)) or len(date_range) != 2:
        st.info("Please select both a start and end date.")
        st.stop()

    use_recency = st.checkbox(
        "Boost recent tenders",
        value=True,
        help="When enabled, recent tenders score higher than older ones. "
        "Disable to rank purely by relevance when searching historical data.",
    )

    st.session_state["search_date_range"] = date_range
    start, end = date_range

    threshold = st.slider(
        label="Relevance threshold",
        min_value=0.0,
        max_value=1.0,
        value=st.session_state["search_threshold"],
        key="search_threshold_widget",
    )
    st.session_state["search_threshold"] = threshold
    _render_threshold_help(threshold)

    if search_mode != "Manual Search":
        selected_profile = next(
            (p for p in profiles if p[ProfileField.NAME] == search_mode), None
        )
        if selected_profile:
            keywords = json.loads(
                selected_profile.get(ProfileField.KEYWORDS) or "[]"
            )
            st.caption(f"Keywords: {', '.join(keywords)}")

        if st.button("🔍 Search with Profile"):
            with st.spinner("Running profile-based search..."):
                results = profile_search_service.search(
                    profile=selected_profile,
                    k=200,
                    threshold=threshold,
                    start_date=date_to_api_str(start),
                    end_date=date_to_api_str(end),
                    use_recency=use_recency,
                )
            st.session_state["last_results"] = results
            st.session_state["last_search_params"] = {
                "query": f"[Profile] {search_mode}",
                "cpv_codes": [],
                "threshold": threshold,
            }
            st.session_state["selected_ids"] = [
                n[NoticeField.ID] for n in results.notices
            ]

    else:
        edited_df = st.data_editor(
            st.session_state["search_cpv_df"],
            num_rows="dynamic",
            key="search_cpv_editor",
            column_config={
                "CPV Code": st.column_config.TextColumn(
                    "CPV Code",
                    help="8-digit CPV code e.g. 72000000",
                    max_chars=8,
                )
            },
        )
        st.session_state["search_cpv_df"] = edited_df

        search = st.text_input(
            "Search query (natural language)",
            value=st.session_state["search_query"],
            key="search_query_input",
            placeholder="e.g. laboratory equipment, IT consulting...",
        )
        st.session_state["search_query"] = search

        if st.button("🔍 Start Search"):
            cpv_codes = [c for c in edited_df["CPV Code"].dropna().tolist() if c]
            cpv_codes = cpv_codes if cpv_codes else None

            with st.spinner("Searching..."):
                results = search_service.search(
                    query=search,
                    k=500,
                    threshold=threshold,
                    cpv_codes=cpv_codes,
                    start_date=date_to_api_str(start),
                    end_date=date_to_api_str(end),
                    use_recency=use_recency,
                )

            st.session_state["last_results"] = results
            st.session_state["last_search_params"] = {
                "query": search,
                "cpv_codes": cpv_codes or [],
                "threshold": threshold,
            }
            st.session_state["selected_ids"] = [
                n[NoticeField.ID] for n in results.notices
            ]

    results = st.session_state.get("last_results")

    if results is not None:
        if not results.notices:
            st.warning(
                "No relevant results found. "
                "Try lowering the threshold or broadening your profile keywords."
            )
        else:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(label="Results", value=results.total_count)
            with col2:
                st.metric(
                    label=f"Total value ({results.valid_eur_count} tenders)",
                    value=f"€{results.total_eur_value:,.0f}"
                    if results.total_eur_value
                    else "N/A",
                )
            with col3:
                st.metric(
                    label=f"Average value ({results.valid_eur_count} tenders)",
                    value=f"€{results.average_eur_value:,.0f}"
                    if results.average_eur_value
                    else "N/A",
                )

            display_cols = [c for c in DISPLAY_COLUMNS if c in results.notices[0]]
            st.dataframe(
                pd.DataFrame(results.notices[:10])[display_cols],
                width="stretch",
            )

            display_publication_per_day(results.notices)

            with st.expander(f"View all {results.total_count} results"):
                st.dataframe(
                    pd.DataFrame(results.notices)[display_cols],
                    width="stretch",
                )

            if st.button("🔔 Save as Alert"):
                params = st.session_state.get("last_search_params", {})
                st.session_state["alert_prefill"] = params
                st.switch_page("pages/03_alerts.py")


render_search_section()
