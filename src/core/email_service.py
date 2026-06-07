import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from src.core.enums import NoticeField

logger = logging.getLogger(__name__)


class EmailService:
    """Sends HTML email digests for procurement alert notifications.

    Connects via SMTP with STARTTLS. Works with any SMTP provider
    and is configured for Brevo by default.

    Attributes:
        smtp_host: SMTP server hostname.
        smtp_port: SMTP server port (587 for STARTTLS).
        sender_email: From address used for outgoing emails.
        smtp_password: App password or API key for SMTP authentication.
        smtp_login: Email address used as the SMTP login identity.
        dashboard_url: Base URL of the Streamlit dashboard included in emails.
    """


    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        smtp_login: str,
        smtp_password: str,
        sender_email: str,
        dashboard_url: str,
    ) -> None:
        """Initializes the email service with SMTP connection details.

        Args:
            smtp_host: SMTP server hostname.
            smtp_port: SMTP server port (typically 587 for STARTTLS).
            smtp_login: Email address used as the SMTP login identity.
            smtp_password: App password or API key for SMTP authentication.
            sender_email: From address displayed on outgoing emails.
            dashboard_url: Base URL of the Streamlit dashboard, used to
                build report links in alert emails.
        """
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.sender_email = sender_email
        self.smtp_password = smtp_password
        self.smtp_login = smtp_login
        self.dashboard_url = dashboard_url

    def send_alert(
        self,
        recipient: str,
        query: str,
        notices: list[dict],
        alert_id: str = "",
    ) -> None:
        """Sends a daily digest email for a single alert profile.

        Skips sending if the notices list is empty. Errors are caught
        and logged without raising, keeping the pipeline fault-tolerant.

        Args:
            recipient: Destination email address.
            query: The search query that produced these results.
            notices: List of matched notice dicts ranked by combined score.
            alert_id: UUID of the alert configuration, used to build the
                report URL. Defaults to an empty string when no report
                link is needed.

        """
        if not notices:
            logger.info(f"No results for '{query}' — skipping email to {recipient}.")
            return

        subject = f"📋 {len(notices)} new tender(s) matching '{query}'"
        html = self._build_html(query, notices, alert_id)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.sender_email
        msg["To"] = recipient
        msg.attach(MIMEText(html, "html"))

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_login, self.smtp_password)
                server.sendmail(self.sender_email, recipient, msg.as_string())
            logger.info(f"Alert sent to {recipient} for query '{query}'.")
        except Exception as e:
            logger.error(f"Failed to send email to {recipient}: {e}", exc_info=True)

    def _build_html(self, query: str, notices: list[dict], alert_id: str = "") -> str:
        """Builds the HTML body for the alert email.

        Shows a summary count, top 5 results as a table,
        and a link back to the dashboard.

        Args:
            query: The search query string.
            notices: Full list of matched notices.
            alert_id: UUID of the alert configuration, appended to the
                dashboard URL to build the report link. Defaults to an
                empty string when no specific alert is referenced.

        Returns:
            HTML string ready to attach to the email.
        """
        report_url = (
            f"{self.dashboard_url}/report?alert_id={alert_id}"
            if alert_id
            else self.dashboard_url
        )
        rows = ""
        for n in notices[:5]:
            score = round(n.get("combined_score", 0), 2)
            rows += f"""
            <tr>
                <td style="padding:8px;border-bottom:1px solid #eee;">
                    {n.get(NoticeField.TITLE, "")}
                </td>
                <td style="padding:8px;border-bottom:1px solid #eee;">
                    {n.get(NoticeField.COUNTRY, "")}
                </td>
                <td style="padding:8px;border-bottom:1px solid #eee;">
                    {n.get(NoticeField.PUB_DATE, "")}
                </td>
                <td style="padding:8px;border-bottom:1px solid #eee;">
                    {score}
                </td>
                <td style="padding:8px;border-bottom:1px solid #eee;">
                    {n.get(NoticeField.ID, "")}
                </td>
            </tr>
            """

        return f"""
        <html>
        <body style="font-family:Arial,sans-serif;color:#333;max-width:700px;margin:auto;">
            <h2 style="color:#1a1a2e;">📋 Tender Alert: {query}</h2>
            <p><strong>{len(notices)} result(s)</strong> found since your last alert.</p>
            <table style="width:100%;border-collapse:collapse;font-size:14px;">
                <tr style="background:#f5f5f5;font-weight:bold;">
                    <td style="padding:8px;">Title</td>
                    <td style="padding:8px;">Country</td>
                    <td style="padding:8px;">Date</td>
                    <td style="padding:8px;">Score</td>
                    <td style="padding:8px;">ID</td>
                </tr>
                {rows}
            </table>
            {"<p style='color:#888;font-size:13px;'>+ " + str(len(notices) - 5) + " more results on the dashboard.</p>" if len(notices) > 5 else ""}
            <br>
            <a href="{report_url}"
               style="background:#4CAF50;color:white;padding:12px 24px;
                      text-decoration:none;border-radius:6px;font-size:15px;">
                View Full Report →
            </a>
            <p style="color:#bbb;font-size:11px;margin-top:30px;">
                Procurement Monitor — automated alert
            </p>
        </body>
        </html>
        """
