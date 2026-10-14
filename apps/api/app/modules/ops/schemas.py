"""Response schemas for the admin ops dashboard."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

OpsPeriod = Literal["today", "7d", "30d"]

AttentionSeverity = Literal["critical", "high", "medium"]

WorkItemKind = Literal[
    "confirm_payment",
    "fulfill_order",
    "aging_pending",
    "fix_fiscal",
    "expired_reservation",
    "restock",
    "failed_email",
]


class OpsKpis(BaseModel):
    period: OpsPeriod
    period_start: datetime
    orders_created: int
    orders_paid: int
    revenue_succeeded: Decimal
    avg_order_value: Decimal
    orders_by_status: dict[str, int]
    quotes_open: int
    # Deltas vs previous equal-length period (null if previous was zero / undefined)
    orders_created_delta_pct: float | None = None
    orders_paid_delta_pct: float | None = None
    revenue_succeeded_delta_pct: float | None = None
    avg_order_value_delta_pct: float | None = None


class MoneyAtRisk(BaseModel):
    currency: str = "USD"
    awaiting_payment_confirm: Decimal = Decimal("0")
    fulfillment_backlog: Decimal = Decimal("0")
    aging_pending_payment: Decimal = Decimal("0")
    total: Decimal = Decimal("0")


class AttentionItem(BaseModel):
    key: str
    label: str
    count: int
    severity: AttentionSeverity
    href: str
    oldest_age_hours: float | None = None


class WorkItem(BaseModel):
    id: str
    kind: WorkItemKind
    severity: AttentionSeverity
    score: float
    title: str
    reason: str
    action_label: str
    href: str
    entity_label: str | None = None
    amount: Decimal | None = None
    currency: str | None = None
    age_hours: float | None = None


class Briefing(BaseModel):
    headline: str
    detail: str
    tone: Literal["clear", "watch", "urgent"] = "clear"


class RecentOrderItem(BaseModel):
    id: UUID
    order_number: str
    status: str
    total: Decimal
    currency: str
    customer_email: str | None = None
    created_at: datetime


class OpsSummaryResponse(BaseModel):
    briefing: Briefing
    kpis: OpsKpis
    money_at_risk: MoneyAtRisk
    work_items: list[WorkItem] = Field(default_factory=list)
    attention: list[AttentionItem] = Field(default_factory=list)
    recent_orders: list[RecentOrderItem] = Field(default_factory=list)
