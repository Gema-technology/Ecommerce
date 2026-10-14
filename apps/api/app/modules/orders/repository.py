from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.modules.orders.models import Order, OrderDailyCounter, OrderItem


class OrderRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, order_id: UUID) -> Order | None:
        return self.db.scalar(
            select(Order)
            .options(
                selectinload(Order.items),
                joinedload(Order.user),
            )
            .where(Order.id == order_id)
        )

    def get_by_number(self, order_number: str) -> Order | None:
        return self.db.scalar(
            select(Order)
            .options(
                selectinload(Order.items),
                joinedload(Order.user),
            )
            .where(Order.order_number == order_number)
        )

    def list_for_user(
        self,
        user_id: UUID,
        *,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Order], int]:
        filters = [Order.user_id == user_id]
        return self._paginate(filters, page=page, page_size=page_size)

    def list_all(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
    ) -> tuple[list[Order], int]:
        filters = []
        if status:
            filters.append(Order.status == status)
        return self._paginate(filters, page=page, page_size=page_size)

    def _paginate(
        self,
        filters: list,
        *,
        page: int,
        page_size: int,
    ) -> tuple[list[Order], int]:
        count_stmt = select(func.count()).select_from(Order)
        stmt: Select[tuple[Order]] = (
            select(Order)
            .options(selectinload(Order.items), joinedload(Order.user))
            .order_by(Order.created_at.desc())
        )
        for f in filters:
            count_stmt = count_stmt.where(f)
            stmt = stmt.where(f)
        total = int(self.db.scalar(count_stmt) or 0)
        offset = max(0, (page - 1) * page_size)
        items = list(self.db.scalars(stmt.offset(offset).limit(page_size)).unique().all())
        return items, total

    def next_order_number(self) -> str:
        day = datetime.now(UTC).strftime("%Y%m%d")
        counter = self.db.scalar(
            select(OrderDailyCounter)
            .where(OrderDailyCounter.day == day)
            .with_for_update()
        )
        if counter is None:
            counter = OrderDailyCounter(day=day, last_value=0)
            self.db.add(counter)
            self.db.flush()
            counter = self.db.scalar(
                select(OrderDailyCounter)
                .where(OrderDailyCounter.day == day)
                .with_for_update()
            )
            assert counter is not None
        counter.last_value += 1
        self.db.flush()
        return f"GEMA-{day}-{counter.last_value:06d}"

    def add(self, order: Order) -> Order:
        self.db.add(order)
        self.db.flush()
        return order

    def add_item(self, item: OrderItem) -> OrderItem:
        self.db.add(item)
        self.db.flush()
        return item
