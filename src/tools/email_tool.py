"""Email Tool — Send emails via SMTP or Gmail API.

SPESION can compose and send emails (complaints, follow-ups, business
correspondence) on your behalf.  All outgoing emails require user approval
through the human-in-the-loop gate.

Supports two backends:
  1. **Gmail API** (OAuth — reuses Google Calendar credentials)
  2. **SMTP** (any provider — Outlook, custom domain, etc.)

Requires (Gmail API):
  pip install google-auth google-auth-oauthlib google-api-python-client
  Same OAuth credentials as Google Calendar + Gmail scope

Requires (SMTP):
  .env:
    SMTP_HOST=smtp.gmail.com
    SMTP_PORT=587
    SMTP_USERNAME=you@gmail.com
    SMTP_PASSWORD=xxxx           (app password, NOT your real password)
    SMTP_FROM_NAME=Eric González
"""

from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


# ─── SMTP backend ────────────────────────────────────────────────────────────

def _send_via_smtp(
    to: str,
    subject: str,
    body_html: str,
    body_plain: str,
    cc: str | None = None,
    bcc: str | None = None,
    attachment_path: str | None = None,
) -> dict[str, Any]:
    """Send an email via SMTP."""
    from src.core.config import settings

    host = getattr(settings, "smtp_host", None) or "smtp.gmail.com"
    port = int(getattr(settings, "smtp_port", None) or 587)
    username = getattr(settings, "smtp_username", None)
    password = getattr(settings, "smtp_password", None)
    from_name = getattr(settings, "smtp_from_name", None) or "SPESION"

    if not username or not password:
        password_val = password.get_secret_value() if hasattr(password, "get_secret_value") else password
        if not username or not password_val:
            return {"error": "SMTP credentials not configured. Set SMTP_USERNAME and SMTP_PASSWORD in .env"}
    else:
        password_val = password.get_secret_value() if hasattr(password, "get_secret_value") else str(password)

    msg = MIMEMultipart("alternative")
    msg["From"] = f"{from_name} <{username}>"
    msg["To"] = to
    msg["Subject"] = subject
    if cc:
        msg["Cc"] = cc
    if bcc:
        msg["Bcc"] = bcc

    msg.attach(MIMEText(body_plain, "plain", "utf-8"))
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    # Attachment
    if attachment_path:
        p = Path(attachment_path)
        if p.exists():
            part = MIMEBase("application", "octet-stream")
            part.set_payload(p.read_bytes())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f"attachment; filename={p.name}")
            msg.attach(part)

    recipients = [to]
    if cc:
        recipients.extend(c.strip() for c in cc.split(","))
    if bcc:
        recipients.extend(b.strip() for b in bcc.split(","))

    try:
        with smtplib.SMTP(host, port) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(username, password_val)
            server.sendmail(username, recipients, msg.as_string())

        logger.info(f"📧 Email sent via SMTP to {to}: {subject}")
        return {
            "sent": True,
            "to": to,
            "subject": subject,
            "via": "smtp",
        }
    except Exception as e:
        logger.error(f"SMTP send failed: {e}")
        return {"error": str(e), "to": to, "subject": subject}


# ─── Gmail API backend ───────────────────────────────────────────────────────

def _send_via_gmail_api(
    to: str,
    subject: str,
    body_html: str,
    body_plain: str,
    cc: str | None = None,
) -> dict[str, Any]:
    """Send email via Gmail API using existing Google OAuth token."""
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        import base64
    except ImportError:
        return {"error": "google-api-python-client not installed. Use SMTP instead."}

    token_path = Path("./data/google_token.json")
    if not token_path.exists():
        return {"error": "No Google token found. Authenticate via Calendar first (python main.py --cli)."}

    try:
        creds = Credentials.from_authorized_user_file(
            str(token_path),
            scopes=["https://www.googleapis.com/auth/gmail.send"],
        )
    except Exception as e:
        return {"error": f"Google credentials error: {e}. Try re-authenticating."}

    msg = MIMEMultipart("alternative")
    msg["To"] = to
    msg["Subject"] = subject
    if cc:
        msg["Cc"] = cc
    msg.attach(MIMEText(body_plain, "plain", "utf-8"))
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")

    try:
        service = build("gmail", "v1", credentials=creds)
        result = service.users().messages().send(
            userId="me",
            body={"raw": raw},
        ).execute()

        logger.info(f"📧 Email sent via Gmail API to {to}: {subject}")
        return {
            "sent": True,
            "to": to,
            "subject": subject,
            "message_id": result.get("id"),
            "via": "gmail_api",
        }
    except Exception as e:
        logger.error(f"Gmail API send failed: {e}")
        return {"error": str(e), "to": to, "subject": subject}


