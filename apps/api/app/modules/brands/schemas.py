from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from app.shared.slug import slugify


class BrandCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    slug: str | None = Field(default=None, max_length=180)
    description: str | None = None
    logo_url: str | None = Field(default=None, max_length=500)
    website_url: str | None = Field(default=None, max_length=500)
    is_active: bool = True
    category_ids: list[UUID] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        cleaned = " ".join(value.strip().split())
        if not cleaned:
            raise ValueError("Name cannot be empty")
        return cleaned

    @field_validator("slug")
    @classmethod
    def normalize_slug(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        return slugify(value)

    @field_validator("logo_url")
    @classmethod
    def validate_logo(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        return str(HttpUrl(value.strip()))

    @field_validator("website_url")
    @classmethod
    def validate_website(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        # Validate URL format via HttpUrl
        return str(HttpUrl(value.strip()))

    @field_validator("category_ids")
    @classmethod
    def dedupe_category_ids(cls, value: list[UUID]) -> list[UUID]:
        return list(dict.fromkeys(value))


class BrandUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    slug: str | None = Field(default=None, max_length=180)
    description: str | None = None
    logo_url: str | None = Field(default=None, max_length=500)
    website_url: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None
    category_ids: list[UUID] | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        cleaned = " ".join(value.strip().split())
        if not cleaned:
            raise ValueError("Name cannot be empty")
        return cleaned

    @field_validator("slug")
    @classmethod
    def normalize_slug(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return slugify(value)

    @field_validator("logo_url")
    @classmethod
    def validate_logo(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        return str(HttpUrl(value.strip()))

    @field_validator("website_url")
    @classmethod
    def validate_website(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        return str(HttpUrl(value.strip()))

    @field_validator("category_ids")
    @classmethod
    def dedupe_category_ids(cls, value: list[UUID] | None) -> list[UUID] | None:
        if value is None:
            return None
        return list(dict.fromkeys(value))


class BrandRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    description: str | None
    logo_url: str | None
    website_url: str | None
    is_active: bool
    category_ids: list[UUID] = Field(default_factory=list)

    @classmethod
    def from_brand(cls, brand: object) -> "BrandRead":
        return cls(
            id=brand.id,  # type: ignore[attr-defined]
            name=brand.name,  # type: ignore[attr-defined]
            slug=brand.slug,  # type: ignore[attr-defined]
            description=brand.description,  # type: ignore[attr-defined]
            logo_url=brand.logo_url,  # type: ignore[attr-defined]
            website_url=brand.website_url,  # type: ignore[attr-defined]
            is_active=brand.is_active,  # type: ignore[attr-defined]
            category_ids=[c.id for c in brand.categories],  # type: ignore[attr-defined]
        )


class BrandListResponse(BaseModel):
    items: list[BrandRead]
    page: int
    page_size: int
    total: int
    total_pages: int
