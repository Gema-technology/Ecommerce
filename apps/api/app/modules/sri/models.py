import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.core.database import Base

if TYPE_CHECKING:
    from app.modules.orders.models import Order

JsonDict = JSON().with_variant(JSONB(), "postgresql")


class TaxRegime(str, enum.Enum):
    RIMPE_NEGOCIO_POPULAR = "RIMPE_NEGOCIO_POPULAR"
    RIMPE_EMPRENDEDOR = "RIMPE_EMPRENDEDOR"
    GENERAL = "GENERAL"


class FiscalDocType(str, enum.Enum):
    NOTA_VENTA = "NOTA_VENTA"
    FACTURA = "FACTURA"


class FiscalDocStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    ISSUED = "ISSUED"
    SIGNED = "SIGNED"
    SENT = "SENT"
    AUTHORIZED = "AUTHORIZED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class BuyerIdType(str, enum.Enum):
    CEDULA = "CEDULA"
    RUC = "RUC"
    PASAPORTE = "PASAPORTE"
    CONSUMIDOR_FINAL = "CONSUMIDOR_FINAL"


class SriConfig(Base):
    """Singleton row (id=1) for SRI / fiscal emitter settings."""

    __tablename__ = "sri_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    tax_regime: Mapped[str] = mapped_column(
        String(40), nullable=False, default=TaxRegime.RIMPE_EMPRENDEDOR.value
    )
    ambiente: Mapped[str] = mapped_column(String(1), nullable=False, default="1")
    establecimiento: Mapped[str] = mapped_column(String(3), nullable=False, default="001")
    punto_emision: Mapped[str] = mapped_column(String(3), nullable=False, default="001")
    dir_matriz: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    dir_establecimiento: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    obligado_contabilidad: Mapped[str] = mapped_column(String(2), nullable=False, default="NO")
    contribuyente_especial: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    secuencial_nota_venta: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    secuencial_factura: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cert_filename: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    cert_stored: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=True
    )


class FiscalDocument(Base):
    __tablename__ = "fiscal_documents"
    __table_args__ = (
        UniqueConstraint("access_key", name="uq_fiscal_documents_access_key"),
        UniqueConstraint("doc_type", "document_number", name="uq_fiscal_documents_doc_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    doc_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    establishment: Mapped[str] = mapped_column(String(3), nullable=False)
    emission_point: Mapped[str] = mapped_column(String(3), nullable=False)
    sequential: Mapped[int] = mapped_column(Integer, nullable=False)
    document_number: Mapped[str] = mapped_column(String(20), nullable=False)
    access_key: Mapped[str | None] = mapped_column(String(49), nullable=True)
    buyer_id_type: Mapped[str] = mapped_column(String(20), nullable=False)
    buyer_id_number: Mapped[str] = mapped_column(String(20), nullable=False)
    buyer_name: Mapped[str] = mapped_column(String(300), nullable=False)
    buyer_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    buyer_address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    tax_total: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, default=Decimal("0"))
    discount_total: Mapped[Decimal] = mapped_column(
        Numeric(14, 4), nullable=False, default=Decimal("0")
    )
    shipping_total: Mapped[Decimal] = mapped_column(
        Numeric(14, 4), nullable=False, default=Decimal("0")
    )
    total: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False, default=Decimal("0"))
    xml_unsigned: Mapped[str | None] = mapped_column(Text, nullable=True)
    xml_signed: Mapped[str | None] = mapped_column(Text, nullable=True)
    authorization_number: Mapped[str | None] = mapped_column(String(49), nullable=True)
    authorized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sri_messages: Mapped[str | None] = mapped_column(Text, nullable=True)
    pdf_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    line_items: Mapped[list[dict[str, Any]] | None] = mapped_column(JsonDict, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    order: Mapped["Order"] = relationship("Order")
