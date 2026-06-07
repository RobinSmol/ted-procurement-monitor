from typing import Protocol


class ReadStorageProtocol(Protocol):
    """Interface for read operations on the notice storage layer.

    Any class implementing this protocol can be used as a read-only
    data source by the search and UI layers, decoupling them from
    the concrete SQLite implementation.
    """

    def get_country_stats(self, ids: list[str] | None = None) -> list[dict]:
        """Returns notice counts grouped by country.

        Args:
            ids: Optional list of notice IDs to restrict the aggregation.
                 If None, aggregates across all stored notices.

        Returns:
            A list of dicts with country and total_notices keys.
        """
        ...

    def get_fetched_dates(self) -> set[str]:
        """Returns all dates that have already been queried from the API.

        Returns:
            A set of date strings in YYYYMMDD format.
        """
        ...

    def get_notices_by_ids(self, ids: list[str]) -> list[dict]:
        """Fetches full notice records for the given list of IDs.

        Args:
            ids: List of notice IDs to retrieve.

        Returns:
            A list of notice dictionaries matching the provided IDs.
        """
        ...

    def get_filtered_ids(
        self, cpv_codes: list[str] | None, start_date: str | None, end_date: str | None
    ) -> list[str]:
        """Returns notice IDs matching the provided hard filters.

        Args:
            cpv_codes: List of 8-digit CPV codes to filter on. None skips this filter.
            start_date: Start of publication date range in YYYYMMDD format.
                Requires end_date.
            end_date: End of publication date range in YYYYMMDD format.
                Requires start_date.

        Returns:
            List of matching notice IDs.
        """
        ...


class WriteStorageProtocol(Protocol):
    """Interface for write operations on the notice storage layer.

    Consumed by the pipeline to persist notices and track progress,
    without depending on any specific database implementation.
    """

    def save_notices(self, notices: list[dict]) -> None:
        """Persists a batch of normalized notices to storage.

        Args:
            notices: List of validated notice dictionaries to store.
        """
        ...

    def mark_date_as_fetched(self, date_str: str) -> None:
        """Records a date as having been queried from the API.

        Enables idempotent pipeline runs by preventing redundant
        API calls for dates already processed.

        Args:
            date_str: The date to mark, in YYYYMMDD format.
        """
        ...

    def get_todays_alerts(self) -> list[dict]:
        """Returns alerts scheduled to fire today.

        Returns:
            List of alert dicts scheduled for today.
        """
        ...

    def get_existing_ids(self, id_list: list[str]) -> list[str]:
        """Returns the subset of IDs that already exist in storage.

        Used by the pipeline deduplication step to filter out
        notices that have already been saved.

        Args:
            id_list: List of notice IDs to check.

        Returns:
            A list of IDs from id_list that are already stored.
        """
        ...

    def mark_alert_sent(self, alert_id: str) -> None:
        """Records today as the last send date for an alert.

        Args:
            alert_id: UUID of the alert to mark as sent.
        """
        ...


class SearchEngineProtocol(Protocol):
    """Interface for semantic indexing and search over notices.

    Decouples the search and pipeline layers from the concrete
    ChromaDB implementation, making the engine swappable.
    """

    def add_notices(self, notices: list[dict]) -> None:
        """Indexes a batch of notices into the search engine.

        Args:
            notices: List of validated notice dictionaries to index.
        """
        ...

    def search_multi_query(self, queries: list[str], k: int) -> dict[str, float]:
        """Finds the best semantic match per notice across multiple queries.

        Args:
            queries: List of keyword strings to search simultaneously.
            k: Number of candidates to retrieve per query.

        Returns:
            A dict mapping notice ID to its best similarity score (0 to 1).
        """
        ...

    def search(self, query: str, k: int) -> list[dict]:
        """Finds the k most semantically relevant notices for a query.

        Args:
            query: The natural language search query.
            k: The number of results to return.

        Returns:
            A list of dicts containing notice ID and similarity score.
        """
        ...
