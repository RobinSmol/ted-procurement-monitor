import pytest

from src.core.enums import NoticeField


@pytest.mark.integration
def test_Notice_save_and_retrieved(db, sample_notice):
    db.save_notices(sample_notice)
    result = db.get_notices_by_ids([sample_notice[0][NoticeField.ID]])
    assert len(result) == 1
    assert result[0][NoticeField.ID] == "1111"


@pytest.mark.integration
def test_no_duplicate(db, sample_notice):
    db.save_notices(sample_notice)
    db.save_notices(sample_notice)
    result = db.get_existing_ids([sample_notice[0][NoticeField.ID]])
    assert len(result) == 1


@pytest.mark.integration
def test_date_tracking_works(db, sample_notice):
    db.mark_date_as_fetched(sample_notice[0][NoticeField.PUB_DATE])
    result = db.get_fetched_dates()
    assert len(result) == 1
    assert result.pop() == "20260510"


@pytest.mark.integration
def test_Country_stats_accurate(db, sample_notice):
    db.save_notices(sample_notice)
    result = db.get_country_stats()
    assert result[0][NoticeField.COUNTRY] == "FRA"
    assert result[0]["total_notices"] == 1


@pytest.mark.integration
def test_get_filtered_ids_returns_empty_when_no_filters(db):
    result = db.get_filtered_ids(cpv_codes=None, start_date=None, end_date=None)
    assert result == []


@pytest.mark.integration
def test_get_filtered_ids_with_cpv_match(db, sample_notice):
    notice = sample_notice[0].copy()
    notice["cpv"] = '["72000000"]'
    db.save_notices([notice])
    result = db.get_filtered_ids(cpv_codes=["72000000"], start_date=None, end_date=None)
    assert "1111" in result


@pytest.mark.integration
def test_get_filtered_ids_with_cpv_no_match(db, sample_notice):
    notice = sample_notice[0].copy()
    notice["cpv"] = '["38000000"]'
    db.save_notices([notice])
    result = db.get_filtered_ids(cpv_codes=["72000000"], start_date=None, end_date=None)
    assert "1111" not in result


@pytest.mark.integration
def test_get_filtered_ids_with_date_range(db, sample_notice):
    db.save_notices(sample_notice)
    result = db.get_filtered_ids(
        cpv_codes=None, start_date="20260509", end_date="20260511"
    )
    assert "1111" in result


@pytest.mark.integration
def test_get_filtered_ids_date_range_excludes_outside(db, sample_notice):
    db.save_notices(sample_notice)
    result = db.get_filtered_ids(
        cpv_codes=None, start_date="20260601", end_date="20260610"
    )
    assert "1111" not in result


@pytest.mark.integration
def test_get_filtered_ids_with_both_filters(db, sample_notice):
    notice = sample_notice[0].copy()
    notice["cpv"] = '["72000000"]'
    db.save_notices([notice])
    result = db.get_filtered_ids(
        cpv_codes=["72000000"], start_date="20260509", end_date="20260511"
    )
    assert "1111" in result


@pytest.mark.integration
def test_save_and_get_alert(db):
    alert = {
        "id": "alert-001",
        "email": "test@test.com",
        "query": "IT services",
        "cpv_codes": '["72000000"]',
        "threshold": 0.5,
        "send_days": "MON,WED,FRI",
    }
    db.save_alert(alert)
    result = db.get_all_alerts()
    assert len(result) == 1
    assert result[0]["email"] == "test@test.com"
    assert result[0]["query"] == "IT services"


@pytest.mark.integration
def test_delete_alert(db):
    alert = {
        "id": "alert-002",
        "email": "test@test.com",
        "query": "construction",
        "cpv_codes": None,
        "threshold": 0.5,
        "send_days": "TUE",
    }
    db.save_alert(alert)
    db.delete_alert("alert-002")
    result = db.get_all_alerts()
    assert all(a["id"] != "alert-002" for a in result)


@pytest.mark.integration
def test_mark_alert_sent(db):
    from datetime import date

    alert = {
        "id": "alert-003",
        "email": "test@test.com",
        "query": "services",
        "cpv_codes": None,
        "threshold": 0.5,
        "send_days": "MON",
    }
    db.save_alert(alert)
    db.mark_alert_sent("alert-003")
    result = db.get_all_alerts()
    today_str = date.today().strftime("%Y%m%d")
    assert result[0]["last_sent"] == today_str


@pytest.mark.integration
def test_get_todays_alerts_returns_correct_alerts(db):
    from datetime import date

    today_day = date.today().strftime("%a").upper()

    alert_today = {
        "id": "alert-004",
        "email": "test@test.com",
        "query": "test",
        "cpv_codes": None,
        "threshold": 0.5,
        "send_days": today_day,
    }
    alert_sent = {
        "id": "alert-005",
        "email": "test@test.com",
        "query": "test",
        "cpv_codes": None,
        "threshold": 0.5,
        "send_days": today_day,
    }
    db.save_alert(alert_today)
    db.save_alert(alert_sent)
    db.mark_alert_sent("alert-005")

    result = db.get_todays_alerts()
    ids = [a["id"] for a in result]
    assert "alert-004" in ids
    assert "alert-005" not in ids
