from dataclasses import dataclass

from src.core.config import AppSettings
from src.core.enums import NoticeField
from src.core.interfaces import ReadStorageProtocol, SearchEngineProtocol
from src.core.utils import compute_recency_score


@dataclass
class SearchResults:
    """Aggregated output of a semantic search query.

    Holds the matched notices alongside pre-computed financial aggregates,
    avoiding redundant iteration in the UI layer.

    Attributes:
        notices: Ordered list of matched notice dicts, ranked by combined score.
        total_count: Number of notices that passed the relevance threshold.
        total_eur_value: Sum of estimated values in EUR across matched notices.
        valid_eur_count: Number of notices with a non-null EUR estimated value.
    """

    notices: list[dict]
    total_count: int
    total_eur_value: float
    valid_eur_count: int

    @property
    def average_eur_value(self) -> float:
        """Computes the average estimated value in EUR across matched notices.

        Returns:
            The mean EUR value across notices with a valid estimate,
            or 0.0 if no such notices exist.
        """
        if self.valid_eur_count == 0:
            return 0.0
        return self.total_eur_value / self.valid_eur_count


class SearchService:
    """Orchestrates semantic search with relevance scoring and result hydration.

    Combines ChromaDB vector search with a weighted scoring formula that
    balances semantic similarity against notice recency. Raw embedding
    distances are converted to similarity scores, merged with a time-decay
    recency factor, and used to rank and filter results before returning
    fully hydrated notice records from SQLite.

    Attributes:
        db: Read-capable storage backend for hydrating search results.
        search_engine: Vector search backend returning IDs and distances.
        settings: Configuration holding scoring weights and decay parameters.
    """

    def __init__(
        self,
        db: ReadStorageProtocol,
        search_engine: SearchEngineProtocol,
        settings: AppSettings,
    ) -> None:
        """Initializes the search service with its core dependencies.

        Args:
            db: Storage backend implementing ReadStorageProtocol.
            search_engine: Search backend implementing SearchEngineProtocol.
            settings: Application configuration with scoring parameters.
        """
        self.db = db
        self.search_engine = search_engine
        self.settings = settings

    def _convert_distance_to_similarity(self, distance: float) -> float:
        """Converts a cosine distance to a similarity score in [0, 1].

        ChromaDB returns distances where lower means more similar.
        This inverts the scale so that 1.0 is a perfect match
        and 0.0 is maximally dissimilar.

        Args:
            distance: Cosine distance returned by ChromaDB.

        Returns:
            A similarity score between 0.0 and 1.0.
        """
        return max(0, (1 - distance))

    def _compute_recency_score(self, pub_date_str: str) -> float:
        """Delegates recency scoring to the shared utility.

        Passes the publication date and the configured decay window to
        compute_recency_score, ensuring consistent recency behaviour
        across SearchService and ProfileSearchService.

        Args:
            pub_date_str: Publication date in YYYYMMDD format.

        Returns:
            A recency score between 0.0 and 1.0, where 1.0 is today and
            the score decays as the notice ages past recency_decay_days.
        """
        return compute_recency_score(pub_date_str, self.settings.recency_decay_days)

    def _compute_combined_score(self, semantic: float, recency: float) -> float:
        """Computes a weighted combination of semantic and recency scores.

        Weights are defined in AppSettings and must sum to 1.0,
        enforced at application startup by a Pydantic model validator.

        Args:
            semantic: Semantic similarity score in [0, 1].
            recency: Recency score in [0, 1].

        Returns:
            A combined relevance score in [0, 1].
        """
        return (
            self.settings.semantic_weight * semantic
            + self.settings.recency_weight * recency
        )

    def search(
        self,
        query: str,
        cpv_codes: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        threshold: float = 0.0,
        k: int = 50,
        use_recency: bool = True,
    ) -> SearchResults:
        """Executes a semantic search and returns ranked, hydrated results.

        Queries the vector store for the k nearest neighbours, applies optional
        hard filters (CPV codes and date range) against SQLite, hydrates the
        surviving IDs with full notice records, computes a combined relevance
        score for each result, and filters out anything below the threshold
        before returning.

        Args:
            query: Natural language search query.
            cpv_codes: Optional list of 8-digit CPV codes. When provided,
                restricts results to notices whose CPV field contains at least
                one matching code. None skips this filter entirely.
            start_date: Start of the publication date range in YYYYMMDD format.
                Requires end_date to take effect.
            end_date: End of the publication date range in YYYYMMDD format.
                Requires start_date to take effect.
            threshold: Minimum combined score a notice must exceed to be included
                in results. Defaults to 0.0 (no filtering).
            k: Maximum number of candidates to retrieve from the vector store.
                Defaults to 50.
            use_recency: When True, applies a time-decay factor to the combined
                score. When False, recency is fixed at 1.0, ranking purely by
                semantic relevance. Useful when searching historical data where
                publication date should not affect ranking.

        Returns:
            A SearchResults instance containing ranked notices and
            pre-computed financial aggregates.
        """
        raw_result = self.search_engine.search(query, k)

        if not raw_result:
            return SearchResults(
                notices=[], total_count=0, total_eur_value=0.0, valid_eur_count=0
            )

        ids = [result[NoticeField.ID] for result in raw_result]
        hard_filters_id = self.db.get_filtered_ids(
            cpv_codes=cpv_codes, start_date=start_date, end_date=end_date
        )
        if cpv_codes is not None or (start_date is not None and end_date is not None):
            ids = [id for id in ids if id in hard_filters_id]
        full_notices = self.db.get_notices_by_ids(ids)

        lookup_dict = {item[NoticeField.ID]: item["score"] for item in raw_result}
        for notice in full_notices:
            distance = lookup_dict[notice[NoticeField.ID]]
            semantic_similarity = self._convert_distance_to_similarity(distance)
            recency_score = (
                self._compute_recency_score(notice[NoticeField.PUB_DATE])
                if use_recency
                else 1.0
            )
            combined_score = self._compute_combined_score(
                semantic_similarity, recency_score
            )
            notice["recency"] = recency_score
            notice["semantic"] = semantic_similarity
            notice["combined_score"] = combined_score

        relevant = sorted(full_notices, key=lambda x: x["combined_score"], reverse=True)
        relevant = [n for n in relevant if n["combined_score"] > threshold]

        total_eur_value = sum(
            n[NoticeField.ESTIMATED_VALUE_EUR]
            for n in relevant
            if n[NoticeField.ESTIMATED_VALUE_EUR] is not None
        )
        valid_eur_count = sum(
            1 for n in relevant if n[NoticeField.ESTIMATED_VALUE_EUR] is not None
        )

        return SearchResults(
            notices=relevant,
            total_count=len(relevant),
            total_eur_value=total_eur_value,
            valid_eur_count=valid_eur_count,
        )
