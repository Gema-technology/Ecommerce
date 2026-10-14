from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class StoreConfig(Base):
    """Singleton row (id=1) for admin-editable store settings."""

    __tablename__ = "store_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    business_name: Mapped[str] = mapped_column(String(200), nullable=False, default="GEMA Technology")
    business_ruc: Mapped[str] = mapped_column(String(30), nullable=False, default="")
    business_phone: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    business_address: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    business_email: Mapped[str] = mapped_column(String(320), nullable=False, default="")
    bank_name: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    bank_account_type: Mapped[str] = mapped_column(String(30), nullable=False, default="Ahorros")
    bank_account_number: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    bank_account_holder: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    bank_account_id: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    bank_transfer_instructions: Mapped[str] = mapped_column(Text, nullable=False, default="")
    shipping_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    shipping_flat_rate: Mapped[Decimal] = mapped_column(
        Numeric(14, 4), nullable=False, default=Decimal("5.0000")
    )
    shipping_free_threshold: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    shipping_province_rates: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=True
    )
