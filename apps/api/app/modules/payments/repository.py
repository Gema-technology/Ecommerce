from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.core.pagination import offset_for
from app.modules.orders.models import Order
from app.modules.payments.models import Payment, PaymentEvent, PaymentStatus


class PaymentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, payment_id: UUID, *, for_update: bool = False) -> Payment | None:
        # PostgreSQL rejects FOR UPDATE with LEFT OUTER JOIN from joinedload.
        if for_update:
            locked = self.db.scalar(
                select(Payment).where(Payment.id == payment_id).with_for_update()
            )
            if locked is None:
                return None
            return self.db.scalar(
                select(Payment)
                .options(joinedload(Payment.order))
                .where(Payment.id == locked.id)
            )
        return self.db.scalar(
            select(Payment)
            .options(joinedload(Payment.order))
            .where(Payment.id == payment_id)
        )

    def list_for_order(self, order_id: UUID) -> list[Payment]:
        return list(
            self.db.scalars(
                select(Payment)
                .options(joinedload(Payment.order))
                .where(Payment.order_id == order_id)
                .order_by(Payment.created_at.desc())
            )
            .unique()
            .all()
        )

    def list_all(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
        provider: str | None = None,
        q: str | None = None,
    ) -> tuple[list[Payment], int]:
        filters = []
        if status:
            filters.append(Payment.status == status)
        if provider:
            filters.append(Payment.provider == provider)
        if q:
            term = f"%{q.strip()}%"
            filters.append(
                or_(
                    Order.order_number.ilike(term),
                    Payment.provider_payment_id.ilike(term),
                )
            )

        count_stmt = select(func.count()).select_from(Payment)
        stmt = (
            select(Payment)
            .options(joinedload(Payment.order))
            .order_by(Payment.created_at.desc())
        )
        if q:
            count_stmt = count_stmt.join(Order, Order.id == Payment.order_id)
            stmt = stmt.join(Order, Order.id == Payment.order_id)
        for f in filters:
            count_stmt = count_stmt.where(f)
            stmt = stmt.where(f)
        total = int(self.db.scalar(count_stmt) or 0)
        items = list(
            self.db.scalars(
                stmt.offset(offset_for(page, page_size)).limit(page_size)
            )
            .unique()
            .all()
        )
        return items, total

    def has_succeeded(self, order_id: UUID) -> bool:
        return (
            self.db.scalar(
                select(Payment.id).where(
                    Payment.order_id == order_id,
                    Payment.status == PaymentStatus.SUCCEEDED.value,
                )
            )
            is not None
        )

    def get_by_provider_payment_id(
        self,
        provider: str,
        provider_payment_id: str,
        *,
        for_update: bool = False,
    ) -> Payment | None:
        query = select(Payment).where(
            Payment.provider == provider,
            Payment.provider_payment_id == provider_payment_id,
        )
        if for_update:
            locked = self.db.scalar(query.with_for_update())
            if locked is None:
                return None
            return self.db.scalar(
                select(Payment)
                .options(joinedload(Payment.order))
                .where(Payment.id == locked.id)
            )
        return self.db.scalar(
            select(Payment)
            .options(joinedload(Payment.order))
            .where(
                Payment.provider == provider,
                Payment.provider_payment_id == provider_payment_id,
            )
        )

    def add(self, payment: Payment) -> Payment:
        self.db.add(payment)
        self.db.flush()
        return payment

    def add_event(self, event: PaymentEvent) -> PaymentEvent:
        self.db.add(event)
        self.db.flush()
        return event

    def get_event(self, provider: str, provider_event_id: str) -> PaymentEvent | None:
        return self.db.scalar(
            select(PaymentEvent).where(
                PaymentEvent.provider == provider,
                PaymentEvent.provider_event_id == provider_event_id,
            )
        )
