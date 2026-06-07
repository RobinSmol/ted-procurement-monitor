import pytest

from src.core.enums import NoticeField
from src.pipeline.notice_transformer import NoticeTransformer


@pytest.mark.unit
def test_transform_returns_none_on_invalid_notice():
    transformer = NoticeTransformer()
    result = transformer.transform({})
    assert result is None


@pytest.mark.unit
def test_transform_returns_valid_notice(sample_notice):
    transformer = NoticeTransformer()
    result = transformer.transform(sample_notice[0])
    assert result is not None
    assert result[NoticeField.ID] == "1111"
