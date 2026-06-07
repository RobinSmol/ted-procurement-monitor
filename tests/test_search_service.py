import pytest

from src.core.enums import NoticeField


@pytest.mark.unit
def test_search_returns_empty_results_when_no_matches(search_service):
    service, db, search_engine = search_service
    search_engine.search.return_value = []
    result = service.search("test query")
    assert result.total_count == 0
    assert result.notices == []


@pytest.mark.unit
def test_search_filters_by_threshold(search_service):
    service, db, search_engine = search_service
    search_engine.search.return_value = [
        {"id": "1111", "score": 0.1},
        {"id": "2222", "score": 0.9},
    ]
    db.get_notices_by_ids.return_value = [
        {
            NoticeField.ID: "1111",
            NoticeField.PUB_DATE: "2026-05-01",
            NoticeField.ESTIMATED_VALUE: None,
            NoticeField.CURRENCY: None,
            NoticeField.ESTIMATED_VALUE_EUR: None,
            NoticeField.DESCRIPTION: None,
            NoticeField.CPV: None,
        },
        {
            NoticeField.ID: "2222",
            NoticeField.PUB_DATE: "2026-05-01",
            NoticeField.ESTIMATED_VALUE: None,
            NoticeField.CURRENCY: None,
            NoticeField.ESTIMATED_VALUE_EUR: None,
            NoticeField.DESCRIPTION: None,
            NoticeField.CPV: None,
        },
    ]
    result = service.search("test", threshold=0.5)
    assert result.notices[0][NoticeField.ID] == "1111"
    assert result.total_count == 1


@pytest.mark.unit
def test_search_returns_correct_total_count(search_service):
    service, db, search_engine = search_service
    search_engine.search.return_value = [
        {"id": "1111", "score": 0.1},
        {"id": "2222", "score": 0.9},
    ]
    db.get_notices_by_ids.return_value = [
        {
            NoticeField.ID: "1111",
            NoticeField.PUB_DATE: "2026-05-01",
            NoticeField.ESTIMATED_VALUE: None,
            NoticeField.CURRENCY: None,
            NoticeField.ESTIMATED_VALUE_EUR: None,
            NoticeField.DESCRIPTION: None,
            NoticeField.CPV: None,
        },
        {
            NoticeField.ID: "2222",
            NoticeField.PUB_DATE: "2026-05-01",
            NoticeField.ESTIMATED_VALUE: None,
            NoticeField.CURRENCY: None,
            NoticeField.ESTIMATED_VALUE_EUR: None,
            NoticeField.DESCRIPTION: None,
            NoticeField.CPV: None,
        },
    ]
    result = service.search("test", threshold=0.0)
    assert result.total_count == 2


@pytest.mark.unit
def test_search_applies_hard_filter(search_service):
    service, mock_db, mock_engine = search_service
    mock_engine.search.return_value = [
        {"id": "1111", "score": 0.1},
        {"id": "2222", "score": 0.2},
    ]
    mock_db.get_filtered_ids.return_value = ["1111"]
    mock_db.get_notices_by_ids.return_value = [
        {
            "id": "1111",
            "pub_date": "2026-05-01",
            "estimated_value": None,
            "currency": None,
            "estimated_value_eur": None,
            "description": None,
            "cpv": None,
        }
    ]
    result = service.search("test", cpv_codes=["72000000"])
    mock_db.get_notices_by_ids.assert_called_once_with(["1111"])
    assert result.total_count == 1


@pytest.mark.unit
def test_search_skips_hard_filter_when_no_params(search_service):
    service, mock_db, mock_engine = search_service
    mock_engine.search.return_value = []
    mock_db.get_filtered_ids.assert_not_called()
