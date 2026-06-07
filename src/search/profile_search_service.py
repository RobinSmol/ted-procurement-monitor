import json
import logging
import re

from src.core.config import AppSettings
from src.core.enums import NoticeField, ProfileField
from src.core.interfaces import ReadStorageProtocol, SearchEngineProtocol
from src.core.utils import compute_recency_score
from src.search.search_service import SearchResults

logger = logging.getLogger(__name__)

COUNTRY_BOOST_FACTOR = 1.2
NEGATIVE_KEYWORD_PENALTY = 0.8


class ProfileSearchService:
    """Ranks tender notices against a full company profile.

    Replaces the single-query semantic search with a multi-dimensional
    scoring system. Each keyword in the profile generates candidates
    independently — a notice matches the profile if it is close to ANY
    keyword. Negative keywords penalize irrelevant results. Preferred
    countries boost the score of geographically relevant tenders.

    This is the core differentiator vs traditional procurement tools
    that rely on a single keyword or CPV filter.

    Attributes:
        db: Read-capable storage backend for hydrating results.
        search_engine: Vector search backend with multi-query support.
        settings: Application configuration with scoring weights.
    """

    def __init__(
        self,
        db: ReadStorageProtocol,
        search_engine: SearchEngineProtocol,
        settings: AppSettings,
    ) -> None:
        """Initializes the profile search service with its core dependencies.

        Args:
            db: Read-capable storage backend used to hydrate candidate notices
                and apply hard filters by CPV code and date range.
            search_engine: Vector search backend providing multi-query semantic
                retrieval across all indexed notices.
            settings: Application configuration holding scoring weights and
                recency decay parameters.
        """
        self.db = db
        self.search_engine = search_engine
        self.settings = settings

    def search(
        self,
        profile: dict,
        k: int = 100,
        threshold: float = 0.0,
        start_date: str | None = None,
        end_date: str | None = None,
        use_recency: bool = True,
    ) -> SearchResults:
        """Scores all candidates against the company profile.

        Retrieves candidates by running multi-keyword semantic search,
        applies optional CPV and date filters, then scores each notice using
        the full profile — keyword match, negative keyword penalty,
        country boost, and recency decay.

        Args:
            profile: Company profile dict with ProfileField keys. Keywords,
                negative keywords, preferred countries, and CPV codes are
                expected as JSON-serialized lists.
            k: Number of candidates to retrieve per keyword from ChromaDB.
                Defaults to 100.
            threshold: Minimum combined score to include in results.
                Defaults to 0.0 (no filtering).
            start_date: Optional start of the publication date range in
                YYYYMMDD format. Requires end_date to take effect.
            end_date: Optional end of the publication date range in
                YYYYMMDD format. Requires start_date to take effect.
            use_recency: When True, applies a time-decay factor to the combined
                score. When False, recency is fixed at 1.0, ranking purely by
                semantic and keyword relevance. Useful when searching historical
                data where publication date should not affect ranking.

        Returns:
            SearchResults ranked by combined profile relevance score.
        """
        keywords = json.loads(profile.get(ProfileField.KEYWORDS) or "[]")
        negative_keywords = json.loads(
            profile.get(ProfileField.NEGATIVE_KEYWORDS) or "[]"
        )
        preferred_countries = json.loads(
            profile.get(ProfileField.PREFERRED_COUNTRIES) or "[]"
        )
        cpv_codes = json.loads(profile.get(ProfileField.CPV_CODES) or "[]") or None

        if not keywords:
            logger.warning(
                f"Profile '{profile.get(ProfileField.NAME)}' has no keywords."
            )
            return SearchResults(
                notices=[], total_count=0, total_eur_value=0.0, valid_eur_count=0
            )

        raw_scores = self.search_engine.search_multi_query(keywords, k=k)
        if not raw_scores:
            return SearchResults(
                notices=[], total_count=0, total_eur_value=0.0, valid_eur_count=0
            )

        candidate_ids = list(raw_scores.keys())

        if cpv_codes or (start_date and end_date):
            filtered_ids = set(
                self.db.get_filtered_ids(
                    cpv_codes=cpv_codes,
                    start_date=start_date,
                    end_date=end_date,
                )
            )
            candidate_ids = [i for i in candidate_ids if i in filtered_ids]

        if not candidate_ids:
            return SearchResults(
                notices=[], total_count=0, total_eur_value=0.0, valid_eur_count=0
            )

        full_notices = self.db.get_notices_by_ids(candidate_ids)

        for notice in full_notices:
            nid = notice[NoticeField.ID]
            semantic_score = raw_scores.get(nid, 0.0)

            notice_text = self._extract_clean_text(notice)
            penalized = any(neg.lower() in notice_text for neg in negative_keywords)
            effective_semantic = max(
                0.0, semantic_score - (NEGATIVE_KEYWORD_PENALTY if penalized else 0.0)
            )

            country = notice.get(NoticeField.COUNTRY, "")
            country_multiplier = (
                COUNTRY_BOOST_FACTOR if country in preferred_countries else 1.0
            )

            recency = (
                compute_recency_score(
                    notice[NoticeField.PUB_DATE],
                    self.settings.recency_decay_days,
                )
                if use_recency
                else 1.0
            )

            combined = min(
                1.0,
                (
                    self.settings.semantic_weight * effective_semantic
                    + self.settings.recency_weight * recency
                )
                * country_multiplier,
            )

            notice["semantic"] = semantic_score
            notice["recency"] = recency
            notice["combined_score"] = round(combined, 4)
            notice["penalized"] = penalized

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

    def _extract_clean_text(self, notice: dict) -> str:
        """Extracts clean lowercase text from a notice for negative matching.

        Args:
            notice: Notice dict.

        Returns:
            Lowercase string with HTML tags stripped.
        """
        title = notice.get(NoticeField.TITLE) or ""
        description = notice.get(NoticeField.DESCRIPTION) or ""
        combined = f"{title} {description}"
        combined = re.sub(r"<[^>]+>", " ", combined)
        return combined.lower()
