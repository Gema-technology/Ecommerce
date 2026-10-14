from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


def normalize_email(email: str) -> str:
    return email.strip().lower()


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    # str (not EmailStr): response DTOs must not reject stored addresses
    # that email-validator treats as special-use (e.g. @gema.local).
    email: str
    first_name: str
    last_name: str
    phone: str | None = None
    is_active: bool
    email_verified: bool
    allow_cash_on_delivery: bool = False
    roles: list[str] = Field(default_factory=list)


class UserProfileUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=30)

    @field_validator("first_name", "last_name")
    @classmethod
    def strip_names(cls, value: str | None) -> str | None:
        if value is None:
            return value
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Name cannot be empty")
        return cleaned


class CustomerListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    first_name: str
    last_name: str
    is_active: bool
    allow_cash_on_delivery: bool = False
    roles: list[str] = Field(default_factory=list)


class CustomerListResponse(BaseModel):
    items: list[CustomerListItem]
    page: int
    page_size: int
    total: int
    total_pages: int


# Backward-compatible alias (tests / older imports).
AdminUserListItem = CustomerListItem


class AdminUserCodUpdate(BaseModel):
    allow_cash_on_delivery: bool


class CustomerActiveUpdate(BaseModel):
    is_active: bool
