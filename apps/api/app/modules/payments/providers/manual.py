import hashlib
import hmac
import json
from uuid import UUID

from fastapi import HTTPException, status

from app.core.config import settings
from app.core.security import secrets_equal
from app.modules.payments.models import PaymentStatus
from app.modules.payments.providers.base import (
    OrderAmountBreakdown,
    ProviderCreateResult,
    ProviderWebhookResult,
)


class ManualPaymentProvider:
    """Dev/staging stand-in. Prefer PayPhone (or another PSP) outside local development.

    Webhooks are authenticated with header ``X-GEMA-Payment-Secret``.
    """

    name = "manual"

    def create_payment(
        self,
        *,
        payment_id: UUID,
        order_id: UUID,
        order_number: str,
        amount: str,
        currency: str,
        method: str,
        breakdown: OrderAmountBreakdown | None = None,
    ) -> ProviderCreateResult:
        _ = breakdown
        provider_payment_id = f"manual_{payment_id}"
        return ProviderCreateResult(
            provider_payment_id=provider_payment_id,
            status=PaymentStatus.PROCESSING.value,
            client_action={
                "type": "manual_pending",
                "payment_id": str(payment_id),
                "hint": "Payment pending operator confirmation or signed webhook",
            },
            metadata={
                "order_id": str(order_id),
                "order_number": order_number,
                "amount": amount,
                "currency": currency,
                "method": method,
            },
        )

    def get_payment_status(self, provider_payment_id: str) -> str:
        return PaymentStatus.PROCESSING.value

    def cancel_payment(self, provider_payment_id: str) -> None:
        return None

    def handle_webhook(
        self,
        *,
        headers: dict[str, str],
        body: bytes,
    ) -> ProviderWebhookResult:
        secret = headers.get("x-gema-payment-secret") or headers.get(
            "X-GEMA-Payment-Secret"
        )
        expected = settings.payment_webhook_secret
        if not secrets_equal(secret, expected):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature",
            )
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid webhook payload",
            ) from exc

        event_id = str(payload.get("event_id") or "")
        event_type = str(payload.get("event_type") or "")
        payment_id_raw = payload.get("payment_id")
        if not event_id or not event_type or not payment_id_raw:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="event_id, event_type and payment_id are required",
            )
        try:
            payment_id = UUID(str(payment_id_raw))
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid payment_id",
            ) from exc

        if event_type == "payment.succeeded":
            outcome = "succeeded"
        elif event_type == "payment.failed":
            outcome = "failed"
        else:
            outcome = "ignored"

        return ProviderWebhookResult(
            provider_event_id=event_id,
            event_type=event_type,
            payment_id=payment_id,
            provider_payment_id=f"manual_{payment_id}",
            outcome=outcome,
            payload=payload if isinstance(payload, dict) else {},
        )


def webhook_signature_for_tests(body: bytes) -> str:
    """Helper for tests — not used in production auth."""
    return hmac.new(
        settings.payment_webhook_secret.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
