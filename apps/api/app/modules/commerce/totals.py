"""Single source of truth for checkout order totals."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.modules.commerce.shipping import calculate_shipping
from app.modules.commerce.tax import calculate_tax
from app.modules.orders.schemas import ShippingAddress
from app.modules.store_config.schemas import StoreConfigRead


def _money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal("0.0001"))


@dataclass(frozen=True)
class OrderTotals:
    subtotal: Decimal
    discount_total: Decimal
    shipping_total: Decimal
    tax_total: Decimal
    total: Decimal
    shipping_method: str


def compute_order_totals(
    *,
    subtotal: Decimal,
    discount_total: Decimal,
    shipping_address: ShippingAddress | None,
    store_config: StoreConfigRead | None = None,
    tax_regime: str | None = None,
) -> OrderTotals:
    subtotal = _money(subtotal)
    discount_total = _money(discount_total)
    merchandise = _money(subtotal - discount_total)
    if merchandise < 0:
        merchandise = Decimal("0.0000")

    shipping_total, shipping_method = calculate_shipping(
        subtotal=subtotal,
        discount_total=discount_total,
        shipping_address=shipping_address,
        store_config=store_config,
    )
    tax_total = calculate_tax(taxable_subtotal=merchandise, tax_regime=tax_regime)
    total = _money(merchandise + shipping_total + tax_total)

    return OrderTotals(
        subtotal=subtotal,
        discount_total=discount_total,
        shipping_total=shipping_total,
        tax_total=tax_total,
        total=total,
        shipping_method=shipping_method,
    )
