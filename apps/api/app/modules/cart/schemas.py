from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.pricing.models import PriceCurrency, PriceType
from app.modules.products.schemas import AvailabilityStatus


class CartItemCreate(BaseModel):
    product_id: UUID
    quantity: int = Field(default=1, ge=1)


class CartItemUpdate(BaseModel):
    quantity: int = Field(ge=0)


class CartProductPrice(BaseModel):
    amount: Decimal
    currency: PriceCurrency
    price_type: PriceType | None = None


class CartProductSummary(BaseModel):
    id: UUID
    name: str
    slug: str
    sku: str
    image: str | None = None
    price: CartProductPrice | None = None
    is_active: bool
    availability: AvailabilityStatus = AvailabilityStatus.UNKNOWN


class CartItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product: CartProductSummary
    quantity: int
    unit_price: Decimal | None = None
    unit_discount: Decimal = Decimal("0")
    line_discount: Decimal = Decimal("0")
    line_total: Decimal | None = None
    quoted_unit_price: Decimal | None = None
    price_changed: bool = False
    available: bool = True


class CartRead(BaseModel):
    id: UUID
    status: str
    items: list[CartItemRead]
    subtotal: Decimal
    discount_total: Decimal = Decimal("0")
    currency: PriceCurrency = PriceCurrency.USD
    item_count: int
    has_price_changes: bool = False
