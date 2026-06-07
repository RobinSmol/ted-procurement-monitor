"""Streamlit page — company profile creation and editing."""
import json
import uuid
from datetime import datetime

import pandas as pd
import streamlit as st

from src.core.enums import ProfileField
from src.resources import load_databases

db, _, _, _, _ = load_databases()

st.title("🏢 Company Profiles")
st.caption(
    "Define your company's procurement profile. "
    "The search engine will score every tender against your full business context — "
    "not just a single keyword."
)

EUROPEAN_COUNTRIES = [
    "AUT",
    "BEL",
    "BGR",
    "HRV",
    "CYP",
    "CZE",
    "DNK",
    "EST",
    "FIN",
    "FRA",
    "DEU",
    "GRC",
    "HUN",
    "IRL",
    "ITA",
    "LVA",
    "LTU",
    "LUX",
    "MLT",
    "NLD",
    "POL",
    "PRT",
    "ROU",
    "SVK",
    "SVN",
    "ESP",
    "SWE",
    "CHE",
    "NOR",
    "ISL",
]

DEFAULT_PROFILE = {
    "keywords": [
        "laser cutting system industrial",
        "laser welding machine manufacturing",
        "sheet metal processing equipment",
        "CNC punching machine tool",
        "laser marking engraving system",
        "photonics laser source industrial",
        "bending machine sheet metal",
        "fiber laser system high power",
        "additive manufacturing metal powder",
        "laser beam welding automation",
    ],
    "negative_keywords": [
        "catering",
        "road construction",
        "cleaning services",
        "building maintenance",
        "waste management",
        "landscaping",
        "security services",
        "medical imaging",
        "flow cytometer",
        "office furniture",
        "multifunction printer",
        "chromatography",
    ],
    "preferred_countries": ["DEU", "CHE", "FRA", "NLD", "BEL", "AUT", "SWE", "DNK"],
    "cpv_codes": [
        "42600000",
        "42610000",
        "42621000",
        "42900000",
        "42990000",
        "38636100",
        "38636110",
    ],
}


def _init_profile_state() -> None:
    """Initializes company profile form session state keys with default values.

    Pre-populates profile name, keyword table, negative keyword table, CPV
    code table, and preferred countries using the built-in DEFAULT_PROFILE
    values. Uses setdefault-style logic so existing values — including those
    loaded by the edit flow — are never overwritten on rerun.
    """
    if "profile_name" not in st.session_state:
        st.session_state["profile_name"] = "ExampleLaserCo"
    if "profile_keywords_df" not in st.session_state:
        st.session_state["profile_keywords_df"] = pd.DataFrame(
            {"Keyword": pd.Series(DEFAULT_PROFILE["keywords"], dtype=str)}
        )
    if "profile_neg_keywords_df" not in st.session_state:
        default_neg_keywords = DEFAULT_PROFILE["negative_keywords"]
        st.session_state["profile_neg_keywords_df"] = pd.DataFrame(
            {"Negative Keyword": pd.Series(default_neg_keywords, dtype=str)}
        )
    if "profile_cpv_df" not in st.session_state:
        st.session_state["profile_cpv_df"] = pd.DataFrame(
            {"CPV Code": pd.Series(DEFAULT_PROFILE["cpv_codes"], dtype=str)}
        )

    if "profile_countries" not in st.session_state:
        default_countries = DEFAULT_PROFILE["preferred_countries"]
        st.session_state["profile_countries"] = default_countries
    if "editing_profile_id" not in st.session_state:
        st.session_state["editing_profile_id"] = None


def render_existing_profiles(db) -> None:
    """Renders the list of all saved company profiles.

    Displays each profile in a collapsible expander showing its keywords,
    negative keywords, preferred countries, and CPV codes. Provides Edit
    and Delete buttons per profile. Edit loads the profile into form session
    state and triggers a rerun to populate the form below.

    Args:
        db: Storage backend used to retrieve, update, and delete profiles.
    """
    st.subheader("My Profiles")
    profiles = db.get_all_profiles()

    if not profiles:
        st.info("No profiles yet. Create one below.")
        return

    for profile in profiles:
        with st.expander(f"🏢 {profile[ProfileField.NAME]}"):
            col1, col2, col3 = st.columns([3, 1, 1])

            keywords = json.loads(profile.get(ProfileField.KEYWORDS) or "[]")
            neg_keywords = json.loads(
                profile.get(ProfileField.NEGATIVE_KEYWORDS) or "[]"
            )
            countries = json.loads(
                profile.get(ProfileField.PREFERRED_COUNTRIES) or "[]"
            )
            cpv_codes = json.loads(profile.get(ProfileField.CPV_CODES) or "[]")

            with col1:
                st.markdown(f"**Keywords:** {', '.join(keywords) or 'None'}")
                st.markdown(
                    f"**Negative keywords:** {', '.join(neg_keywords) or 'None'}"
                )
                st.markdown(
                    f"**Preferred countries:** {', '.join(countries) or 'None'}"
                )
                st.markdown(f"**CPV codes:** {', '.join(cpv_codes) or 'None'}")

            with col2:
                if st.button("✏️ Edit", key=f"edit_{profile[ProfileField.ID]}"):
                    st.session_state["editing_profile_id"] = profile[ProfileField.ID]
                    st.session_state["profile_name"] = profile[ProfileField.NAME]
                    st.session_state["profile_keywords_df"] = pd.DataFrame(
                        {"Keyword": pd.Series(keywords, dtype=str)}
                    )
                    st.session_state["profile_neg_keywords_df"] = pd.DataFrame(
                        {"Negative Keyword": pd.Series(neg_keywords, dtype=str)}
                    )
                    st.session_state["profile_cpv_df"] = pd.DataFrame(
                        {"CPV Code": pd.Series(cpv_codes, dtype=str)}
                    )
                    st.session_state["profile_countries"] = countries
                    st.rerun()

            with col3:
                if st.button("🗑️ Delete", key=f"del_{profile[ProfileField.ID]}"):
                    db.delete_profile(profile[ProfileField.ID])
                    st.rerun()


