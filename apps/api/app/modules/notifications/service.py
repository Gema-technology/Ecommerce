"""Order transactional email — claim/dedupe then best-effort SMTP send."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.notifications.models import NotificationDispatch
from app.modules.notifications.smtp import EmailMessagePayload, SmtpTransport
from app.modules.notifications.templates import (
    build_order_created,
    build_order_paid,
    build_order_shipped,
)
from app.modules.orders.models import Order

logger = logging.getLogger(__name__)

EVENT_ORDER_CREATED = "order.created"
EVENT_ORDER_PAID = "order.paid"
EVENT_ORDER_SHIPPED = "order.shipped"

_STATUS_CLAIMED = "claimed"
_STATUS_SENT = "accepted"  # MTA accepted — not proof of inbox delivery
_STATUS_SKIPPED = "skipped"
_STATUS_FAILED = "failed"


class EmailTransport(Protocol):
    def send(self, message: EmailMessagePayload) -> str: ...


_builders = {
    EVENT_ORDER_CREATED: build_order_created,
    EVENT_ORDER_PAID: build_order_paid,
    EVENT_ORDER_SHIPPED: build_order_shipped,
}

# Test override — set via set_email_transport / reset in fixtures.
_transport_override: EmailTransport | None = None


def set_email_transport(transport: EmailTransport | None) -> None:
    global _transport_override
    _transport_override = transport


def get_email_transport() -> EmailTransport:
    if _transport_override is not None:
        return _transport_override
    return SmtpTransport()


class NotificationService:
    def __init__(self, db: Session, transport: EmailTransport | None = None) -> None:
        self.db = db
        self.transport = transport or get_email_transport()

    def notify_order_event(self, order: Order, event_key: str) -> NotificationDispatch | None:
        """Claim unique dispatch then attempt send. Never raises to callers."""
        if event_key not in _builders:
            logger.warning("unknown_notification_event event=%s", event_key)
            return None

        recipient = (order.customer_email or "").strip()
        dispatch = NotificationDispatch(
            order_id=order.id,
            event_key=event_key,
            channel="email",
            recipient=recipient or None,
            status=_STATUS_CLAIMED,
            detail=None,
        )
        try:
            self.db.add(dispatch)
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            logger.info(
                "notification_deduped order_id=%s event=%s",
                order.id,
                event_key,
            )
            return None
        except Exception:
            self.db.rollback()
            logger.exception(
                "notification_claim_failed order_id=%s event=%s", order.id, event_key
            )
            return None

        if not recipient:
            return self._finalize(
                dispatch,
                status=_STATUS_SKIPPED,
                detail="no_customer_email",
            )

        if not settings.email_enabled:
            return self._finalize(
                dispatch,
                status=_STATUS_SKIPPED,
                detail="email_disabled",
            )

        if not (settings.smtp_host or "").strip():
            return self._finalize(
                dispatch,
                status=_STATUS_SKIPPED,
                detail="smtp_not_configured",
            )

        builder = _builders[event_key]
        app_url = (settings.public_app_url or "").strip().rstrip("/")
        subject, text_body, html_body = builder(order, app_url=app_url)
        try:
            result = self.transport.send(
                EmailMessagePayload(
                    to_address=recipient,
                    subject=subject,
                    text_body=text_body,
                    html_body=html_body,
                )
            )
            return self._finalize(
                dispatch,
                status=_STATUS_SENT,
                detail=result[:500],
                sent=True,
            )
        except Exception as exc:
            logger.exception(
                "notification_send_failed order_id=%s event=%s", order.id, event_key
            )
            return self._finalize(
                dispatch,
                status=_STATUS_FAILED,
                detail=str(exc)[:500],
            )

    def _finalize(
        self,
        dispatch: NotificationDispatch,
        *,
        status: str,
        detail: str | None,
        sent: bool = False,
    ) -> NotificationDispatch:
        try:
            row = self.db.get(NotificationDispatch, dispatch.id)
            if row is None:
                return dispatch
            row.status = status
            row.detail = detail
            if sent:
                row.sent_at = datetime.now(UTC)
            self.db.commit()
            logger.info(
                "notification_result order_id=%s event=%s status=%s detail=%s",
                row.order_id,
                row.event_key,
                row.status,
                row.detail,
            )
            return row
        except Exception:
            self.db.rollback()
            logger.exception("notification_finalize_failed id=%s", dispatch.id)
            return dispatch


def notify_order_event(db: Session, order_id: UUID, event_key: str) -> None:
    """Load order and dispatch notification; swallow all errors."""
    try:
        order = db.get(Order, order_id)
        if order is None:
            return
        NotificationService(db).notify_order_event(order, event_key)
    except Exception:
        logger.exception(
            "notify_order_event_failed order_id=%s event=%s", order_id, event_key
        )
