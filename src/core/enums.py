from enum import StrEnum


class NoticeField(StrEnum):
    """Field name constants shared across the entire pipeline."""

    ID = "id"
    TITLE = "title"
    PUB_DATE = "pub_date"
    COUNTRY = "country"
    ESTIMATED_VALUE = "estimated_value"
    DESCRIPTION = "description"
    CPV = "cpv"
    CURRENCY = "currency"
    ESTIMATED_VALUE_EUR = "estimated_value_eur"
    SOURCE_NAME = "source_name"


class StorageConfig(StrEnum):
    """Identifiers for all persistent storage resources."""

    DB_TABLE_NOTICES = "notices"
    DB_TABLE_FETCHED_DATES = "fetched_dates"
    DB_TABLE_ALERTS = "email_alerts"
    DB_TABLE_PROFILES = "company_profiles"
    CHROMA_COLLECTION = "ted_notices_embedded"
    FETCHED_DATES_COLUMN = "date"


class SourceNames(StrEnum):
    """Identifier for all different source names of the tenders."""

    TED = "TED_API"


class AlertField(StrEnum):
    """Field name constants for the email alert configuration table."""

    ID = "id"
    EMAIL = "email"
    QUERY = "query"
    CPV_CODES = "cpv_codes"
    THRESHOLD = "threshold"
    SEND_DAYS = "send_days"
    LAST_SENT = "last_sent"


class ProfileField(StrEnum):
    """Field name constants for the company profile table.

    A profile captures everything a company cares about when searching
    for tenders — not just a single query but a full business context.
    """

    ID = "id"
    NAME = "name"
    KEYWORDS = "keywords"
    NEGATIVE_KEYWORDS = "negative_keywords"
    PREFERRED_COUNTRIES = "preferred_countries"
    CPV_CODES = "cpv_codes"
    CREATED_AT = "created_at"
