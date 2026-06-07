import json
from datetime import datetime

from src.core.enums import NoticeField
from src.extraction.base_transformer import BaseTransformer


class TEDNoticeTransformer(BaseTransformer):
    """Transforms raw TED API payloads into StandardNotice-compatible dicts.

    Handles the structural inconsistencies of the TED API response format —
    multilingual fields, nested lot-level values, and missing global estimates.
    All output keys match StandardNotice field names exactly.
    """

    def __init__(self, source_name: str) -> None:
        """Initialize the TED Transformer and fix the source_name.

        Args:
            source_name: String characterizing the source_name of tenders
            (here it should be TED)
        """
        super().__init__(source_name=source_name)

    def normalize(self, notice: dict) -> dict | None:
        """Normalizes a raw TED API notice into a StandardNotice-compatible dict.

        Extracts and flattens nested fields, prioritizes English content where
        available, and falls back to lot-level value aggregation when a global
        estimated value is absent.

        Args:
            notice: Raw notice payload as returned by the TED API.

        Returns:
            A flat dictionary with StandardNotice-compatible keys, or None
            if the notice lacks a valid identifier (ND field).
        """
        if not notice.get("ND"):
            return None

        title_dict = notice.get("TI", {})
        title = title_dict.get("eng", str(title_dict))

        country_list = notice.get("organisation-country-buyer", [])
        country = country_list[0] if country_list else None

        estimated_value = notice.get("estimated-value-glo")
        currency = notice.get("estimated-value-cur-glo")

        if estimated_value is None:
            lot_values = notice.get("estimated-value-lot") or []
            lot_values = [float(item) for item in lot_values]
            estimated_value = sum(lot_values) if lot_values else None
            lot_currencies = notice.get("estimated-value-cur-lot") or []
            currency = lot_currencies[0] if lot_currencies else None

        description = self._extract_description_text(notice.get("description-lot"))
        cpv = (
            json.dumps(notice.get("classification-cpv"))
            if notice.get("classification-cpv")
            else None
        )
        raw_date = notice.get("PD")

        return {
            NoticeField.ID: notice.get("ND"),
            NoticeField.TITLE: title,
            NoticeField.PUB_DATE: (
                datetime.fromisoformat(raw_date).strftime("%Y%m%d") if raw_date else ""
            ),
            NoticeField.COUNTRY: country,
            NoticeField.ESTIMATED_VALUE: estimated_value,
            NoticeField.DESCRIPTION: description,
            NoticeField.CPV: cpv,
            NoticeField.CURRENCY: currency,
            NoticeField.ESTIMATED_VALUE_EUR: None,
            NoticeField.SOURCE_NAME: self.source_name,
        }

    def _extract_description_text(self, description_lot: list | None) -> str:
        """Extracts a single clean text string from the description-lot field.

        The TED API returns descriptions as a list of per-lot dicts, each
        potentially containing multiple language keys. This method prioritizes
        English content, then falls back to the first available language,
        and finally joins raw strings if no dict structure is found.

        Args:
            description_lot: The raw description-lot value from the API,
                which may be a list of dicts, a single dict, or None.

        Returns:
            A single description string, or an empty string if no
            extractable content is found.
        """
        description = ""
        if description_lot is None:
            return ""
        if isinstance(description_lot, dict):
            description_lot = [description_lot]
        for d in description_lot:
            if isinstance(d, dict) and d.get("eng"):
                english_description = d.get("eng")
                if english_description:
                    description = english_description
                break

        if not description and description_lot:
            first_item = description_lot[0]
            if isinstance(first_item, dict):
                for value in first_item.values():
                    if value:
                        description = value
                        break
            elif isinstance(first_item, str):
                description = " ".join(s for s in description_lot if isinstance(s, str))
        return description
