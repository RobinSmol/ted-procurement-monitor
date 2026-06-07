import logging

from pydantic import ValidationError

from src.core.currency import to_eur
from src.core.enums import NoticeField
from src.core.models import StandardNotice

logger = logging.getLogger(__name__)


class NoticeTransformer:
    """Validates and enriches normalized notice dictionaries.

    Sits between source-specific transformers and the storage layer.
    Runs Pydantic validation against StandardNotice and appends
    the EUR-converted estimated value when currency data is available.
    Acts as the final quality gate before any notice reaches the database.
    """

    def transform(self, notice: dict) -> dict | None:
        """Validates a notice dict and enriches it with EUR conversion.

        Instantiates a StandardNotice from the input dict to enforce
        schema compliance, then serializes it back to a plain dict.
        If currency and estimated value are both present, appends the
        EUR-normalized value via the currency converter.

        Args:
            notice: A normalized notice dictionary, typically produced
                by a source-specific BaseTransformer subclass.

        Returns:
            A fully validated and enriched notice dictionary ready for
            storage, or None if Pydantic validation fails.
        """
        try:
            clean_notice = StandardNotice(**notice)
            data = clean_notice.model_dump()

            if data.get(NoticeField.CURRENCY) and data.get(NoticeField.ESTIMATED_VALUE):
                data[NoticeField.ESTIMATED_VALUE_EUR] = to_eur(
                    data[NoticeField.ESTIMATED_VALUE], data[NoticeField.CURRENCY]
                )
            return data

        except ValidationError as e:
            logger.error(f"Validation failed - Error: {e}")
            return None
