from abc import ABC, abstractmethod


class BaseTransformer(ABC):
    """Abstract base class for all source-specific notice transformers.

    Each data source (TED, BOAMP, etc.) has its own raw API format.
    Subclasses implement normalize() to map that raw format into a
    StandardNotice-compatible dictionary, isolating parsing logic
    from the rest of the pipeline.
    """

    def __init__(self, source_name: str) -> None:
        """Initializes the transformer with a source identifier.

        Args:
            source_name: Human-readable name for the data source
                (e.g. "TED_API", "BOAMP").
        """
        self.source_name = source_name

    @abstractmethod
    def normalize(self, raw_notice: dict) -> dict | None:
        """Normalizes a raw API notice into a StandardNotice-compatible dict.

        Args:
            raw_notice: The raw notice payload as returned by the source API.

        Returns:
            A dictionary whose keys match StandardNotice field names,
            or None if the notice is malformed and should be discarded.
        """
        pass
