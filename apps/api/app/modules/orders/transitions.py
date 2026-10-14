"""Admin fulfillment transition rules (domain — no payment status changes)."""

from __future__ import annotations

from app.modules.orders.models import OrderStatus

# Forward-only fulfillment chain. Cancel remains PENDING_PAYMENT-only elsewhere.
FULFILLMENT_NEXT: dict[str, str] = {
    OrderStatus.PAID.value: OrderStatus.PROCESSING.value,
    OrderStatus.PROCESSING.value: OrderStatus.SHIPPED.value,
    OrderStatus.SHIPPED.value: OrderStatus.DELIVERED.value,
}

FULFILLMENT_TARGETS = frozenset(FULFILLMENT_NEXT.values())


def allowed_next_status(current: str) -> str | None:
    return FULFILLMENT_NEXT.get(current)


def allowed_transitions_for(current: str) -> list[str]:
    nxt = allowed_next_status(current)
    return [nxt] if nxt else []


def is_valid_fulfillment_transition(current: str, target: str) -> bool:
    return FULFILLMENT_NEXT.get(current) == target
