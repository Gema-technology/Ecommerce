"""Simple configurable shipping for MVP (zones/carriers deferred)."""

from __future__ import annotations

from decimal import Decimal

from app.modules.orders.schemas import ShippingAddress
from app.modules.store_config.schemas import StoreConfigRead


def _money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal("0.0001"))


def calculate_shipping(
    *,
    subtotal: Decimal,
    discount_total: Decimal,
    shipping_address: ShippingAddress | None,
    store_config: StoreConfigRead | None = None,
) -> tuple[Decimal, str]:
    """Return (shipping_total, method_label)."""
    config = store_config or StoreConfigRead.from_settings()
    if not config.shipping_enabled:
        return Decimal("0.0000"), "standard"

    merchandise = _money(subtotal - discount_total)
    threshold = config.shipping_free_threshold
    if threshold is not None and merchandise >= _money(threshold):
        return Decimal("0.0000"), "free"

    base = _money(config.shipping_flat_rate)
    if shipping_address is not None:
        province_key = shipping_address.province.strip().lower()
        for name, rate in config.shipping_province_rates.items():
            if name.strip().lower() == province_key:
                return _money(rate), "province_flat"

    return base, "standard"
