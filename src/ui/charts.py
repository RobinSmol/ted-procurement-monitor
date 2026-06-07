from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st

from src.core.enums import NoticeField


def display_publication_per_day(relevant: list[dict]) -> None:
    """Renders a bar chart of notice publication volume per day.

    Aggregates the provided notices by publication date and displays
    the result as an interactive Plotly bar chart inside the Streamlit layout.

    Args:
        relevant: List of notice dicts, each containing a pub_date field
            in ISO format. Typically the output of SearchService.search().
    """
    dates = [datetime.fromisoformat(n[NoticeField.PUB_DATE]).date() for n in relevant]
    data = pd.DataFrame(dates, columns=[NoticeField.PUB_DATE])
    data["total"] = 1
    data = data.groupby(NoticeField.PUB_DATE)["total"].sum().reset_index()
    fig = px.bar(data, x=NoticeField.PUB_DATE, y="total", title="Publications per day")
    st.plotly_chart(fig)


def display_europe_map(raw_data: list[dict]) -> None:
    """Renders an interactive geographic bubble map scoped to Europe.

    Displays notice volume per country as proportional bubbles on a
    Plotly scatter_geo chart, styled to match the Streamlit dark theme.
    Renders an info message and returns early if no data is available.

    Args:
        raw_data: List of dicts with 'country' (ISO-3 code) and
            'total_notices' keys, typically from DBManager.get_country_stats().
    """
    df_map = pd.DataFrame(raw_data, columns=[NoticeField.COUNTRY, "total_notices"])
    if df_map.empty:
        st.info("No geographic data available.")
        return

    fig = px.scatter_geo(
        df_map,
        locations=NoticeField.COUNTRY,
        locationmode="ISO-3",
        size="total_notices",
        color="total_notices",
        color_continuous_scale=px.colors.sequential.Plasma,
        hover_name=NoticeField.COUNTRY,
        projection="natural earth",
    )

    fig.update_geos(
        scope="europe",
        showcountries=True,
        countrycolor="#555555",
        showland=True,
        landcolor="#262730",
        showocean=False,
        bgcolor="rgba(0,0,0,0)",
    )

    fig.update_layout(
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )

    st.plotly_chart(fig)
