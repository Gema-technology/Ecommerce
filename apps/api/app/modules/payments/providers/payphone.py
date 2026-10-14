"""PayPhone (Ecuador) payment provider — API Link + Sale status + external notify."""

from __future__ import annotations

import json
import logging
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status

from app.core.config import settings
from app.modules.payments.models import PaymentStatus
from app.modules.payments.providers.base import (
    OrderAmountBreakdown,
    ProviderCreateResult,
    ProviderWebhookResult,
)
from app.modules.payments.providers.payphone_client import (
    PayPhoneApiError,
    PayPhoneHttpClient,
    UrllibPayPhoneClient,
)

logger = logging.getLogger(__name__)

# PayPhone statusCode: 1 pending, 2 cancelled/rejected, 3 approved
_STATUS_PENDING = 1
_STATUS_REJECTED = 2
_STATUS_APPROVED = 3


def money_to_cents(value: Decimal | str) -> int:
    quantized = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return int(quantized * 100)


def client_transaction_id_for(payment_id: UUID) -> str:
    """PayPhone requires unique clientTransactionId with max length 15."""
    return payment_id.hex[:15]


def build_link_amounts(breakdown: OrderAmountBreakdown) -> dict[str, int]:
    """Map GEMA order totals to PayPhone cent fields.

    When tax is zero (default GEMA MVP), send the full total as amountWithoutTax.
    When tax > 0, taxable base ≈ subtotal − discount, tax = tax_total, shipping
    as amountWithoutTax (common Ecuador e-commerce split).
    """
    total_cents = money_to_cents(breakdown.total)
    tax_cents = money_to_cents(breakdown.tax_total)
    shipping_cents = money_to_cents(breakdown.shipping_total)

    if tax_cents <= 0:
        return {
            "amount": total_cents,
            "amountWithoutTax": total_cents,
            "amountWithTax": 0,
            "tax": 0,
            "service": 0,
            "tip": 0,
        }

    taxable_base = breakdown.subtotal - breakdown.discount_total
    if taxable_base < 0:
        taxable_base = Decimal("0")
    with_tax = money_to_cents(taxable_base)
    without_tax = shipping_cents
    # Keep PayPhone identity: amount == sum of parts. Adjust without_tax if needed.
    parts = with_tax + tax_cents + without_tax
    if parts != total_cents:
        without_tax = max(0, total_cents - with_tax - tax_cents)
        parts = with_tax + tax_cents + without_tax
    if parts != total_cents:
        # Last resort: collapse to untaxed total so the link matches order.total.
        return {
            "amount": total_cents,
            "amountWithoutTax": total_cents,
            "amountWithTax": 0,
            "tax": 0,
            "service": 0,
            "tip": 0,
        }
    return {
        "amount": total_cents,
        "amountWithoutTax": without_tax,
        "amountWithTax": with_tax,
        "tax": tax_cents,
        "service": 0,
        "tip": 0,
    }


