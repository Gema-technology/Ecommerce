import re
from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.commerce.buyer_id import BUYER_ID_TYPES, normalize_buyer_identification


class ShippingAddress(BaseModel):
    recipient_name: str = Field(min_length=1, max_length=150)
    phone: str = Field(min_length=7, max_length=30)
    address_line: str = Field(min_length=1, max_length=255)
    reference: str | None = Field(default=None, max_length=255)
    city: str = Field(min_length=1, max_length=100)
    province: str = Field(min_length=1, max_length=100)
    country: str = Field(default="Ecuador", min_length=1, max_length=100)
    postal_code: str | None = Field(default=None, max_length=20)

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        cleaned = " ".join(value.strip().split())
        if not cleaned:
            raise ValueError("Field cannot be empty")
        digits = re.sub(r"\D", "", cleaned)
        if len(digits) < 9 or len(digits) > 15:
            raise ValueError("Ingresa un número de teléfono válido")
        return cleaned

    @field_validator(
        "recipient_name",
        "address_line",
        "city",
        "province",
        "country",
    )
    @classmethod
    def normalize_required(cls, value: str) -> str:
        cleaned = " ".join(value.strip().split())
        if not cleaned:
            raise ValueError("Field cannot be empty")
        return cleaned

    @field_validator("reference", "postal_code")
    @classmethod
    def normalize_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.strip().split())
        return cleaned or None


BuyerIdTypeLiteral = Literal["CEDULA", "RUC", "PASAPORTE", "CONSUMIDOR_FINAL"]


class CheckoutRequest(BaseModel):
    shipping_address: ShippingAddress
    customer_notes: str | None = Field(default=None, max_length=1000)
    buyer_id_type: BuyerIdTypeLiteral | None = None
    buyer_id_number: str | None = Field(default=None, max_length=20)

    @field_validator("customer_notes")
    @classmethod
    def normalize_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("buyer_id_number")
    @classmethod
    def normalize_buyer_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class OrderItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID
    product_name_snapshot: str
    sku_snapshot: str
    unit_price: Decimal
    quantity: int
    line_total: Decimal
    line_discount: Decimal = Decimal("0")
    created_at: datetime


class OrderReservationRead(BaseModel):
    id: UUID
    inventory_id: UUID
    product_id: UUID | None = None
    quantity: int
    status: str
    expires_at: datetime | None = None
    created_at: datetime


class OrderStatusEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    from_status: str
    to_status: str
    actor_user_id: UUID | None = None
    note: str | None = None
    created_at: datetime


class OrderStatusUpdateRequest(BaseModel):
    status: Literal["PROCESSING", "SHIPPED", "DELIVERED"]
    note: str | None = Field(default=None, max_length=500)

    @field_validator("note")
    @classmethod
    def normalize_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class CounterSaleItem(BaseModel):
    product_id: UUID
    quantity: int = Field(ge=1, le=999)


class CounterSaleRequest(BaseModel):
    """In-store cash sale. A Clientes account is optional."""

    customer_id: UUID | None = None
    customer_name: str | None = Field(default=None, max_length=255)
    customer_phone: str | None = Field(default=None, max_length=30)
    customer_notes: str | None = Field(default=None, max_length=1000)
    buyer_id_type: Literal[*BUYER_ID_TYPES] | None = None
    buyer_id_number: str | None = Field(default=None, max_length=20)
    address_line: str | None = Field(default=None, max_length=255)
    address_reference: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=100)
    province: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=20)
    items: list[CounterSaleItem] = Field(min_length=1, max_length=50)

    @field_validator(
        "customer_name",
        "customer_phone",
        "customer_notes",
        "address_line",
        "address_reference",
        "city",
        "province",
        "country",
        "postal_code",
    )
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.strip().split())
        return cleaned or None

    @model_validator(mode="after")
    def check_buyer_id(self):
        self.buyer_id_type, self.buyer_id_number = normalize_buyer_identification(
            self.buyer_id_type, self.buyer_id_number
        )
        if self.buyer_id_type and not (self.address_line and self.city and self.province):
            raise ValueError("La factura necesita dirección, ciudad y provincia")
        if self.buyer_id_type and self.customer_id is None and not self.customer_phone:
            raise ValueError("La factura necesita el teléfono del cliente")
        return self


class CounterSalePreviewRequest(BaseModel):
    """Price a counter sale without creating the order or moving stock."""

    items: list[CounterSaleItem] = Field(min_length=1, max_length=50)


class CounterSalePreviewItemRead(BaseModel):
    product_id: UUID
    product_name: str
    sku: str
    quantity: int
    unit_price: Decimal
    line_discount: Decimal = Decimal("0")
    line_total: Decimal


class CounterSalePreviewResponse(BaseModel):
    currency: str
    subtotal: Decimal
    tax_total: Decimal
    shipping_total: Decimal
    discount_total: Decimal
    total: Decimal
    tax_enabled: bool
    items: list[CounterSalePreviewItemRead]


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_number: str
    status: str
    channel: str = "WEB"
    currency: str
    subtotal: Decimal
    tax_total: Decimal
    shipping_total: Decimal
    discount_total: Decimal
    total: Decimal
    customer_email: str | None = None
    customer_name: str | None = None
    customer_phone: str | None = None
    buyer_id_type: str | None = None
    buyer_id_number: str | None = None
    shipping_address: ShippingAddress | None = None
    customer_notes: str | None = None
    reserved_until: datetime | None = None
    created_at: datetime
    updated_at: datetime
    items: list[OrderItemRead] = Field(default_factory=list)
    reservations: list[OrderReservationRead] = Field(default_factory=list)
    allowed_transitions: list[str] = Field(default_factory=list)
    status_history: list[OrderStatusEventRead] = Field(default_factory=list)


class OrderListResponse(BaseModel):
    items: list[OrderRead]
    page: int
    page_size: int
    total: int
    total_pages: int


class CheckoutPreviewRequest(BaseModel):
    shipping_address: ShippingAddress | None = None


class CheckoutPreviewItemRead(BaseModel):
    product_id: UUID
    product_name: str
    sku: str
    quantity: int
    unit_price: Decimal
    unit_discount: Decimal = Decimal("0")
    line_discount: Decimal = Decimal("0")
    line_total: Decimal
    price_type: str | None = None


class CheckoutPreviewResponse(BaseModel):
    currency: str
    subtotal: Decimal
    tax_total: Decimal
    shipping_total: Decimal
    discount_total: Decimal
    total: Decimal
    shipping_method: str
    tax_enabled: bool
    items: list[CheckoutPreviewItemRead]


class CheckoutItemRead(BaseModel):
    product_id: UUID
    product_name: str
    quantity: int
    unit_price: Decimal
    unit_discount: Decimal = Decimal("0")
    line_discount: Decimal = Decimal("0")
    line_total: Decimal
    price_type: str | None = None


class CheckoutResponse(BaseModel):
    order_id: UUID
    order_number: str
    status: str
    currency: str
    subtotal: Decimal
    tax_total: Decimal
    shipping_total: Decimal
    discount_total: Decimal
    total: Decimal
    customer_email: str | None = None
    customer_name: str | None = None
    customer_phone: str | None = None
    buyer_id_type: str | None = None
    buyer_id_number: str | None = None
    shipping_address: ShippingAddress | None = None
    customer_notes: str | None = None
    items: list[CheckoutItemRead]
