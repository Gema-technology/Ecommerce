"""Cash on delivery — only for admin-trusted customers; admin confirms after delivery."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status

from app.modules.payments.models import PaymentStatus
from app.modules.payments.providers.base import (
    OrderAmountBreakdown,
    ProviderCreateResult,
    ProviderWebhookResult,
)


class CashOnDeliveryPaymentProvider:
    name = "cash_on_delivery"

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
        return ProviderCreateResult(
            provider_payment_id=f"cod_{payment_id}",
            status=PaymentStatus.PROCESSING.value,
            client_action={
                "type": "cash_on_delivery_pending",
                "payment_id": str(payment_id),
                "reference": order_number,
                "amount": amount,
                "currency": currency,
                "hint": (
                    "Pagarás en efectivo al recibir el pedido. "
                    "Un operador confirmará el cobro al entregar."
                ),
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
        _ = provider_payment_id
        return PaymentStatus.PROCESSING.value

    def cancel_payment(self, provider_payment_id: str) -> None:
        return None

    def handle_webhook(
        self,
        *,
        headers: dict[str, str],
        body: bytes,
    ) -> ProviderWebhookResult:
        _ = headers, body
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cash on delivery payments are confirmed by an administrator",
        )
