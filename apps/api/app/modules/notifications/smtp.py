"""SMTP transport — stdlib only; never logs credentials."""

from __future__ import annotations

import logging
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmailMessagePayload:
    to_address: str
    subject: str
    text_body: str
    html_body: str


class SmtpTransport:
    """Synchronous SMTP sender. Acceptance by the MTA ≠ inbox delivery."""

    def send(self, message: EmailMessagePayload) -> str:
        from_addr = (settings.smtp_from or settings.business_email or "").strip()
        if not from_addr:
            raise RuntimeError("SMTP_FROM (or BUSINESS_EMAIL) is not configured")

        msg = EmailMessage()
        msg["Subject"] = message.subject
        msg["From"] = from_addr
        msg["To"] = message.to_address
        msg.set_content(message.text_body)
        msg.add_alternative(message.html_body, subtype="html")

        host = (settings.smtp_host or "").strip()
        if not host:
            raise RuntimeError("SMTP_HOST is not configured")

        timeout = max(1.0, float(settings.smtp_timeout_seconds))
        port = int(settings.smtp_port)
        use_tls = bool(settings.smtp_use_tls)
        user = (settings.smtp_user or "").strip()
        password = settings.smtp_password or ""

        logger.info(
            "smtp_send_attempt host=%s port=%s tls=%s to=%s subject=%s",
            host,
            port,
            use_tls,
            message.to_address,
            message.subject,
        )

        if use_tls and port == 465:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, timeout=timeout, context=context) as smtp:
                if user:
                    smtp.login(user, password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=timeout) as smtp:
                if use_tls:
                    context = ssl.create_default_context()
                    smtp.starttls(context=context)
                if user:
                    smtp.login(user, password)
                smtp.send_message(msg)

        # We only know the MTA accepted the message, not that it was delivered.
        return "accepted_by_smtp"


class MemoryTransport:
    """Test double that records payloads without network I/O."""

    def __init__(self) -> None:
        self.sent: list[EmailMessagePayload] = []
        self.fail_next = False

    def send(self, message: EmailMessagePayload) -> str:
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("simulated SMTP failure")
        self.sent.append(message)
        return "accepted_by_memory"
