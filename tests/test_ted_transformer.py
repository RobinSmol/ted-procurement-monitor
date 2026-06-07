import pytest

from src.core.enums import NoticeField
from src.extraction.ted_transformer import TEDNoticeTransformer


@pytest.mark.unit
def test_normalize_returns_none_when_id_missing():
    transformer = TEDNoticeTransformer("test_source")
    result = transformer.normalize({"test": "test"})
    assert result is None


@pytest.mark.unit
def test_normalize_returns_correct_fields():
    transformer = TEDNoticeTransformer("Test_source")
    test_dict = {"ND": "1111", "TI": {"eng": "test_title"}, "PD": "2026-05-10"}
    result = transformer.normalize(test_dict)
    assert result[NoticeField.ID] == "1111"


@pytest.mark.unit
def test_pub_date_format_is_yyyymmdd():
    transformer = TEDNoticeTransformer("test_source")
    test_dict = {"ND": "1111", "TI": {"eng": "test_title"}, "PD": "2026-05-18+02:00"}
    result = transformer.normalize(test_dict)
    assert result["pub_date"] == "20260518"


@pytest.mark.unit
def test_pub_date_none_returns_empty_string():
    transformer = TEDNoticeTransformer("test_source")
    test_dict = {"ND": "1111", "TI": {"eng": "test"}, "PD": None}
    result = transformer.normalize(test_dict)
    assert result["pub_date"] == ""


@pytest.mark.unit
def test_source_name_is_injected():
    transformer = TEDNoticeTransformer("MY_SOURCE")
    test_dict = {"ND": "1111", "TI": {"eng": "test"}, "PD": "2026-05-18+02:00"}
    result = transformer.normalize(test_dict)
    assert result["source_name"] == "MY_SOURCE"
