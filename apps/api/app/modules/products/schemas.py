from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from app.modules.pricing.schemas import PublicPrice
from app.shared.slug import normalize_sku, slugify


class AvailabilityStatus(str, Enum):
    IN_STOCK = "IN_STOCK"
    LOW_STOCK = "LOW_STOCK"
    OUT_OF_STOCK = "OUT_OF_STOCK"
    UNKNOWN = "UNKNOWN"


class ProductSort(str, Enum):
    RELEVANCE = "relevance"
    PRICE_ASC = "price_asc"
    PRICE_DESC = "price_desc"
    NAME_ASC = "name_asc"
    NAME_DESC = "name_desc"
    NEWEST = "newest"


class ProductImageInput(BaseModel):
    url: str = Field(min_length=1, max_length=500)
    alt_text: str | None = Field(default=None, max_length=255)
    sort_order: int = 0
    is_primary: bool = False

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        return str(HttpUrl(value))


class ProductImageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    url: str
    alt_text: str | None
    sort_order: int
    is_primary: bool


class BrandSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str


class CategorySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str


class ProductCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    slug: str | None = Field(default=None, max_length=280)
    short_description: str | None = Field(default=None, max_length=500)
    description: str | None = None
    model: str | None = Field(default=None, max_length=150)
    brand_id: UUID
    category_id: UUID
    specifications: dict[str, Any] = Field(default_factory=dict)
    weight: str | None = Field(default=None, max_length=50)
    warranty_months: int | None = Field(default=None, ge=0, le=1200)
    is_active: bool = True
    images: list[ProductImageInput] = Field(default_factory=list)

    @field_validator("sku")
    @classmethod
    def validate_sku(cls, value: str) -> str:
        sku = normalize_sku(value)
        if not sku:
            raise ValueError("SKU cannot be empty")
        return sku

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Name cannot be empty")
        return cleaned

    @field_validator("slug")
    @classmethod
    def normalize_slug(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        return slugify(value)

    @field_validator("specifications")
    @classmethod
    def validate_specs(cls, value: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ValueError("Specifications must be an object")
        return value


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    slug: str | None = Field(default=None, max_length=280)
    short_description: str | None = Field(default=None, max_length=500)
    description: str | None = None
    model: str | None = Field(default=None, max_length=150)
    brand_id: UUID | None = None
    category_id: UUID | None = None
    specifications: dict[str, Any] | None = None
    weight: str | None = Field(default=None, max_length=50)
    warranty_months: int | None = Field(default=None, ge=0, le=1200)
    is_active: bool | None = None
    images: list[ProductImageInput] | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Name cannot be empty")
        return cleaned

    @field_validator("slug")
    @classmethod
    def normalize_slug(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return slugify(value)


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    sku: str
    name: str
    slug: str
    short_description: str | None
    description: str | None
    model: str | None
    brand: BrandSummary
    category: CategorySummary
    specifications: dict[str, Any]
    weight: str | None
    warranty_months: int | None
    is_active: bool
    images: list[ProductImageRead] = Field(default_factory=list)
    price: PublicPrice | None = None
    availability: AvailabilityStatus = AvailabilityStatus.UNKNOWN


class ProductListResponse(BaseModel):
    items: list[ProductRead]
    page: int
    page_size: int
    total: int
    total_pages: int
