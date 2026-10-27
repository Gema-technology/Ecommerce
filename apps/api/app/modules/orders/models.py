import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
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
    from app.modules.catalog.models import Product
    from app.modules.roles.models import User

JsonDict = JSON().with_variant(JSONB(), "postgresql")


class OrderStatus(str, enum.Enum):  # noqa: UP042
    PENDING_PAYMENT = "PENDING_PAYMENT"
    PAID = "PAID"
    PROCESSING = "PROCESSING"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    channel: Mapped[str] = mapped_column(
        String(20), nullable=False, default="WEB", server_default="WEB"
    )
    order_number: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=OrderStatus.PENDING_PAYMENT.value,
        index=True,
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    tax_total: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, default=Decimal("0"))
    shipping_total: Mapped[Decimal] = mapped_column(
        Numeric(14, 4), nullable=False, default=Decimal("0")
    )
    discount_total: Mapped[Decimal] = mapped_column(
        Numeric(14, 4), nullable=False, default=Decimal("0")
    )
    total: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    shipping_address: Mapped[dict[str, Any] | None] = mapped_column(JsonDict, nullable=True)
    customer_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    customer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    buyer_id_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    buyer_id_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cart_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("carts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped["User | None"] = relationship("User")
    items: Mapped[list["OrderItem"]] = relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="OrderItem.created_at",
    )
    status_events: Mapped[list["OrderStatusEvent"]] = relationship(
        "OrderStatusEvent",
        back_populates="order",
        cascade="all, delete-orphan",
        order_by="OrderStatusEvent.created_at",
    )


class OrderStatusEvent(Base):
    """Append-only audit of order status transitions (fulfillment + cancel)."""

    __tablename__ = "order_status_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_status: Mapped[str] = mapped_column(String(30), nullable=False)
    to_status: Mapped[str] = mapped_column(String(30), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    order: Mapped["Order"] = relationship("Order", back_populates="status_events")


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    product_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    sku_snapshot: Mapped[str] = mapped_column(String(64), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    line_discount: Mapped[Decimal] = mapped_column(
        Numeric(14, 4), nullable=False, default=Decimal("0")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    order: Mapped["Order"] = relationship("Order", back_populates="items")
    product: Mapped["Product"] = relationship("Product")


class OrderDailyCounter(Base):
    """Per-day sequence for public order numbers (GEMA-YYYYMMDD-NNNNNN)."""

    __tablename__ = "order_daily_counters"
    __table_args__ = (UniqueConstraint("day", name="uq_order_daily_counters_day"),)

    day: Mapped[str] = mapped_column(String(8), primary_key=True)
    last_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
