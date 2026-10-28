"""Ecuador IVA (opción A): precio + impuesto en checkout cuando está habilitado."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.config import settings

RIMPE_NEGOCIO_POPULAR = "RIMPE_NEGOCIO_POPULAR"


def _money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal("0.0001"))


def store_tax_regime(db: Session) -> str | None:
    from app.modules.sri.models import SriConfig

    row = db.get(SriConfig, 1)
    if row is None:
        return None
    return row.tax_regime


def charges_iva(*, tax_regime: str | None) -> bool:
    """RIMPE Negocio Popular no percibe IVA. Emprendedor y régimen general sí."""
    if tax_regime == RIMPE_NEGOCIO_POPULAR:
        return False
    return bool(settings.commerce_tax_enabled)


def calculate_tax(*, taxable_subtotal: Decimal, tax_regime: str | None = None) -> Decimal:
    """
    Flat IVA on merchandise (subtotal − discounts).

    Sprint A3 opción A: enable via COMMERCE_TAX_ENABLED=true so checkout,
    PayPhone amount, and SRI factura share the same order.total.
    Shipping is not included in the taxable base in v1 (matches checkout totals).
    RIMPE Negocio Popular stays at zero even when the store rate is 15%.
    """
    if not charges_iva(tax_regime=tax_regime):
        return Decimal("0.0000")
    rate = _money(settings.commerce_tax_rate)
    if rate <= 0:
        return Decimal("0.0000")
    return _money(taxable_subtotal * rate)
