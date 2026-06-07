from abc import ABC, abstractmethod
from datetime import date


class BaseExtractor(ABC):
    """Abstract base class for all data source extractors.

    Each data source (TED, BOAMP, etc.) must subclass this and implement
    fetch_daily_notices(). The pipeline operates against this interface,
    making new data sources pluggable without touching pipeline logic.

    Attributes:
        source_name: Human-readable identifier for the data source,
            used in logging throughout the pipeline.
    """

    def __init__(self, source_name: str) -> None:
        """Initializes the extractor with a source identifier.

        Args:
            source_name: Human-readable name for the data source
                (e.g. "TED_API", "BOAMP").
        """
        self.source_name = source_name

    @abstractmethod
    def fetch_daily_notices(self, date: date) -> list[dict]:
        """Fetches all notices published on the given date.

        Args:
            date: The target publication date to query.

        Returns:
            A list of normalized notice dictionaries compatible
            with StandardNotice field names.
        """
        pass
