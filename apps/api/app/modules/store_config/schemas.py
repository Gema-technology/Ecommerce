import json
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

AccountType = Literal["Ahorros", "Corriente"]


class StoreConfigRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    business_name: str
    business_ruc: str
    business_phone: str
    business_address: str
    business_email: str
    bank_name: str
    bank_account_type: str
    bank_account_number: str
    bank_account_holder: str
    bank_account_id: str
    bank_transfer_instructions: str
    shipping_enabled: bool
    shipping_flat_rate: Decimal
    shipping_free_threshold: Decimal | None = None
    shipping_province_rates: dict[str, Decimal] = Field(default_factory=dict)
    updated_at: datetime | None = None

    @classmethod
    def from_settings(cls) -> "StoreConfigRead":
        from app.core.config import settings

        return cls(
            business_name=settings.business_name or "GEMA Technology",
            business_ruc=settings.business_ruc or "",
            business_phone=settings.business_phone or "",
            business_address=settings.business_address or "",
            business_email=settings.business_email or "",
            bank_name=settings.bank_name or "",
            bank_account_type=settings.bank_account_type or "Ahorros",
            bank_account_number=settings.bank_account_number or "",
            bank_account_holder=settings.bank_account_holder or "",
            bank_account_id=settings.bank_account_id or "",
            bank_transfer_instructions=settings.bank_transfer_instructions or "",
            shipping_enabled=bool(settings.shipping_enabled),
            shipping_flat_rate=Decimal(str(settings.shipping_flat_rate)),
            shipping_free_threshold=(
                Decimal(str(settings.shipping_free_threshold))
                if settings.shipping_free_threshold is not None
                else None
            ),
            shipping_province_rates=_parse_province_rates(settings.shipping_province_rates),
            updated_at=None,
        )

    def business_dict(self) -> dict[str, str]:
        return {
            "name": self.business_name,
            "ruc": self.business_ruc,
            "phone": self.business_phone,
            "address": self.business_address,
            "email": self.business_email,
        }

    def bank_dict(self) -> dict[str, str]:
        return {
            "bank_name": self.bank_name.strip(),
            "account_type": (self.bank_account_type or "").strip() or "Ahorros",
            "account_number": self.bank_account_number.strip(),
            "account_holder": self.bank_account_holder.strip(),
            "account_id": self.bank_account_id.strip(),
            "extra_instructions": self.bank_transfer_instructions.strip(),
        }

    def bank_configured(self) -> bool:
        return bool(
            self.bank_name.strip()
            and self.bank_account_number.strip()
            and self.bank_account_holder.strip()
        )


class StoreConfigUpdate(BaseModel):
    business_name: str = Field(min_length=1, max_length=200)
    business_ruc: str = Field(default="", max_length=30)
    business_phone: str = Field(default="", max_length=40)
    business_address: str = Field(default="", max_length=300)
    business_email: str = Field(default="", max_length=320)
    bank_name: str = Field(default="", max_length=120)
    bank_account_type: AccountType = "Ahorros"
    bank_account_number: str = Field(default="", max_length=60)
    bank_account_holder: str = Field(default="", max_length=200)
    bank_account_id: str = Field(default="", max_length=40)
    bank_transfer_instructions: str = Field(default="", max_length=2000)
    shipping_enabled: bool = True
    shipping_flat_rate: Decimal = Field(ge=0)
    shipping_free_threshold: Decimal | None = Field(default=None, ge=0)
    shipping_province_rates: dict[str, Decimal] = Field(default_factory=dict)

    @field_validator(
        "business_name",
        "business_ruc",
        "business_phone",
        "business_address",
        "business_email",
        "bank_name",
        "bank_account_number",
        "bank_account_holder",
        "bank_account_id",
        "bank_transfer_instructions",
    )
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("shipping_province_rates")
    @classmethod
    def normalize_provinces(cls, value: dict[str, Decimal]) -> dict[str, Decimal]:
        cleaned: dict[str, Decimal] = {}
        for key, rate in value.items():
            name = str(key).strip()
            if not name:
                continue
            cleaned[name] = Decimal(str(rate))
            if cleaned[name] < 0:
                raise ValueError("Province shipping rates must be >= 0")
        return cleaned


def _parse_province_rates(raw: str | None) -> dict[str, Decimal]:
    text = (raw or "").strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    rates: dict[str, Decimal] = {}
    for key, value in parsed.items():
        try:
            rates[str(key).strip()] = Decimal(str(value))
        except Exception:
            continue
    return rates


def province_rates_to_json(rates: dict[str, Decimal]) -> str:
    if not rates:
        return ""
    return json.dumps({k: str(v) for k, v in rates.items()}, ensure_ascii=False)
