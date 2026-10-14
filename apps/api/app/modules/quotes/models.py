import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.core.database import Base

if TYPE_CHECKING:
    from app.modules.roles.models import User


class QuoteStatus(str, enum.Enum):
    DRAFT = "draft"
    SENT = "sent"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"


class QuotePriceTier(str, enum.Enum):
    MIN = "min"
    REC = "rec"
    HIGH = "high"
    MANUAL = "manual"


class PricingConfig(Base):
    """Singleton row for global quote pricing parameters."""

    __tablename__ = "quote_pricing_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    min_margin: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False, default=Decimal("0.12"))
    rec_margin: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False, default=Decimal("0.20"))
    high_margin: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False, default=Decimal("0.25"))
    card_cost: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False, default=Decimal("0.03"))
    default_iva: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False, default=Decimal("0.15"))
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )


class QuoteProduct(Base):
    """Catalog items used for quotations (separate from storefront products)."""

    __tablename__ = "quote_products"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cost_price: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    other_costs: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, default=Decimal("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class QuoteNumberCounter(Base):
    """Atomic sequence for quote numbers (PRO-0001)."""

    __tablename__ = "quote_number_counters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    last_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Quote(Base):
    __tablename__ = "quotes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    client_name: Mapped[str] = mapped_column(String(200), nullable=False)
    client_id_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    client_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    client_email: Mapped[str | None] = mapped_column(String(120), nullable=True)
    client_address: Mapped[str | None] = mapped_column(String(250), nullable=True)
    iva_pct: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False, default=Decimal("0.15"))
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, default=Decimal("0"))
    iva_amount: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, default=Decimal("0"))
    total: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, default=Decimal("0"))
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=QuoteStatus.DRAFT.value, index=True
    )
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    created_by_user: Mapped["User | None"] = relationship("User")
    items: Mapped[list["QuoteItem"]] = relationship(
        "QuoteItem",
        back_populates="quote",
        cascade="all, delete-orphan",
        order_by="QuoteItem.id",
    )


class QuoteItem(Base):
    __tablename__ = "quote_items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    quote_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("quotes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("quote_products.id", ondelete="SET NULL"), nullable=True, index=True
    )
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    tier: Mapped[str | None] = mapped_column(String(10), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)

    quote: Mapped["Quote"] = relationship("Quote", back_populates="items")
    product: Mapped["QuoteProduct | None"] = relationship("QuoteProduct")
