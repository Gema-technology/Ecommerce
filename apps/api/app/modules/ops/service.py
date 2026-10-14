"""Aggregate + ranked work queue for the admin ops dashboard."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.modules.inventory.models import InventoryReservation, ReservationStatus
from app.modules.inventory.repository import InventoryRepository
from app.modules.notifications.models import NotificationDispatch
from app.modules.ops.schemas import (
    AttentionItem,
    AttentionSeverity,
    Briefing,
    MoneyAtRisk,
    OpsKpis,
    OpsPeriod,
    OpsSummaryResponse,
    RecentOrderItem,
    WorkItem,
)
from app.modules.orders.models import Order, OrderStatus
from app.modules.payments.models import Payment, PaymentStatus
from app.modules.quotes.models import Quote, QuoteStatus
from app.modules.sri.models import FiscalDocStatus, FiscalDocument

_PAID_FUNNEL = (
    OrderStatus.PAID.value,
    OrderStatus.PROCESSING.value,
    OrderStatus.SHIPPED.value,
    OrderStatus.DELIVERED.value,
)

_OFFLINE_PROVIDERS = ("bank_transfer", "manual")
_PENDING_PAY_STATUSES = (PaymentStatus.PENDING.value, PaymentStatus.PROCESSING.value)

_SEVERITY_BASE: dict[AttentionSeverity, float] = {
    "critical": 100.0,
    "high": 60.0,
    "medium": 30.0,
}

_WORK_LIMIT = 12


def _period_start(period: OpsPeriod, *, now: datetime) -> datetime:
    if period == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "30d":
        return now - timedelta(days=30)
    return now - timedelta(days=7)


def _previous_window(
    period: OpsPeriod, *, start: datetime, now: datetime
) -> tuple[datetime, datetime]:
    """Return [prev_start, prev_end) equal in length to the current window."""
    if period == "today":
        prev_end = start
        prev_start = start - timedelta(days=1)
        return prev_start, prev_end
    length = now - start
    prev_end = start
    prev_start = start - length
    return prev_start, prev_end


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _age_hours(oldest: datetime | None, *, now: datetime) -> float | None:
    oldest = _aware(oldest)
    if oldest is None:
        return None
    return round(max((now - oldest).total_seconds() / 3600.0, 0.0), 1)


def _delta_pct(current: float | Decimal, previous: float | Decimal) -> float | None:
    cur = float(current)
    prev = float(previous)
    if prev == 0:
        return None if cur == 0 else 100.0
    return round(((cur - prev) / prev) * 100.0, 1)


def _money(value: Decimal | float | int | None) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.0001"))


def _score(
    *,
    severity: AttentionSeverity,
    age_hours: float | None,
    amount: Decimal | None = None,
) -> float:
    score = _SEVERITY_BASE[severity]
    if age_hours is not None:
        score += min(age_hours, 72.0) * 0.5
    if amount is not None and amount > 0:
        score += min(float(amount), 500.0) / 10.0
    return round(score, 2)


def _format_money_es(amount: Decimal) -> str:
    quantized = amount.quantize(Decimal("0.01"))
    return f"${quantized:,.2f}"


class OpsService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def summary(self, period: OpsPeriod = "7d") -> OpsSummaryResponse:
        now = datetime.now(UTC)
        start = _period_start(period, now=now)
        prev_start, prev_end = _previous_window(period, start=start, now=now)

        kpis = self._kpis(period=period, start=start, prev_start=prev_start, prev_end=prev_end)
        money = self._money_at_risk(now=now)
        work_items = self._work_items(now=now)
        attention = self._attention(now=now, work_items=work_items)
        briefing = self._briefing(kpis=kpis, money=money, work_items=work_items)
        recent = self._recent_orders()
        return OpsSummaryResponse(
            briefing=briefing,
            kpis=kpis,
            money_at_risk=money,
            work_items=work_items,
            attention=attention,
            recent_orders=recent,
        )

    def _window_metrics(self, *, start: datetime, end: datetime | None) -> tuple[int, int, Decimal]:
        order_filters = [Order.created_at >= start]
        if end is not None:
            order_filters.append(Order.created_at < end)

        orders_created = self.db.scalar(
            select(func.count()).select_from(Order).where(*order_filters)
        ) or 0

        orders_paid = self.db.scalar(
            select(func.count())
            .select_from(Order)
            .where(*order_filters, Order.status.in_(_PAID_FUNNEL))
        ) or 0

        pay_time = func.coalesce(Payment.paid_at, Payment.created_at)
        pay_filters = [
            Payment.status == PaymentStatus.SUCCEEDED.value,
            pay_time >= start,
        ]
        if end is not None:
            pay_filters.append(pay_time < end)
        revenue = self.db.scalar(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(*pay_filters)
        )
        return int(orders_created), int(orders_paid), _money(revenue)

    def _kpis(
        self,
        *,
        period: OpsPeriod,
        start: datetime,
        prev_start: datetime,
        prev_end: datetime,
    ) -> OpsKpis:
        orders_created, orders_paid, revenue_succeeded = self._window_metrics(
            start=start, end=None
        )
        prev_created, prev_paid, prev_revenue = self._window_metrics(
            start=prev_start, end=prev_end
        )

        if orders_paid > 0:
            avg_order_value = (revenue_succeeded / Decimal(orders_paid)).quantize(
                Decimal("0.0001")
            )
        else:
            avg_order_value = Decimal("0")

        if prev_paid > 0:
            prev_avg = (prev_revenue / Decimal(prev_paid)).quantize(Decimal("0.0001"))
        else:
            prev_avg = Decimal("0")

        status_rows = self.db.execute(
            select(Order.status, func.count()).group_by(Order.status)
        ).all()
        orders_by_status = {status: int(count) for status, count in status_rows}
        for status in OrderStatus:
            orders_by_status.setdefault(status.value, 0)

        quotes_open = self.db.scalar(
            select(func.count())
            .select_from(Quote)
            .where(Quote.status.in_((QuoteStatus.DRAFT.value, QuoteStatus.SENT.value)))
        ) or 0

        return OpsKpis(
            period=period,
            period_start=start,
            orders_created=orders_created,
            orders_paid=orders_paid,
            revenue_succeeded=revenue_succeeded,
            avg_order_value=avg_order_value,
            orders_by_status=orders_by_status,
            quotes_open=int(quotes_open),
            orders_created_delta_pct=_delta_pct(orders_created, prev_created),
            orders_paid_delta_pct=_delta_pct(orders_paid, prev_paid),
            revenue_succeeded_delta_pct=_delta_pct(revenue_succeeded, prev_revenue),
            avg_order_value_delta_pct=_delta_pct(avg_order_value, prev_avg),
        )

    def _money_at_risk(self, *, now: datetime) -> MoneyAtRisk:
        awaiting = self.db.scalar(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.provider.in_(_OFFLINE_PROVIDERS),
                Payment.status.in_(_PENDING_PAY_STATUSES),
            )
        )
        fulfillment = self.db.scalar(
            select(func.coalesce(func.sum(Order.total), 0)).where(
                Order.status.in_((OrderStatus.PAID.value, OrderStatus.PROCESSING.value))
            )
        )
        aging_cutoff = now - timedelta(hours=24)
        aging = self.db.scalar(
            select(func.coalesce(func.sum(Order.total), 0)).where(
                Order.status == OrderStatus.PENDING_PAYMENT.value,
                Order.created_at < aging_cutoff,
            )
        )
        awaiting_d = _money(awaiting)
        fulfillment_d = _money(fulfillment)
        aging_d = _money(aging)
        return MoneyAtRisk(
            awaiting_payment_confirm=awaiting_d,
            fulfillment_backlog=fulfillment_d,
            aging_pending_payment=aging_d,
            total=_money(awaiting_d + fulfillment_d + aging_d),
        )

    def _work_items(self, *, now: datetime) -> list[WorkItem]:
        items: list[WorkItem] = []

        payments = self.db.execute(
            select(Payment, Order)
            .join(Order, Order.id == Payment.order_id)
            .where(
                Payment.provider.in_(_OFFLINE_PROVIDERS),
                Payment.status.in_(_PENDING_PAY_STATUSES),
            )
            .order_by(Payment.created_at.asc())
            .limit(40)
        ).all()
        for payment, order in payments:
            age = _age_hours(payment.created_at, now=now) or 0.0
            severity: AttentionSeverity = "critical" if age >= 48 else "high"
            provider = "transferencia" if payment.provider == "bank_transfer" else "manual"
            items.append(
                WorkItem(
                    id=f"pay:{payment.id}",
                    kind="confirm_payment",
                    severity=severity,
                    score=_score(severity=severity, age_hours=age, amount=payment.amount),
                    title=f"Confirmar pago {provider}",
                    reason=(
                        f"{order.order_number} lleva {age:.0f} h esperando confirmación"
                        if age >= 1
                        else f"{order.order_number} espera confirmación de pago"
                    ),
                    action_label="Revisar pago",
                    href=f"/admin/payments/{payment.id}",
                    entity_label=order.order_number,
                    amount=payment.amount,
                    currency=payment.currency,
                    age_hours=age,
                )
            )

        fulfill_orders = self.db.scalars(
            select(Order)
            .where(
                Order.status.in_((OrderStatus.PAID.value, OrderStatus.PROCESSING.value))
            )
            .order_by(Order.created_at.asc())
            .limit(40)
        ).all()
        for order in fulfill_orders:
            age = _age_hours(order.created_at, now=now) or 0.0
            severity: AttentionSeverity = "critical" if age >= 48 else "high"
            next_step = (
                "Marcar en preparación"
                if order.status == OrderStatus.PAID.value
                else "Marcar como enviada"
            )
            items.append(
                WorkItem(
                    id=f"fulfill:{order.id}",
                    kind="fulfill_order",
                    severity=severity,
                    score=_score(severity=severity, age_hours=age, amount=order.total),
                    title=next_step,
                    reason=(
                        f"{order.order_number} en {order.status} desde hace {age:.0f} h"
                    ),
                    action_label="Abrir pedido",
                    href=f"/admin/orders/{order.id}",
                    entity_label=order.order_number,
                    amount=order.total,
                    currency=order.currency,
                    age_hours=age,
                )
            )

        aging_cutoff = now - timedelta(hours=24)
        aging_orders = self.db.scalars(
            select(Order)
            .where(
                Order.status == OrderStatus.PENDING_PAYMENT.value,
                Order.created_at < aging_cutoff,
            )
            .order_by(Order.created_at.asc())
            .limit(20)
        ).all()
        for order in aging_orders:
            age = _age_hours(order.created_at, now=now) or 0.0
            severity: AttentionSeverity = "high" if age >= 72 else "medium"
            items.append(
                WorkItem(
                    id=f"aging:{order.id}",
                    kind="aging_pending",
                    severity=severity,
                    score=_score(severity=severity, age_hours=age, amount=order.total),
                    title="Seguir pago pendiente",
                    reason=f"{order.order_number} sin pagar hace {age:.0f} h",
                    action_label="Ver pedido",
                    href=f"/admin/orders/{order.id}",
                    entity_label=order.order_number,
                    amount=order.total,
                    currency=order.currency,
                    age_hours=age,
                )
            )

        fiscal_docs = self.db.scalars(
            select(FiscalDocument)
            .where(
                or_(
                    FiscalDocument.status == FiscalDocStatus.REJECTED.value,
                    and_(
                        FiscalDocument.status == FiscalDocStatus.SENT.value,
                        FiscalDocument.authorization_number.is_(None),
                    ),
                )
            )
            .order_by(FiscalDocument.created_at.asc())
            .limit(20)
        ).all()
        for doc in fiscal_docs:
            age = _age_hours(doc.created_at, now=now) or 0.0
            rejected = doc.status == FiscalDocStatus.REJECTED.value
            severity: AttentionSeverity = "critical" if rejected else "high"
            items.append(
                WorkItem(
                    id=f"fiscal:{doc.id}",
                    kind="fix_fiscal",
                    severity=severity,
                    score=_score(severity=severity, age_hours=age, amount=doc.total),
                    title=(
                        "Corregir comprobante rechazado"
                        if rejected
                        else "Comprobante sin autorización SRI"
                    ),
                    reason=f"{doc.document_number} · {doc.doc_type}",
                    action_label="Ver pedido",
                    href=f"/admin/orders/{doc.order_id}",
                    entity_label=doc.document_number,
                    amount=doc.total,
                    currency=doc.currency,
                    age_hours=age,
                )
            )

        expired = self.db.execute(
            select(InventoryReservation, Order)
            .join(Order, Order.id == InventoryReservation.order_id)
            .where(
                InventoryReservation.status == ReservationStatus.ACTIVE.value,
                InventoryReservation.expires_at.is_not(None),
                InventoryReservation.expires_at < now,
            )
            .order_by(InventoryReservation.expires_at.asc())
            .limit(20)
        ).all()
        for reservation, order in expired:
            age = _age_hours(reservation.expires_at, now=now) or 0.0
            items.append(
                WorkItem(
                    id=f"res:{reservation.id}",
                    kind="expired_reservation",
                    severity="critical",
                    score=_score(severity="critical", age_hours=age, amount=order.total),
                    title="Reserva vencida aún activa",
                    reason=f"{order.order_number} — liberar o expirar stock retenido",
                    action_label="Ver pedido",
                    href=f"/admin/orders/{order.id}",
                    entity_label=order.order_number,
                    amount=order.total,
                    currency=order.currency,
                    age_hours=age,
                )
            )

        for inv in InventoryRepository(self.db).list_low_stock()[:15]:
            deficit = max(inv.reorder_point - inv.available_quantity, 0)
            severity: AttentionSeverity = (
                "critical" if inv.available_quantity <= 0 else "medium"
            )
            items.append(
                WorkItem(
                    id=f"stock:{inv.id}",
                    kind="restock",
                    severity=severity,
                    score=_score(
                        severity=severity,
                        age_hours=None,
                        amount=Decimal(deficit * 10),
                    ),
                    title=(
                        "Producto agotado"
                        if inv.available_quantity <= 0
                        else "Reponer bajo stock"
                    ),
                    reason=(
                        f"{inv.product.sku if inv.product else 'SKU'} · "
                        f"disp. {inv.available_quantity} / reorden {inv.reorder_point}"
                    ),
                    action_label="Abrir inventario",
                    href=f"/admin/inventory/{inv.product_id}?location_id={inv.location_id}",
                    entity_label=inv.product.sku if inv.product else None,
                    age_hours=None,
                )
            )

        email_since = now - timedelta(days=7)
        failed = self.db.scalars(
            select(NotificationDispatch)
            .where(
                NotificationDispatch.status == "failed",
                NotificationDispatch.created_at >= email_since,
            )
            .order_by(NotificationDispatch.created_at.asc())
            .limit(10)
        ).all()
        for dispatch in failed:
            age = _age_hours(dispatch.created_at, now=now) or 0.0
            items.append(
                WorkItem(
                    id=f"mail:{dispatch.id}",
                    kind="failed_email",
                    severity="medium",
                    score=_score(severity="medium", age_hours=age),
                    title="Correo transaccional fallido",
                    reason=dispatch.detail or dispatch.event_key,
                    action_label="Ver pedido",
                    href=f"/admin/orders/{dispatch.order_id}",
                    entity_label=dispatch.event_key,
                    age_hours=age,
                )
            )

        items.sort(key=lambda item: (-item.score, item.severity))
        return items[:_WORK_LIMIT]

    def _attention(
        self, *, now: datetime, work_items: list[WorkItem]
    ) -> list[AttentionItem]:
        """Category rollups derived from live queries (not just the truncated work queue)."""
        items: list[AttentionItem] = []

        offline = self._count_and_oldest(
            select(Payment.created_at)
            .where(
                Payment.provider.in_(_OFFLINE_PROVIDERS),
                Payment.status.in_(_PENDING_PAY_STATUSES),
            )
            .order_by(Payment.created_at.asc())
        )
        if offline[0]:
            items.append(
                AttentionItem(
                    key="offline_payments",
                    label="Pagos offline por confirmar",
                    count=offline[0],
                    severity="high",
                    href="/admin/payments",
                    oldest_age_hours=_age_hours(offline[1], now=now),
                )
            )

        fulfillment = self._count_and_oldest(
            select(Order.created_at)
            .where(
                Order.status.in_(
                    (OrderStatus.PAID.value, OrderStatus.PROCESSING.value)
                )
            )
            .order_by(Order.created_at.asc())
        )
        if fulfillment[0]:
            items.append(
                AttentionItem(
                    key="fulfillment_backlog",
                    label="Pedidos por preparar o enviar",
                    count=fulfillment[0],
                    severity="high",
                    href="/admin/orders",
                    oldest_age_hours=_age_hours(fulfillment[1], now=now),
                )
            )

        aging_cutoff = now - timedelta(hours=24)
        aging = self._count_and_oldest(
            select(Order.created_at)
            .where(
                Order.status == OrderStatus.PENDING_PAYMENT.value,
                Order.created_at < aging_cutoff,
            )
            .order_by(Order.created_at.asc())
        )
        if aging[0]:
            items.append(
                AttentionItem(
                    key="aging_pending_payment",
                    label="Pagos pendientes con más de 24 h",
                    count=aging[0],
                    severity="medium",
                    href="/admin/orders",
                    oldest_age_hours=_age_hours(aging[1], now=now),
                )
            )

        fiscal_rejected = self._count_and_oldest(
            select(FiscalDocument.created_at)
            .where(FiscalDocument.status == FiscalDocStatus.REJECTED.value)
            .order_by(FiscalDocument.created_at.asc())
        )
        if fiscal_rejected[0]:
            items.append(
                AttentionItem(
                    key="fiscal_rejected",
                    label="Comprobantes SRI rechazados",
                    count=fiscal_rejected[0],
                    severity="critical",
                    href="/admin/comprobantes",
                    oldest_age_hours=_age_hours(fiscal_rejected[1], now=now),
                )
            )

        fiscal_stuck = self._count_and_oldest(
            select(FiscalDocument.created_at)
            .where(
                FiscalDocument.status == FiscalDocStatus.SENT.value,
                FiscalDocument.authorization_number.is_(None),
            )
            .order_by(FiscalDocument.created_at.asc())
        )
        if fiscal_stuck[0]:
            items.append(
                AttentionItem(
                    key="fiscal_stuck_sent",
                    label="Comprobantes enviados sin autorización",
                    count=fiscal_stuck[0],
                    severity="high",
                    href="/admin/comprobantes",
                    oldest_age_hours=_age_hours(fiscal_stuck[1], now=now),
                )
            )

        low_stock_count = len(InventoryRepository(self.db).list_low_stock())
        if low_stock_count:
            items.append(
                AttentionItem(
                    key="low_stock",
                    label="Productos con bajo stock",
                    count=low_stock_count,
                    severity="medium",
                    href="/admin/inventory",
                )
            )

        expired_res = self._count_and_oldest(
            select(InventoryReservation.created_at)
            .where(
                InventoryReservation.status == ReservationStatus.ACTIVE.value,
                InventoryReservation.expires_at.is_not(None),
                InventoryReservation.expires_at < now,
            )
            .order_by(InventoryReservation.created_at.asc())
        )
        if expired_res[0]:
            items.append(
                AttentionItem(
                    key="expired_reservations",
                    label="Reservas activas vencidas",
                    count=expired_res[0],
                    severity="critical",
                    href="/admin/orders",
                    oldest_age_hours=_age_hours(expired_res[1], now=now),
                )
            )

        email_since = now - timedelta(days=7)
        failed_emails = self.db.scalar(
            select(func.count())
            .select_from(NotificationDispatch)
            .where(
                NotificationDispatch.status == "failed",
                NotificationDispatch.created_at >= email_since,
            )
        ) or 0
        if failed_emails:
            oldest_email = self.db.scalar(
                select(func.min(NotificationDispatch.created_at)).where(
                    NotificationDispatch.status == "failed",
                    NotificationDispatch.created_at >= email_since,
                )
            )
            items.append(
                AttentionItem(
                    key="failed_emails",
                    label="Correos fallidos (7 días)",
                    count=int(failed_emails),
                    severity="medium",
                    href="/admin/orders",
                    oldest_age_hours=_age_hours(oldest_email, now=now),
                )
            )

        # Prefer categories that have concrete work_items still visible.
        visible_kinds = {item.kind for item in work_items}
        kind_to_key = {
            "confirm_payment": "offline_payments",
            "fulfill_order": "fulfillment_backlog",
            "aging_pending": "aging_pending_payment",
            "fix_fiscal": "fiscal_rejected",
            "expired_reservation": "expired_reservations",
            "restock": "low_stock",
            "failed_email": "failed_emails",
        }
        # Keep all categories; sort by severity then whether they appear in top work.
        severity_rank = {"critical": 0, "high": 1, "medium": 2}
        items.sort(
            key=lambda item: (
                severity_rank[item.severity],
                0
                if any(kind_to_key.get(k) == item.key for k in visible_kinds)
                else 1,
                -item.count,
            )
        )
        return items

    def _briefing(
        self,
        *,
        kpis: OpsKpis,
        money: MoneyAtRisk,
        work_items: list[WorkItem],
    ) -> Briefing:
        if not work_items:
            rev_delta = kpis.revenue_succeeded_delta_pct
            if rev_delta is not None and rev_delta > 0:
                detail = (
                    f"Ingresos {_format_money_es(kpis.revenue_succeeded)} "
                    f"({rev_delta:+.0f}% vs periodo anterior). Sin bloqueos operativos."
                )
            else:
                detail = (
                    f"{kpis.orders_created} pedidos creados · "
                    f"{_format_money_es(kpis.revenue_succeeded)} confirmados. "
                    "Sin bloqueos operativos."
                )
            return Briefing(
                headline="Operación al día",
                detail=detail,
                tone="clear",
            )

        top = work_items[0]
        critical = sum(1 for item in work_items if item.severity == "critical")
        high = sum(1 for item in work_items if item.severity == "high")
        if critical:
            tone: Literal["clear", "watch", "urgent"] = "urgent"
            headline = (
                f"{critical} urgencia operativa"
                if critical == 1
                else f"{critical} urgencias operativas"
            )
        elif high:
            tone = "watch"
            headline = f"{len(work_items)} acciones pendientes"
        else:
            tone = "watch"
            headline = f"{len(work_items)} seguimientos recomendados"

        money_bits: list[str] = []
        if money.awaiting_payment_confirm > 0:
            money_bits.append(
                f"{_format_money_es(money.awaiting_payment_confirm)} por confirmar"
            )
        if money.fulfillment_backlog > 0:
            money_bits.append(
                f"{_format_money_es(money.fulfillment_backlog)} por despachar"
            )
        money_part = (" · " + " y ".join(money_bits)) if money_bits else ""

        detail = f"Prioridad: {top.title} — {top.reason}.{money_part}"
        if kpis.revenue_succeeded_delta_pct is not None:
            detail += (
                f" Ingresos {_format_money_es(kpis.revenue_succeeded)} "
                f"({kpis.revenue_succeeded_delta_pct:+.0f}% vs anterior)."
            )
        return Briefing(headline=headline, detail=detail, tone=tone)

    def _count_and_oldest(self, stmt) -> tuple[int, datetime | None]:
        rows = list(self.db.scalars(stmt).all())
        if not rows:
            return 0, None
        return len(rows), rows[0]

    def _recent_orders(self, *, limit: int = 5) -> list[RecentOrderItem]:
        orders = self.db.scalars(
            select(Order).order_by(Order.created_at.desc()).limit(limit)
        ).all()
        return [
            RecentOrderItem(
                id=order.id,
                order_number=order.order_number,
                status=order.status,
                total=order.total,
                currency=order.currency,
                customer_email=order.customer_email,
                created_at=order.created_at,
            )
            for order in orders
        ]