class PayPhonePaymentProvider:
    """Checkout via PayPhone payment links (Ecuador, USD)."""

    name = "payphone"

    def __init__(self, client: PayPhoneHttpClient | None = None) -> None:
        self._client = client or UrllibPayPhoneClient(settings.payphone_api_base)

    def _require_credentials(self) -> tuple[str, str]:
        token = (settings.payphone_token or "").strip()
        store_id = (settings.payphone_store_id or "").strip()
        if not token or not store_id:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "PayPhone is not configured. Set PAYPHONE_TOKEN and "
                    "PAYPHONE_STORE_ID."
                ),
            )
        return token, store_id

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
        if currency.upper() != "USD":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="PayPhone provider currently supports USD only",
            )
        token, store_id = self._require_credentials()
        bd = breakdown or OrderAmountBreakdown(
            total=Decimal(amount),
            subtotal=Decimal(amount),
            tax_total=Decimal("0"),
            shipping_total=Decimal("0"),
            discount_total=Decimal("0"),
        )
        amounts = build_link_amounts(bd)
        client_tx = client_transaction_id_for(payment_id)
        expire_hours = max(1, min(settings.reservation_ttl_hours, 168))
        body = {
            **amounts,
            "currency": "USD",
            "clientTransactionId": client_tx,
            "storeId": store_id,
            "reference": order_number[:100],
            "additionalData": f"GEMA payment {payment_id}"[:250],
            "oneTime": True,
            "expireIn": expire_hours,
            "isAmountEditable": False,
        }
        try:
            result = self._client.request(
                "POST", "/api/Links", token=token, json_body=body
            )
        except PayPhoneApiError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="PayPhone rejected the payment link request",
            ) from exc

        payment_url = _extract_payment_url(result)
        if not payment_url:
            logger.error("PayPhone Links response missing URL")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="PayPhone did not return a payment URL",
            )

        return ProviderCreateResult(
            provider_payment_id=client_tx,
            status=PaymentStatus.PROCESSING.value,
            client_action={
                "type": "redirect",
                "url": payment_url,
                "payment_id": str(payment_id),
                "hint": (
                    "Completa el pago en PayPhone. Luego vuelve y verifica el estado; "
                    "la confirmación la hace el servidor."
                ),
            },
            metadata={
                "order_id": str(order_id),
                "order_number": order_number,
                "amount": amount,
                "amount_cents": amounts["amount"],
                "currency": currency,
                "method": method,
                "client_transaction_id": client_tx,
                "payment_url": payment_url,
                "store_id": store_id,
            },
        )

    def get_payment_status(self, provider_payment_id: str) -> str:
        token, _store = self._require_credentials()
        try:
            result = self._client.request(
                "GET",
                f"/api/Sale/client/{provider_payment_id}",
                token=token,
            )
        except PayPhoneApiError as exc:
            if exc.status_code == 404:
                return PaymentStatus.PROCESSING.value
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="PayPhone status lookup failed",
            ) from exc
        return status_from_payphone_payload(result)

    def cancel_payment(self, provider_payment_id: str) -> None:
        return None

    def handle_webhook(
        self,
        *,
        headers: dict[str, str],
        body: bytes,
    ) -> ProviderWebhookResult:
        """Parse PayPhone Notificacion Externa JSON (approved payments)."""
        _ = headers  # optional shared secret checked in router when configured
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid PayPhone webhook payload",
            ) from exc
        if not isinstance(payload, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid PayPhone webhook payload",
            )

        expected_store = (settings.payphone_store_id or "").strip()
        store_id = str(payload.get("StoreId") or payload.get("storeId") or "").strip()
        if expected_store:
            if not store_id or store_id != expected_store:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid PayPhone store",
                )

        client_tx = str(
            payload.get("ClientTransactionId") or payload.get("clientTransactionId") or ""
        ).strip()
        transaction_id = payload.get("TransactionId", payload.get("transactionId"))
        status_code = payload.get("StatusCode", payload.get("statusCode"))
        try:
            status_code_int = int(status_code) if status_code is not None else 0
        except (TypeError, ValueError):
            status_code_int = 0

        if not client_tx or transaction_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ClientTransactionId and TransactionId are required",
            )

        # Approved notifications must carry Amount so we can match order payment.
        if status_code_int == _STATUS_APPROVED:
            raw_amount = payload.get("Amount", payload.get("amount"))
            if raw_amount is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Amount is required for approved PayPhone notifications",
                )

        payment_id = _payment_id_from_client_tx(client_tx)
        event_id = f"payphone-{transaction_id}"

        if status_code_int == _STATUS_APPROVED:
            outcome = "succeeded"
            event_type = "payment.succeeded"
        elif status_code_int == _STATUS_REJECTED:
            outcome = "failed"
            event_type = "payment.failed"
        else:
            outcome = "ignored"
            event_type = "payment.pending"

        return ProviderWebhookResult(
            provider_event_id=event_id,
            event_type=event_type,
            payment_id=payment_id,
            provider_payment_id=client_tx,
            outcome=outcome,
            payload=payload,
        )

    def sync_from_remote(self, client_transaction_id: str) -> ProviderWebhookResult:
        """Poll Sale API and build a webhook-equivalent result for confirm/sync."""
        token, _store = self._require_credentials()
        try:
            result = self._client.request(
                "GET",
                f"/api/Sale/client/{client_transaction_id}",
                token=token,
            )
        except PayPhoneApiError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="PayPhone status lookup failed",
            ) from exc

        # Sale API may return a list for some queries — normalize.
        if isinstance(result, list):
            if not result:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="PayPhone has no transaction for this payment yet",
                )
            result = result[0]
        if not isinstance(result, dict):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Unexpected PayPhone status response",
            )

        status_code = result.get("statusCode", result.get("StatusCode"))
        try:
            status_code_int = int(status_code) if status_code is not None else 0
        except (TypeError, ValueError):
            status_code_int = 0

        transaction_id = result.get("transactionId", result.get("TransactionId"))
        client_tx = str(
            result.get("clientTransactionId")
            or result.get("ClientTransactionId")
            or client_transaction_id
        )
        payment_id = _payment_id_from_client_tx(client_tx)
        if transaction_id is None:
            event_id = f"payphone-sync-{client_tx}-{status_code_int}"
        else:
            event_id = f"payphone-{transaction_id}"

        if status_code_int == _STATUS_APPROVED:
            outcome = "succeeded"
            event_type = "payment.succeeded"
        elif status_code_int == _STATUS_REJECTED:
            outcome = "failed"
            event_type = "payment.failed"
        elif status_code_int == _STATUS_PENDING:
            outcome = "ignored"
            event_type = "payment.pending"
        else:
            outcome = "ignored"
            event_type = "payment.unknown"

        return ProviderWebhookResult(
            provider_event_id=event_id,
            event_type=event_type,
            payment_id=payment_id,
            provider_payment_id=client_tx,
            outcome=outcome,
            payload=result if isinstance(result, dict) else {},
        )


def status_from_payphone_payload(payload: Any) -> str:
    if isinstance(payload, list) and payload:
        payload = payload[0]
    if not isinstance(payload, dict):
        return PaymentStatus.PROCESSING.value
    status_code = payload.get("statusCode", payload.get("StatusCode"))
    try:
        code = int(status_code)
    except (TypeError, ValueError):
        return PaymentStatus.PROCESSING.value
    if code == _STATUS_APPROVED:
        return PaymentStatus.SUCCEEDED.value
    if code == _STATUS_REJECTED:
        return PaymentStatus.FAILED.value
    return PaymentStatus.PROCESSING.value


def _extract_payment_url(result: Any) -> str | None:
    if isinstance(result, str) and result.startswith("http"):
        return result
    if isinstance(result, dict):
        for key in ("paymentUrl", "url", "link", "paymentLink"):
            value = result.get(key)
            if isinstance(value, str) and value.startswith("http"):
                return value
    return None


def _payment_id_from_client_tx(client_tx: str) -> UUID | None:
    """Best-effort: client_tx is payment_id.hex[:15]; full UUID needs DB lookup.

    Webhook/sync resolve payment via repository by provider_payment_id (= client_tx).
    payment_id on the result is optional; service uses provider_payment_id lookup.
    """
    _ = client_tx
    return None
