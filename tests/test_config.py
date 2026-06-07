from pathlib import Path

import pytest
from pydantic import ValidationError

from src.core.config import AppSettings


@pytest.mark.unit
def test_raise_weight_not_sum_to_1():
    with pytest.raises(ValidationError):
        AppSettings(
            _env_file=None, ted_api_key="fake_key", semantic_weight=1, recency_weight=1
        )


@pytest.mark.unit
def test_default_value(valid_settings):
    assert valid_settings.ted_api_page_limit == 200
    assert valid_settings.ted_api_timeout == 10
    assert valid_settings.ted_db_path == Path("data/ted_database.db")
    assert valid_settings.semantic_weight == 0.7
    assert valid_settings.recency_decay_days == 30
