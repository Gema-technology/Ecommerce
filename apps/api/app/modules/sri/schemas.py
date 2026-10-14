from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

TaxRegimeLiteral = Literal["RIMPE_NEGOCIO_POPULAR", "RIMPE_EMPRENDEDOR", "GENERAL"]
AmbienteLiteral = Literal["1", "2"]
ObligadoLiteral = Literal["SI", "NO"]
DocTypeLiteral = Literal["NOTA_VENTA", "FACTURA"]
BuyerIdLiteral = Literal["CEDULA", "RUC", "PASAPORTE", "CONSUMIDOR_FINAL"]


class SriConfigRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tax_regime: TaxRegimeLiteral
    ambiente: AmbienteLiteral
    establecimiento: str
    punto_emision: str
    dir_matriz: str
    dir_establecimiento: str
    obligado_contabilidad: ObligadoLiteral
    contribuyente_especial: str
    secuencial_nota_venta: int
    secuencial_factura: int
    cert_filename: str
    cert_stored: bool
    cert_password_configured: bool = False
    updated_at: datetime | None = None


class SriConfigUpdate(BaseModel):
    tax_regime: TaxRegimeLiteral = "RIMPE_EMPRENDEDOR"
    ambiente: AmbienteLiteral = "1"
    establecimiento: str = Field(default="001", min_length=3, max_length=3)
    punto_emision: str = Field(default="001", min_length=3, max_length=3)
    dir_matriz: str = Field(default="", max_length=300)
    dir_establecimiento: str = Field(default="", max_length=300)
    obligado_contabilidad: ObligadoLiteral = "NO"
    contribuyente_especial: str = Field(default="", max_length=20)

    @field_validator("establecimiento", "punto_emision")
    @classmethod
    def digits_only(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned.isdigit() or len(cleaned) != 3:
            raise ValueError("Must be exactly 3 digits")
        return cleaned

    @field_validator(
        "dir_matriz",
        "dir_establecimiento",
        "contribuyente_especial",
    )
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class CertVerifyResponse(BaseModel):
    ok: bool
    subject: str | None = None
    issuer: str | None = None
    not_valid_after: str | None = None
    serial: str | None = None
    message: str | None = None


class EmitFiscalDocumentRequest(BaseModel):
    doc_type: DocTypeLiteral
    buyer_id_type: BuyerIdLiteral | None = None
    buyer_id_number: str | None = Field(default=None, max_length=20)
    buyer_name: str | None = Field(default=None, max_length=300)
    buyer_email: str | None = Field(default=None, max_length=320)
    buyer_address: str | None = Field(default=None, max_length=300)
    send_to_sri: bool = True

    @field_validator("buyer_id_number", "buyer_name", "buyer_email", "buyer_address")
    @classmethod
    def strip_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class FiscalDocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_id: UUID
    doc_type: str
    status: str
    establishment: str
    emission_point: str
    sequential: int
    document_number: str
    access_key: str | None = None
    buyer_id_type: str
    buyer_id_number: str
    buyer_name: str
    buyer_email: str | None = None
    buyer_address: str | None = None
    currency: str
    subtotal: Decimal
    tax_total: Decimal
    discount_total: Decimal
    shipping_total: Decimal
    total: Decimal
    tax_rate: Decimal
    authorization_number: str | None = None
    authorized_at: datetime | None = None
    sri_messages: str | None = None
    has_pdf: bool = False
    has_xml: bool = False
    line_items: list[dict[str, Any]] | None = None
    created_at: datetime
    updated_at: datetime


class FiscalDocumentListResponse(BaseModel):
    items: list[FiscalDocumentRead]
    page: int
    page_size: int
    total: int
    total_pages: int