def render_profile_form(db) -> None:
    """Renders the create or edit form for a company profile.

    Handles both create and update flows depending on whether
    editing_profile_id is set in session state. Displays editable tables
    for keywords, negative keywords, and CPV codes alongside a country
    multiselect and a name input. Validates that at least one keyword is
    present and all CPV codes are exactly 8 digits before persisting.
    Clears form state and reruns on success.

    Args:
        db: Storage backend used to save or update the profile record.
    """
    editing_id = st.session_state.get("editing_profile_id")
    st.subheader("Edit Profile" if editing_id else "Create New Profile")

    name = st.text_input(
        "Profile name (e.g. company name)",
        value=st.session_state["profile_name"],
        key="profile_name_input",
        placeholder="e.g. Nanoscribe GmbH",
    )
    st.session_state["profile_name"] = name

    st.markdown("**Keywords** — what your company sells or what you're looking for")
    st.caption(
        "Each keyword is embedded independently. "
        "A tender matches if it is close to ANY keyword. "
        "Be specific: 'two-photon lithography' is better than 'equipment'."
    )
    keywords_df = st.data_editor(
        st.session_state["profile_keywords_df"],
        num_rows="dynamic",
        key="profile_keywords_editor",
        column_config={
            "Keyword": st.column_config.TextColumn(
                "Keyword",
                help="e.g. 'high-precision 3D printer', 'optical lithography system'",
            )
        },
    )
    st.session_state["profile_keywords_df"] = keywords_df

    st.markdown("**Negative Keywords** — terms that indicate irrelevant tenders")
    st.caption(
        "If any negative keyword appears in a tender's title or description, "
        "the score is heavily penalized. "
        "e.g. 'catering', 'road construction', 'cleaning services'."
    )
    neg_df = st.data_editor(
        st.session_state["profile_neg_keywords_df"],
        num_rows="dynamic",
        key="profile_neg_editor",
        column_config={
            "Negative Keyword": st.column_config.TextColumn(
                "Negative Keyword",
                help="e.g. 'cleaning', 'catering', 'road works'",
            )
        },
    )
    st.session_state["profile_neg_keywords_df"] = neg_df

    st.markdown("**Preferred Countries** — tenders from these countries score higher")
    countries = st.multiselect(
        "Select preferred countries (ISO-3 codes)",
        options=EUROPEAN_COUNTRIES,
        default=st.session_state["profile_countries"],
        key="profile_countries_select",
    )
    st.session_state["profile_countries"] = countries

    st.markdown("**CPV Codes** — hard filter, only show tenders in these categories")
    cpv_df = st.data_editor(
        st.session_state["profile_cpv_df"],
        num_rows="dynamic",
        key="profile_cpv_editor",
        column_config={
            "CPV Code": st.column_config.TextColumn(
                "CPV Code",
                help="8-digit CPV code e.g. 38000000",
                max_chars=8,
            )
        },
    )
    st.session_state["profile_cpv_df"] = cpv_df

    col1, col2 = st.columns([1, 4])
    with col1:
        save_label = "💾 Update Profile" if editing_id else "💾 Save Profile"
        if st.button(save_label):
            if not name:
                st.error("Profile name is required.")
                return

            keywords = [k for k in keywords_df["Keyword"].dropna().tolist() if k]
            if not keywords:
                st.error("At least one keyword is required.")
                return

            neg_keywords = [
                k for k in neg_df["Negative Keyword"].dropna().tolist() if k
            ]
            cpv_list = [c for c in cpv_df["CPV Code"].dropna().tolist() if c]

            invalid_cpv = [c for c in cpv_list if not c.isdigit() or len(c) != 8]
            if invalid_cpv:
                st.error(f"Invalid CPV codes: {', '.join(invalid_cpv)}")
                return

            profile = {
                ProfileField.ID: editing_id or str(uuid.uuid4()),
                ProfileField.NAME: name,
                ProfileField.KEYWORDS: json.dumps(keywords),
                ProfileField.NEGATIVE_KEYWORDS: json.dumps(neg_keywords),
                ProfileField.PREFERRED_COUNTRIES: json.dumps(countries),
                ProfileField.CPV_CODES: json.dumps(cpv_list) if cpv_list else None,
                ProfileField.CREATED_AT: datetime.now().strftime("%Y%m%d"),
            }

            if editing_id:
                db.update_profile(
                    editing_id,
                    {k: v for k, v in profile.items() if k != ProfileField.ID},
                )
                st.success(f"✅ Profile '{name}' updated!")
            else:
                db.save_profile(profile)
                st.success(f"✅ Profile '{name}' saved!")

            # Reset form
            for key in [
                "profile_name",
                "editing_profile_id",
                "profile_countries",
                "profile_keywords_df",
                "profile_neg_keywords_df",
                "profile_cpv_df",
            ]:
                st.session_state.pop(key, None)
            st.rerun()

    with col2:
        if editing_id and st.button("❌ Cancel Edit"):
            for key in [
                "editing_profile_id",
                "profile_name",
                "profile_countries",
                "profile_keywords_df",
                "profile_neg_keywords_df",
                "profile_cpv_df",
            ]:
                st.session_state.pop(key, None)
            st.rerun()


_init_profile_state()
render_existing_profiles(db)
st.divider()
render_profile_form(db)
