from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.pricing.models import PriceCurrency, PriceType


class ProductPriceCreate(BaseModel):
    price_type: PriceType = PriceType.RETAIL
    amount: Decimal = Field(ge=0, max_digits=14, decimal_places=4)
    currency: PriceCurrency = PriceCurrency.USD
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    is_active: bool = True
    cost_reference: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=4)
    supplier_product_id: UUID | None = None

    @model_validator(mode="after")
    def validate_range(self) -> "ProductPriceCreate":
        if self.ends_at is not None and self.starts_at is not None:
            if self.ends_at <= self.starts_at:
                raise ValueError("ends_at must be after starts_at")
        return self


class ProductPriceUpdate(BaseModel):
    amount: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=4)
    currency: PriceCurrency | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    is_active: bool | None = None
    cost_reference: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=4)
    supplier_product_id: UUID | None = None


class PublicPrice(BaseModel):
    amount: Decimal
    currency: PriceCurrency
    price_type: PriceType
    compare_at_amount: Decimal | None = None


class EffectivePrice(BaseModel):
    """Canonical storefront/checkout price: PROMOTIONAL if active, else RETAIL."""

    amount: Decimal
    currency: PriceCurrency
    price_type: PriceType
    compare_at_amount: Decimal | None = None

    @property
    def unit_discount(self) -> Decimal:
        if self.compare_at_amount is None:
            return Decimal("0")
        delta = Decimal(self.compare_at_amount) - Decimal(self.amount)
        return delta if delta > 0 else Decimal("0")


class ProductPriceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID
    price_type: PriceType
    amount: Decimal
    currency: PriceCurrency
    starts_at: datetime
    ends_at: datetime | None
    is_active: bool
    cost_reference: Decimal | None
    supplier_product_id: UUID | None
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    created_by_email: str | None = None
    supplier_name: str | None = None


class MarginResult(BaseModel):
    sale_price: Decimal
    cost: Decimal
    margin_amount: Decimal
    margin_percentage: Decimal | None
    cost_source: str | None = None


class MarginRequest(BaseModel):
    sale_price: Decimal = Field(ge=0, max_digits=14, decimal_places=4)
    cost: Decimal = Field(ge=0, max_digits=14, decimal_places=4)
    cost_source: str | None = None
