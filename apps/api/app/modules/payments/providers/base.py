from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID


@dataclass
class ProviderCreateResult:
    provider_payment_id: str
    status: str  # PENDING | PROCESSING
    client_action: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderWebhookResult:
    provider_event_id: str
    event_type: str
    payment_id: UUID | None
    provider_payment_id: str | None
    outcome: str  # succeeded | failed | ignored
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OrderAmountBreakdown:
    """Server-side order money used by providers that need tax splits (e.g. PayPhone)."""

    total: Decimal
    subtotal: Decimal
    tax_total: Decimal
    shipping_total: Decimal
    discount_total: Decimal


class PaymentProvider(Protocol):
    name: str

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
    ) -> ProviderCreateResult: ...

    def get_payment_status(self, provider_payment_id: str) -> str: ...

    def cancel_payment(self, provider_payment_id: str) -> None: ...

    def handle_webhook(
        self,
        *,
        headers: dict[str, str],
        body: bytes,
    ) -> ProviderWebhookResult: ...
