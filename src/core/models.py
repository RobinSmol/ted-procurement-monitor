from typing import Optional

from pydantic import BaseModel, Field, field_validator


class StandardNotice(BaseModel):
    """Canonical data model for a normalized tender notice.

    Acts as the contract between the extraction layer and the rest of
    the pipeline. Every data source must produce output that validates
    against this model before reaching storage or search indexing.

    Field descriptions are defined inline via Pydantic's Field()
    and serve as the authoritative schema documentation.
    """

    id: str = Field(..., description="Unique notice identifier")
    title: str = Field(default="", description="Title of the tender")
    pub_date: str = Field(default="", description="Publication date (YYYYMMDD)")
    country: Optional[str] = Field(default=None, description="Buyer's country (ISO-3)")
    estimated_value: Optional[float] = Field(
        default=None, description="Estimated contract value"
    )
    description: Optional[str] = Field(default="", description="Tender description")
    cpv: Optional[str] = Field(
        default=None, description="CPV classification (JSON string)"
    )
    currency: Optional[str] = Field(
        default=None, description="Original ISO currency code (e.g. EUR, PLN, CZK)"
    )
    estimated_value_eur: Optional[float] = Field(
        default=None, description="Estimated value normalized to EUR"
    )
    source_name: str = Field(
        description="The source name from where the tender comes from."
    )

    @field_validator("description", mode="before")
    @classmethod
    def coerce_description_to_str(cls, v):
        """Coerces description to a string before validation.

        The TED API occasionally returns description fields as a list
        of strings rather than a single string. This validator joins
        them into a single space-separated string.

        Args:
            v: The raw incoming value for the description field.

        Returns:
            A string, or None if the input was None.
        """
        if v is None:
            return None
        if isinstance(v, list):
            return " ".join(str(item) for item in v if item)
        return v

    @field_validator("estimated_value", mode="before")
    @classmethod
    def coerce_estimated_value(cls, v):
        """Coerces estimated_value to a scalar float before validation.

        The TED API may return this field as a single-element list.
        This validator extracts the first element when that occurs.

        Args:
            v: The raw incoming value for the estimated_value field.

        Returns:
            A float, or None if the list was empty or input was None.
        """
        if isinstance(v, list):
            return v[0] if v else None
        return v

    @field_validator("currency", mode="before")
    @classmethod
    def coerce_currency(cls, v):
        """Coerces currency to a scalar string before validation.

        The TED API may return this field as a single-element list.
        This validator extracts the first element when that occurs.

        Args:
            v: The raw incoming value for the currency field.

        Returns:
            A string, or None if the list was empty or input was None.
        """
        if isinstance(v, list):
            return v[0] if v else None
        return v
