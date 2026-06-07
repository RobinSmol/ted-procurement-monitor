from datetime import date, datetime, timedelta

from src.core.enums import NoticeField


def date_to_api_str(d: date) -> str:
    """Converts a date object to the YYYYMMDD string format expected by the TED API.

    Args:
        d: The date to convert.

    Returns:
        A string in YYYYMMDD format (e.g. "20260518").
    """
    return d.strftime("%Y%m%d")


def get_date_range(start: date, end: date) -> list[date]:
    """Generates a list of every date between start and end, inclusive.

    Args:
        start: The first date of the range.
        end: The last date of the range.

    Returns:
        An ordered list of date objects covering the full range.
    """
    return [start + timedelta(days=x) for x in range((end - start).days + 1)]


def get_missing_dates(wanted: list[date], downloaded: set[str]) -> list[date]:
    """Filters out dates that have already been downloaded.

    Compares a list of target dates against a set of already-fetched
    date strings to determine what still needs to be queried.

    Args:
        wanted: The full list of dates to check.
        downloaded: A set of already-fetched dates in YYYYMMDD string format.

    Returns:
        A list of dates from wanted that are absent from downloaded.
    """
    return [d for d in wanted if date_to_api_str(d) not in downloaded]


def extract_text_for_embedding(notice: dict) -> str:
    """Builds a single string from a notice for embedding generation.

    Concatenates title and description into one text block.
    Empty or missing fields default to an empty string to avoid
    breaking the embedding pipeline.

    Args:
        notice: A normalized notice dictionary.

    Returns:
        A space-separated string combining title and description.
    """
    title = notice.get(NoticeField.TITLE) or ""
    description = notice.get(NoticeField.DESCRIPTION) or ""
    return title + " " + description


def compute_recency_score(pub_date_str: str, decay_days: int = 30) -> float:
    """Computes a time-decay recency score for a notice publication date.

    Shared utility used by both SearchService and ProfileSearchService
    to ensure consistent recency scoring across search modes.

    Args:
        pub_date_str: Publication date in YYYYMMDD format.
        decay_days: Number of days over which the score decays to ~0.5.

    Returns:
        A recency score between 0.0 and 1.0.
    """
    try:
        date_obj = datetime.strptime(pub_date_str, "%Y%m%d").date()
    except (ValueError, TypeError):
        return 0.0
    days_old = (date.today() - date_obj).days
    return 1 / (1 + days_old / decay_days)
