"""Ecuador IVA (opción A): precio + impuesto en checkout cuando está habilitado."""

from __future__ import annotations

from decimal import Decimal

from app.core.config import settings


def _money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal("0.0001"))


def calculate_tax(*, taxable_subtotal: Decimal) -> Decimal:
    """
    Flat IVA on merchandise (subtotal − discounts).

    Sprint A3 opción A: enable via COMMERCE_TAX_ENABLED=true so checkout,
    PayPhone amount, and SRI factura share the same order.total.
    Shipping is not included in the taxable base in v1 (matches checkout totals).
    """
    if not settings.commerce_tax_enabled:
        return Decimal("0.0000")
    rate = _money(settings.commerce_tax_rate)
    if rate <= 0:
        return Decimal("0.0000")
    return _money(taxable_subtotal * rate)