# ─── Tools ────────────────────────────────────────────────────────────────────

@tool
def send_email(
    to: str,
    subject: str,
    body: str,
    cc: str | None = None,
    bcc: str | None = None,
    format: str = "plain",
    attachment_path: str | None = None,
    via: str = "smtp",
) -> dict[str, Any]:
    """Send an email on behalf of the user.

    ⚠️ DANGEROUS — requires user approval before execution.

    Args:
        to: Recipient email address
        subject: Email subject line
        body: Email body (plain text or HTML depending on format)
        cc: CC recipients (comma-separated)
        bcc: BCC recipients (comma-separated, SMTP only)
        format: "plain" or "html"
        attachment_path: Optional file path to attach
        via: "smtp" or "gmail_api"

    Returns:
        Dict with sent status and details.
    """
    if format == "html":
        body_html = body
        # Strip HTML tags for plain text version
        import re
        body_plain = re.sub(r"<[^>]+>", "", body)
    else:
        body_plain = body
        # Wrap plain text in minimal HTML
        body_html = f"<html><body><pre>{body}</pre></body></html>"

    if via == "gmail_api":
        return _send_via_gmail_api(to, subject, body_html, body_plain, cc=cc)
    else:
        return _send_via_smtp(to, subject, body_html, body_plain, cc=cc, bcc=bcc, attachment_path=attachment_path)


@tool
def draft_email(
    to: str,
    subject: str,
    purpose: str,
    tone: str = "professional",
    language: str = "es",
) -> dict[str, Any]:
    """Draft an email without sending it. Returns the composed email for review.

    Use this to compose a complaint, follow-up, business email, etc.
    The user can review and approve before calling send_email.

    Args:
        to: Recipient email address
        subject: Email subject line
        purpose: What the email should achieve (e.g. "complain about wrong gas receipt")
        tone: "professional", "formal", "friendly", "assertive"
        language: "es" (Spanish) or "en" (English)

    Returns:
        Dict with drafted subject and body for review.
    """
    # This tool just returns the parameters — the LLM agent will compose
    # the actual body in its response using these instructions.
    return {
        "action": "draft_ready",
        "to": to,
        "subject": subject,
        "purpose": purpose,
        "tone": tone,
        "language": language,
        "instructions": (
            f"Compose a {tone} email in {language} to {to} about: {purpose}. "
            f"Subject: {subject}. "
            "Return the full email body. The user will review before sending."
        ),
    }


@tool
def check_email_config() -> dict[str, Any]:
    """Check if email sending is configured and which backend is available.

    Returns:
        Dict with SMTP and Gmail API availability status.
    """
    from src.core.config import settings

    smtp_ok = bool(
        getattr(settings, "smtp_username", None)
        and getattr(settings, "smtp_password", None)
    )

    gmail_ok = Path("./data/google_token.json").exists()

    return {
        "smtp_configured": smtp_ok,
        "smtp_host": getattr(settings, "smtp_host", "not set"),
        "gmail_api_available": gmail_ok,
        "recommended": "gmail_api" if gmail_ok else ("smtp" if smtp_ok else "none"),
        "setup_instructions": (
            "For SMTP: set SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD in .env. "
            "For Gmail API: authenticate via Google Calendar first."
        ) if not smtp_ok and not gmail_ok else None,
    }


# ─── Factory ──────────────────────────────────────────────────────────────────

def create_email_tools() -> list:
    """Return all email tools."""
    return [send_email, draft_email, check_email_config]
