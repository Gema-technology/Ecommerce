from decimal import Decimal, ROUND_HALF_UP

MONEY_QUANT = Decimal("0.0001")


def quantize_money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def cost_real(cost_price: Decimal, other_costs: Decimal) -> Decimal:
    return quantize_money(Decimal(cost_price) + Decimal(other_costs))


def price_from_margin(cost_real_value: Decimal, margin: Decimal) -> Decimal:
    margin_dec = Decimal(margin)
    if margin_dec >= Decimal("1"):
        raise ValueError("Margin must be less than 1")
    if margin_dec < Decimal("0"):
        raise ValueError("Margin must be non-negative")
    base = Decimal(cost_real_value)
    if base <= Decimal("0"):
        return Decimal("0")
    return quantize_money(base / (Decimal("1") - margin_dec))


def compute_tier_prices(
    cost_price: Decimal,
    other_costs: Decimal,
    *,
    min_margin: Decimal,
    rec_margin: Decimal,
    high_margin: Decimal,
) -> dict[str, Decimal]:
    real = cost_real(cost_price, other_costs)
    return {
        "cost_real": real,
        "price_min": price_from_margin(real, min_margin),
        "price_rec": price_from_margin(real, rec_margin),
        "price_high": price_from_margin(real, high_margin),
    }


def resolve_unit_price(
    product: "QuoteProductLike",
    tier: str,
    *,
    min_margin: Decimal,
    rec_margin: Decimal,
    high_margin: Decimal,
    manual_price: Decimal | None = None,
) -> Decimal:
    prices = compute_tier_prices(
        product.cost_price,
        product.other_costs,
        min_margin=min_margin,
        rec_margin=rec_margin,
        high_margin=high_margin,
    )
    if tier == "min":
        return prices["price_min"]
    if tier == "rec":
        return prices["price_rec"]
    if tier == "high":
        return prices["price_high"]
    if tier == "manual":
        if manual_price is None:
            raise ValueError("manual_price required for manual tier")
        return quantize_money(Decimal(manual_price))
    raise ValueError(f"Invalid tier: {tier}")


def compute_quote_totals(
    items: list[tuple[int, Decimal]],
    iva_pct: Decimal,
) -> tuple[Decimal, Decimal, Decimal]:
    subtotal = Decimal("0")
    for quantity, unit_price in items:
        qty = int(quantity)
        if qty <= 0:
            raise ValueError("Quantity must be positive")
        line = quantize_money(Decimal(unit_price) * qty)
        subtotal += line
    subtotal = quantize_money(subtotal)
    iva_amount = quantize_money(subtotal * Decimal(iva_pct))
    total = quantize_money(subtotal + iva_amount)
    return subtotal, iva_amount, total


class QuoteProductLike:
    cost_price: Decimal
    other_costs: Decimal
