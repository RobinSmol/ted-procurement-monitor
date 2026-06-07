import json
import logging
from datetime import date

from src.core.email_service import EmailService
from src.core.enums import AlertField, NoticeField
from src.core.interfaces import SearchEngineProtocol, WriteStorageProtocol
from src.core.utils import date_to_api_str
from src.extraction.base_extractor import BaseExtractor
from src.pipeline.notice_transformer import NoticeTransformer
from src.search.search_service import SearchService

logger = logging.getLogger(__name__)


class DataPipeline:
    """Orchestrates the full ETL process: Extract → Transform → Load.

    Iterates over all registered extractors for a given date, deduplicates
    incoming notices against existing storage, validates them through Pydantic,
    and persists them to both SQLite and ChromaDB. Designed to be idempotent —
    re-running for the same date produces no duplicates and no side effects.

    Attributes:
        extractors: List of data source extractors to run in sequence.
        db: Write-capable storage backend for persisting notices.
        chroma: Search engine backend for indexing notice embeddings.
        transformer: Validation and enrichment layer applied before storage.
        search_service: Optional search service used to execute alert queries
            at the end of each pipeline run. When None, alert processing is
            silently skipped.
        email_service: Optional email service used to dispatch alert digests.
            When None, alert processing is silently skipped.
    """

    def __init__(
        self,
        extractors: list[BaseExtractor],
        db: WriteStorageProtocol,
        search_engine: SearchEngineProtocol,
        transformer: NoticeTransformer,
        search_service: SearchService | None = None,
        email_service: EmailService | None = None,
    ) -> None:
        """Initializes the pipeline with its core dependencies.

        Args:
            extractors: Ordered list of extractors to run against each date.
            db: Storage backend implementing WriteStorageProtocol.
            search_engine: Search backend implementing SearchEngineProtocol.
            transformer: Transformer responsible for Pydantic validation and
                enrichment before storage.
            search_service: Optional search service for executing alert queries.
                When None, the alert processing step at the end of run() is
                silently skipped.
            email_service: Optional email service for dispatching alert digests.
                When None, the alert processing step at the end of run() is
                silently skipped.
        """
        self.extractors = extractors
        self.db = db
        self.chroma = search_engine
        self.transformer = transformer
        self.search_service = search_service
        self.email_service = email_service

    def run(self, target_date: date) -> None:
        """Executes the full ETL pipeline for the given date.

        For each extractor, fetches raw notices, filters duplicates,
        validates through Pydantic, and loads into both storage backends.
        Marks the date as fetched regardless of whether any notices were
        found, ensuring the date is not re-queried on subsequent runs.

        Args:
            target_date: The publication date to process.
        """
        date_str = date_to_api_str(target_date)
        if not self.extractors:
            logger.error("No extractor configured. Aborting pipeline.")
            return
        logger.info(f"--- Pipeline started for {date_str} ---")

        for extractor in self.extractors:
            logger.info(f"Processing source: {extractor.source_name}")

            raw_notices = extractor.fetch_daily_notices(target_date)
            if not raw_notices:
                logger.warning(f"No data retrieved from {extractor.source_name}.")
                continue

            new_notices = self._filter_existing(raw_notices)
            if not new_notices:
                logger.info(f"All notices from {extractor.source_name} already stored.")
                continue

            valid_notices = []
            for notice in new_notices:
                result = self.transformer.transform(notice)
                if result:
                    valid_notices.append(result)

            logger.info(
                f"{len(valid_notices)} valid notices out of {len(raw_notices)} raw."
            )
            if not valid_notices:
                logger.warning(
                    f"No valid notices after validation for {extractor.source_name}."
                )
                continue

            self._load_data(valid_notices)

        self.db.mark_date_as_fetched(date_str)
        self._process_alerts(date_str)
        logger.info("--- Pipeline finished successfully ---")

    def _filter_existing(self, raw_notices: list[dict]) -> list[dict]:
        """Removes notices that are already present in storage.

        Extracts IDs from the incoming batch and queries the database
        for matches, returning only the notices that are genuinely new.

        Args:
            raw_notices: The full list of notices returned by an extractor.

        Returns:
            A filtered list containing only notices not yet in storage.
        """
        logger.info(f"Filtering {len(raw_notices)} notices for duplicates...")

        extracted_ids = [
            str(n.get(NoticeField.ID)) for n in raw_notices if n.get(NoticeField.ID)
        ]
        if not extracted_ids:
            return []

        existing_ids = self.db.get_existing_ids(extracted_ids)
        new_notices = [
            n for n in raw_notices if str(n.get(NoticeField.ID)) not in existing_ids
        ]

        logger.info(f"-> {len(new_notices)} new notices to process.")
        return new_notices

    def _load_data(self, valid_notices: list[dict]) -> None:
        """Persists validated notices to SQLite and indexes them in ChromaDB.

        Treats the two storage operations independently — a ChromaDB failure
        does not roll back the SQLite save. Errors are logged but not raised,
        keeping the pipeline fault-tolerant across sources.

        Args:
            valid_notices: Fully validated and enriched notice dictionaries.
        """
        logger.info(f"Loading {len(valid_notices)} notices into storage...")

        try:
            self.db.save_notices(valid_notices)
            logger.info("SQLite save successful.")
        except Exception as e:
            logger.error(f"Critical error during SQLite save: {e}", exc_info=True)
            return
        try:
            self.chroma.add_notices(valid_notices)
            logger.info("ChromaDB indexing successful.")
        except Exception as e:
            logger.error(f"Error during ChromaDB indexing: {e}", exc_info=True)

    def _process_alerts(self, date_str: str) -> None:
        """Fires all alerts scheduled for today.

        Skips silently if search_service or email_service are not configured.
        For each alert, runs the saved search from last_sent to today,
        sends the email, and marks the alert as sent.

        Args:
            date_str: Today's date in YYYYMMDD format.
        """
        if not self.search_service or not self.email_service:
            return

        alerts = self.db.get_todays_alerts()
        if not alerts:
            logger.info("No alerts scheduled for today.")
            return

        logger.info(f"Processing {len(alerts)} alert(s).")
        for alert in alerts:
            try:
                cpv_codes = (
                    json.loads(alert[AlertField.CPV_CODES])
                    if alert[AlertField.CPV_CODES]
                    else None
                )
                start_date = alert[AlertField.LAST_SENT] or date_str

                results = self.search_service.search(
                    query=alert[AlertField.QUERY] or "",
                    cpv_codes=cpv_codes,
                    start_date=start_date,
                    end_date=date_str,
                    threshold=alert[AlertField.THRESHOLD],
                    k=50,
                )
                self.email_service.send_alert(
                    recipient=alert[AlertField.EMAIL],
                    query=alert[AlertField.QUERY] or "",
                    notices=results.notices,
                    alert_id=alert[AlertField.ID],
                )
                self.db.mark_alert_sent(alert[AlertField.ID])
            except Exception as e:
                logger.error(
                    f"Error processing alert {alert[AlertField.ID]}: {e}", exc_info=True
                )
