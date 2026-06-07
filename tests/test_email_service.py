from unittest.mock import MagicMock, patch

import pytest

from src.core.email_service import EmailService


@pytest.fixture
def email_service():
    return EmailService(
        smtp_host="smtp-relay.brevo.com",
        smtp_port=587,
        smtp_login="test@smtp-brevo.com",
        smtp_password="fake_key",
        sender_email="sender@test.com",
        dashboard_url="http://localhost:8501",
    )


@pytest.mark.unit
def test_send_alert_skips_when_no_notices(email_service):
    with patch("smtplib.SMTP") as mock_smtp:
        email_service.send_alert(
            recipient="test@test.com",
            query="IT services",
            notices=[],
        )
        mock_smtp.assert_not_called()


@pytest.mark.unit
def test_send_alert_calls_smtp_with_notices(email_service):
    notices = [
        {
            "id": "1111",
            "title": "Test Tender",
            "country": "DEU",
            "pub_date": "20260528",
            "combined_score": 0.85,
        }
    ]
    with patch("smtplib.SMTP") as mock_smtp:
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        email_service.send_alert(
            recipient="test@test.com",
            query="IT services",
            notices=notices,
        )
        mock_smtp.assert_called_once_with("smtp-relay.brevo.com", 587)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("test@smtp-brevo.com", "fake_key")


@pytest.mark.unit
def test_build_html_contains_query(email_service):
    notices = [
        {
            "id": "1111",
            "title": "Test Tender",
            "country": "DEU",
            "pub_date": "20260528",
            "combined_score": 0.85,
        }
    ]
    html = email_service._build_html("precision optics", notices)
    assert "precision optics" in html


@pytest.mark.unit
def test_build_html_contains_notice_title(email_service):
    notices = [
        {
            "id": "1111",
            "title": "Laser equipment procurement",
            "country": "DEU",
            "pub_date": "20260528",
            "combined_score": 0.85,
        }
    ]
    html = email_service._build_html("test query", notices)
    assert "Laser equipment procurement" in html


@pytest.mark.unit
def test_build_html_shows_overflow_count(email_service):
    notices = [
        {
            "id": str(i),
            "title": f"Tender {i}",
            "country": "DEU",
            "pub_date": "20260528",
            "combined_score": 0.8,
        }
        for i in range(8)
    ]
    html = email_service._build_html("test", notices)
    assert "3 more" in html
