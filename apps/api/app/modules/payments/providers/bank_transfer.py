"""Offline bank transfer (Ecuador) — instructions + admin confirmation."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status

from app.modules.payments.models import PaymentStatus
from app.modules.payments.providers.base import (
    OrderAmountBreakdown,
    ProviderCreateResult,
    ProviderWebhookResult,
)
from app.modules.store_config.schemas import StoreConfigRead


def bank_account_configured(config: StoreConfigRead | None = None) -> bool:
    cfg = config or StoreConfigRead.from_settings()
    return cfg.bank_configured()


def bank_details_dict(config: StoreConfigRead | None = None) -> dict[str, str]:
    cfg = config or StoreConfigRead.from_settings()
    return cfg.bank_dict()


class BankTransferPaymentProvider:
    """Customer pays via wire transfer; admin confirms after verifying the deposit."""

    name = "bank_transfer"

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
        store_config: StoreConfigRead | None = None,
    ) -> ProviderCreateResult:
        _ = breakdown
        config = store_config or StoreConfigRead.from_settings()
        if not bank_account_configured(config):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Bank transfer is not configured. Set bank details in "
                    "Admin → Configuración (or BANK_* env for initial seed)."
                ),
            )
        bank = bank_details_dict(config)
        return ProviderCreateResult(
            provider_payment_id=f"bank_{payment_id}",
            status=PaymentStatus.PROCESSING.value,
            client_action={
                "type": "bank_transfer_instructions",
                "payment_id": str(payment_id),
                "reference": order_number,
                "amount": amount,
                "currency": currency,
                "bank": bank,
                "hint": (
                    "Realiza la transferencia con el monto exacto y usa el número "
                    "de orden como referencia. Luego pulsa «Ya transferí»."
                ),
                "customer_marked_transferred": False,
            },
            metadata={
                "order_id": str(order_id),
                "order_number": order_number,
                "amount": amount,
                "currency": currency,
                "method": method,
                "reference": order_number,
                "bank": bank,
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
            detail="Bank transfer payments are confirmed by an administrator",
        )
