from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.quotes.models import QuotePriceTier, QuoteStatus


class PricingConfigRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    min_margin: Decimal
    rec_margin: Decimal
    high_margin: Decimal
    card_cost: Decimal
    default_iva: Decimal
    updated_at: datetime | None = None


class PricingConfigUpdate(BaseModel):
    min_margin: Decimal | None = Field(default=None, ge=0, lt=1)
    rec_margin: Decimal | None = Field(default=None, ge=0, lt=1)
    high_margin: Decimal | None = Field(default=None, ge=0, lt=1)
    card_cost: Decimal | None = Field(default=None, ge=0, lt=1)
    default_iva: Decimal | None = Field(default=None, ge=0, lt=1)


class QuoteProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    category: str | None = Field(default=None, max_length=100)
    cost_price: Decimal = Field(gt=0)
    other_costs: Decimal = Field(default=Decimal("0"), ge=0)
    is_active: bool = True


class QuoteProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    category: str | None = Field(default=None, max_length=100)
    cost_price: Decimal | None = Field(default=None, gt=0)
    other_costs: Decimal | None = Field(default=None, ge=0)
    is_active: bool | None = None


class QuoteProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    category: str | None
    cost_price: Decimal
    other_costs: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime
    cost_real: Decimal
    price_min: Decimal
    price_rec: Decimal
    price_high: Decimal


class QuoteProductListResponse(BaseModel):
    items: list[QuoteProductRead]
    page: int
    page_size: int
    total: int
    total_pages: int


class QuoteItemCreate(BaseModel):
    product_id: UUID | None = None
    product_name: str | None = Field(default=None, max_length=200)
    tier: QuotePriceTier = QuotePriceTier.REC
    quantity: int = Field(default=1, ge=1)
    unit_price: Decimal | None = Field(default=None, gt=0)


class QuoteItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID | None
    product_name: str
    tier: str | None
    quantity: int
    unit_price: Decimal
    line_total: Decimal


class QuoteCreate(BaseModel):
    client_name: str = Field(min_length=1, max_length=200)
    client_id_number: str | None = Field(default=None, max_length=50)
    client_phone: str | None = Field(default=None, max_length=50)
    client_email: str | None = Field(default=None, max_length=120)
    client_address: str | None = Field(default=None, max_length=250)
    iva_pct: Decimal | None = Field(default=None, ge=0, lt=1)
    valid_until: date | None = None
    notes: str | None = Field(default=None, max_length=5000)
    status: QuoteStatus = QuoteStatus.DRAFT
    items: list[QuoteItemCreate] = Field(min_length=1)

    @field_validator("client_name")
    @classmethod
    def normalize_client_name(cls, value: str) -> str:
        cleaned = " ".join(value.strip().split())
        if not cleaned:
            raise ValueError("client_name cannot be empty")
        return cleaned


class QuoteUpdate(BaseModel):
    client_name: str | None = Field(default=None, min_length=1, max_length=200)
    client_id_number: str | None = Field(default=None, max_length=50)
    client_phone: str | None = Field(default=None, max_length=50)
    client_email: str | None = Field(default=None, max_length=120)
    client_address: str | None = Field(default=None, max_length=250)
    iva_pct: Decimal | None = Field(default=None, ge=0, lt=1)
    valid_until: date | None = None
    notes: str | None = Field(default=None, max_length=5000)
    status: QuoteStatus | None = None
    items: list[QuoteItemCreate] | None = None


class QuoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    number: str
    client_name: str
    client_id_number: str | None
    client_phone: str | None
    client_email: str | None
    client_address: str | None
    iva_pct: Decimal
    subtotal: Decimal
    iva_amount: Decimal
    total: Decimal
    status: str
    valid_until: date | None
    notes: str | None
    created_by: UUID | None
    created_at: datetime
    items: list[QuoteItemRead]
    created_by_email: str | None = None


class QuoteListResponse(BaseModel):
    items: list[QuoteRead]
    page: int
    page_size: int
    total: int
    total_pages: int
