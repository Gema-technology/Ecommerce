import re
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.commerce.buyer_id import normalize_buyer_identification


def normalize_email(email: str) -> str:
    return email.strip().lower()


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.strip().split())
    return cleaned or None


def _validate_phone(value: str | None, *, required: bool) -> str | None:
    cleaned = _clean_text(value)
    if cleaned is None:
        if required:
            raise ValueError("La factura necesita el teléfono del cliente")
        return None
    digits = re.sub(r"\D", "", cleaned)
    if len(digits) < 9 or len(digits) > 15:
        raise ValueError("Ingresa un número de teléfono válido")
    return cleaned


def _require_billing(data) -> None:
    if not data.tax_id_type or not data.tax_id:
        raise ValueError("La factura necesita cédula, RUC o pasaporte")
    if not data.address_line or not data.city or not data.province:
        raise ValueError("La factura necesita dirección, ciudad y provincia")


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
    phone: str | None = None
    tax_id_type: str | None = None
    tax_id: str | None = None
    address_line: str | None = None
    address_reference: str | None = None
    city: str | None = None
    province: str | None = None
    country: str = "Ecuador"
    postal_code: str | None = None
    is_active: bool
    allow_cash_on_delivery: bool = False
    roles: list[str] = Field(default_factory=list)


class CustomerCreate(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    phone: str = Field(min_length=7, max_length=30)
    tax_id_type: str = Field(min_length=1, max_length=20)
    tax_id: str = Field(min_length=1, max_length=20)
    address_line: str = Field(min_length=1, max_length=255)
    address_reference: str | None = Field(default=None, max_length=255)
    city: str = Field(min_length=1, max_length=100)
    province: str = Field(min_length=1, max_length=100)
    country: str = Field(default="Ecuador", min_length=1, max_length=100)
    postal_code: str | None = Field(default=None, max_length=20)

    @field_validator("email")
    @classmethod
    def normalize_customer_email(cls, value: str) -> str:
        return normalize_email(value)

    @field_validator("first_name", "last_name")
    @classmethod
    def strip_customer_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Name cannot be empty")
        return cleaned

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        cleaned = _validate_phone(value, required=True)
        assert cleaned is not None
        return cleaned

    @field_validator("address_line", "city", "province", "country")
    @classmethod
    def strip_required_place(cls, value: str) -> str:
        cleaned = _clean_text(value)
        if not cleaned:
            raise ValueError("Field cannot be empty")
        return cleaned

    @field_validator("address_reference", "postal_code")
    @classmethod
    def strip_optional_place(cls, value: str | None) -> str | None:
        return _clean_text(value)

    @field_validator("password", mode="before")
    @classmethod
    def blank_password_is_absent(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("password")
    @classmethod
    def validate_customer_password(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value.strip() != value:
            raise ValueError("Password cannot start or end with whitespace")
        return value

    @model_validator(mode="after")
    def check_billing(self):
        self.tax_id_type, self.tax_id = normalize_buyer_identification(
            self.tax_id_type, self.tax_id
        )
        _require_billing(self)
        return self


class CustomerUpdate(BaseModel):
    email: str | None = Field(default=None, min_length=3, max_length=320)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=30)
    tax_id_type: str | None = Field(default=None, max_length=20)
    tax_id: str | None = Field(default=None, max_length=20)
    address_line: str | None = Field(default=None, max_length=255)
    address_reference: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=100)
    province: str | None = Field(default=None, max_length=100)
    country: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=20)

    @field_validator("email")
    @classmethod
    def normalize_customer_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_email(value)

    @field_validator("first_name", "last_name")
    @classmethod
    def strip_customer_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Name cannot be empty")
        return cleaned

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        return _validate_phone(value, required=False)

    @field_validator(
        "address_line",
        "address_reference",
        "city",
        "province",
        "country",
        "postal_code",
    )
    @classmethod
    def strip_place(cls, value: str | None) -> str | None:
        return _clean_text(value)

    @field_validator("password")
    @classmethod
    def validate_customer_password(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value.strip() != value:
            raise ValueError("Password cannot start or end with whitespace")
        return value

    @model_validator(mode="after")
    def check_billing(self):
        billing = {"tax_id_type", "tax_id", "address_line", "city", "province"}
        if not billing.intersection(self.model_fields_set):
            return self
        self.tax_id_type, self.tax_id = normalize_buyer_identification(
            self.tax_id_type, self.tax_id
        )
        _require_billing(self)
        return self


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
