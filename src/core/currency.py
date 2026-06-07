from typing import Optional, cast

from currency_converter import CurrencyConverter, RateNotFoundError

_converter = CurrencyConverter()
GENERAL_CURRENCY = "EUR"


def to_eur(amount: float, currency: str) -> Optional[float]:
    """Converts a monetary amount to EUR.

    Uses a module-level CurrencyConverter instance for efficiency.
    Returns None rather than raising on missing or invalid data,
    keeping the pipeline fault-tolerant for notices with exotic currencies.

    Args:
        amount: The monetary value to convert.
        currency: The ISO 4217 source currency code (e.g. "PLN", "CZK").

    Returns:
        The converted amount rounded to 2 decimal places, or None if
        the conversion fails or inputs are missing.
    """
    if not amount or not currency:
        return None
    if currency == GENERAL_CURRENCY:
        return round(amount, 2)
    try:
        return cast(
            float, round(_converter.convert(amount, currency, GENERAL_CURRENCY), 2)
        )
    except (RateNotFoundError, ValueError):
        return None
