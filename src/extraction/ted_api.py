import logging
from datetime import date
from typing import Optional, cast

import requests

from src.core.config import AppSettings
from src.core.utils import date_to_api_str
from src.extraction.base_extractor import BaseExtractor
from src.extraction.ted_transformer import TEDNoticeTransformer

logger = logging.getLogger(__name__)


class TEDExtractor(BaseExtractor):
    """Extracts tender notices from the TED (Tenders Electronic Daily) API.

    Handles pagination transparently, delegating raw notice normalization
    to an initialized transformer. The API is queried by publication date,
    returning all active notices published on that day.

    Attributes:
        transformer: Source-specific transformer for normalizing raw payloads.
        settings: Application configuration instance.
        base_url: TED API v3 search endpoint.
    """

    def __init__(self, settings: AppSettings, source_name: str) -> None:
        """Initializes the TEDExtractor with configuration and a transformer.

        Args:
            settings: Application configuration holding API credentials
                and pagination parameters.
            source_name: The source name that represents this extractor
                and its corresponding Transformer.
        """
        super().__init__(source_name=source_name)
        self.transformer = TEDNoticeTransformer(source_name=source_name)
        self.settings = settings
        self.base_url = "https://api.ted.europa.eu/v3/notices/search"

    def fetch_daily_notices(self, target_date: date) -> list[dict]:
        """Fetches and normalizes all notices published on the given date.

        Paginates through the TED API until all available notices for the
        target date have been retrieved. Each raw notice is passed through
        the transformer before being added to the result set. Notices
        without a valid ID are silently discarded.

        Args:
            target_date: The publication date to query.

        Returns:
            A list of normalized notice dictionaries compatible with
            StandardNotice field names.
        """
        date_str = date_to_api_str(target_date)
        logger.info(f"Fetching {self.source_name} publication for {date_str}")

        total_available = 1
        total_fetched = 0
        all_notices = []
        page_number = 1

        while total_fetched < total_available:
            logger.debug(f"Fetching page {page_number}.")
            response = self._make_request(date_str, page_number)

            if not response or "notices" not in response:
                logger.error("Error or unadverted end of data. Stopping pagination.")
                break

            if page_number == 1:
                total_available = response.get("totalNoticeCount", 0)
                logger.info(
                    f"Total notices available for {date_str}: {total_available}"
                )

            current_notices = response["notices"]
            total_fetched += len(current_notices)
            page_number += 1

            for notice in current_notices:
                clean_notice = self.transformer.normalize(notice)
                if clean_notice and clean_notice.get("id"):
                    all_notices.append(clean_notice)

        return all_notices

    def _make_request(self, date_str: str, page: int) -> Optional[dict]:
        """Sends a single paginated POST request to the TED API.

        Requests a specific page of notices for the given publication date.
        Returns None on any HTTP or network error rather than raising,
        allowing the caller to decide how to handle failures.

        Args:
            date_str: Publication date to query in YYYYMMDD format.
            page: Page number to fetch (1-indexed).

        Returns:
            The parsed JSON response dict, or None if the request failed.
        """
        payload = {
            "query": f"PD={date_str}",
            "fields": [
                "ND",
                "TI",
                "AA",
                "DT",
                "PD",
                "description-lot",
                "estimated-value-glo",
                "estimated-value-cur-glo",
                "estimated-value-lot",
                "estimated-value-cur-lot",
                "organisation-country-buyer",
                "classification-cpv",
            ],
            "page": f"{page}",
            "limit": self.settings.ted_api_page_limit,
            "scope": "ACTIVE",
            "paginationMode": "PAGE_NUMBER",
        }

        headers = {"Accept": "application/json"}

        try:
            response = requests.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=self.settings.ted_api_timeout,
            )
            response.raise_for_status()
            return cast(dict, response.json())
        except requests.exceptions.HTTPError as http_err:
            logger.error(f"HTTP error: {http_err}")
        except Exception as err:
            logger.error(f"Unexpected exception occurred: {err}")
        return None
