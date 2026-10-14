from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    HttpUrl,
    field_validator,
)

from app.modules.suppliers.models import CurrencyCode, SupplierAvailability, TaxIdType


def normalize_tax_id(value: str) -> str:
    return "".join(value.strip().upper().split())


def normalize_name(value: str) -> str:
    cleaned = " ".join(value.strip().split())
    if not cleaned:
        raise ValueError("Name cannot be empty")
    return cleaned


class SupplierCreate(BaseModel):
    business_name: str = Field(min_length=1, max_length=255)
    commercial_name: str | None = Field(default=None, max_length=255)
    tax_id: str = Field(min_length=1, max_length=50)
    tax_id_type: TaxIdType = TaxIdType.RUC
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)
    website_url: str | None = Field(default=None, max_length=500)
    address: str | None = Field(default=None, max_length=500)
    city: str | None = Field(default=None, max_length=100)
    province: str | None = Field(default=None, max_length=100)
    country: str = Field(default="Ecuador", min_length=1, max_length=100)
    contact_name: str | None = Field(default=None, max_length=150)
    notes: str | None = None
    is_active: bool = True

    @field_validator("business_name")
    @classmethod
    def normalize_business_name(cls, value: str) -> str:
        return normalize_name(value)

    @field_validator("commercial_name", "contact_name", "city", "province")
    @classmethod
    def normalize_optional_name(cls, value: str | None) -> str | None:
        if value is None or not str(value).strip():
            return None
        return " ".join(str(value).strip().split())

    @field_validator("country")
    @classmethod
    def normalize_country(cls, value: str) -> str:
        cleaned = " ".join(value.strip().split())
        return cleaned or "Ecuador"

    @field_validator("tax_id")
    @classmethod
    def normalize_tax(cls, value: str) -> str:
        cleaned = normalize_tax_id(value)
        if not cleaned:
            raise ValueError("tax_id cannot be empty")
        return cleaned

    @field_validator("email", mode="before")
    @classmethod
    def empty_email_to_none(cls, value: object) -> object:
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        return value

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr | None) -> str | None:
        if value is None:
            return None
        return str(value).strip().lower()

    @field_validator("website_url")
    @classmethod
    def validate_website(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        return str(HttpUrl(value))


class SupplierUpdate(BaseModel):
    business_name: str | None = Field(default=None, min_length=1, max_length=255)
    commercial_name: str | None = Field(default=None, max_length=255)
    tax_id: str | None = Field(default=None, min_length=1, max_length=50)
    tax_id_type: TaxIdType | None = None
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)
    website_url: str | None = Field(default=None, max_length=500)
    address: str | None = Field(default=None, max_length=500)
    city: str | None = Field(default=None, max_length=100)
    province: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, min_length=1, max_length=100)
    contact_name: str | None = Field(default=None, max_length=150)
    notes: str | None = None
    is_active: bool | None = None

    @field_validator("business_name")
    @classmethod
    def normalize_business_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_name(value)

    @field_validator("commercial_name", "contact_name", "city", "province")
    @classmethod
    def normalize_optional_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.strip():
            return None
        return " ".join(value.strip().split())

    @field_validator("country")
    @classmethod
    def normalize_country(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.strip().split())
        return cleaned or "Ecuador"

    @field_validator("tax_id")
    @classmethod
    def normalize_tax(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = normalize_tax_id(value)
        if not cleaned:
            raise ValueError("tax_id cannot be empty")
        return cleaned

    @field_validator("email", mode="before")
    @classmethod
    def empty_email_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr | None) -> str | None:
        if value is None:
            return None
        return str(value).strip().lower()

    @field_validator("website_url")
    @classmethod
    def validate_website(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.strip():
            return None
        return str(HttpUrl(value))


class SupplierRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_name: str
    commercial_name: str | None
    tax_id: str
    tax_id_type: TaxIdType
    email: str | None
    phone: str | None
    website_url: str | None
    address: str | None
    city: str | None
    province: str | None
    country: str
    contact_name: str | None
    notes: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class SupplierListResponse(BaseModel):
    items: list[SupplierRead]
    page: int
    page_size: int
    total: int
    total_pages: int


class SupplierProductCreate(BaseModel):
    product_id: UUID
    supplier_sku: str | None = Field(default=None, max_length=100)
    supplier_product_name: str | None = Field(default=None, max_length=255)
    cost: Decimal = Field(ge=0, max_digits=14, decimal_places=4)
    currency: CurrencyCode = CurrencyCode.USD
    availability: SupplierAvailability = SupplierAvailability.UNKNOWN
    lead_time_days: int | None = Field(default=None, ge=0)
    minimum_order_quantity: int = Field(default=1, gt=0)
    supplier_url: str | None = Field(default=None, max_length=500)
    is_active: bool = True

    @field_validator("supplier_sku")
    @classmethod
    def normalize_sku(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        return value.strip().upper()

    @field_validator("supplier_product_name")
    @classmethod
    def normalize_product_name(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        return " ".join(value.strip().split())

    @field_validator("supplier_url")
    @classmethod
    def validate_url(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        return str(HttpUrl(value))


class SupplierProductUpdate(BaseModel):
    supplier_sku: str | None = Field(default=None, max_length=100)
    supplier_product_name: str | None = Field(default=None, max_length=255)
    cost: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=4)
    currency: CurrencyCode | None = None
    availability: SupplierAvailability | None = None
    lead_time_days: int | None = Field(default=None, ge=0)
    minimum_order_quantity: int | None = Field(default=None, gt=0)
    supplier_url: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None
    mark_checked: bool = False

    @field_validator("supplier_sku")
    @classmethod
    def normalize_sku(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.strip():
            return None
        return value.strip().upper()

    @field_validator("supplier_product_name")
    @classmethod
    def normalize_product_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.strip():
            return None
        return " ".join(value.strip().split())

    @field_validator("supplier_url")
    @classmethod
    def validate_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.strip():
            return None
        return str(HttpUrl(value))


class SupplierProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    supplier_id: UUID
    product_id: UUID
    supplier_sku: str | None
    supplier_product_name: str | None
    cost: Decimal
    currency: CurrencyCode
    availability: SupplierAvailability
    lead_time_days: int | None
    minimum_order_quantity: int
    supplier_url: str | None
    last_checked_at: datetime | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    product_name: str | None = None
    product_sku: str | None = None


class ProductSupplierItem(BaseModel):
    supplier_product_id: UUID
    supplier_id: UUID
    supplier_name: str
    supplier_sku: str | None
    cost: Decimal
    currency: CurrencyCode
    availability: SupplierAvailability
    lead_time_days: int | None
    minimum_order_quantity: int
    supplier_url: str | None
    last_checked_at: datetime | None
    is_active: bool


class ProductSuppliersResponse(BaseModel):
    product: dict[str, str]
    suppliers: list[ProductSupplierItem]


class ProductSupplierLinkCreate(BaseModel):
    """Link an existing supplier to a product from the product admin view."""

    supplier_id: UUID
    supplier_sku: str | None = Field(default=None, max_length=100)
    supplier_product_name: str | None = Field(default=None, max_length=255)
    cost: Decimal = Field(ge=0, max_digits=14, decimal_places=4)
    currency: CurrencyCode = CurrencyCode.USD
    availability: SupplierAvailability = SupplierAvailability.UNKNOWN
    lead_time_days: int | None = Field(default=None, ge=0)
    minimum_order_quantity: int = Field(default=1, gt=0)
    supplier_url: str | None = Field(default=None, max_length=500)
    is_active: bool = True

    @field_validator("supplier_sku")
    @classmethod
    def normalize_sku(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        return value.strip().upper()

    @field_validator("supplier_product_name")
    @classmethod
    def normalize_product_name(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        return " ".join(value.strip().split())

    @field_validator("supplier_url")
    @classmethod
    def validate_url(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        return str(HttpUrl(value))
