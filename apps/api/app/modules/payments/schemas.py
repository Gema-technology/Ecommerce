from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.payments.models import PaymentMethod


class PaymentCreateRequest(BaseModel):
    method: PaymentMethod = PaymentMethod.CARD


class PaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    payment_id: UUID | None = None
    order_id: UUID
    order_number: str | None = None
    provider: str
    provider_payment_id: str | None = None
    method: str
    status: str
    amount: Decimal
    currency: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
    paid_at: datetime | None = None
    client_action: dict[str, Any] | None = None


class PaymentListResponse(BaseModel):
    items: list[PaymentRead]
    page: int = 1
    page_size: int = 20
    total: int = 0
    total_pages: int = 0


class ManualWebhookPayload(BaseModel):
    event_id: str = Field(min_length=1, max_length=120)
    event_type: str  # payment.succeeded | payment.failed
    payment_id: UUID
