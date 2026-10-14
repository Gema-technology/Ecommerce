import math
from datetime import date
from uuid import UUID

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.modules.quotes.models import (
    PricingConfig,
    Quote,
    QuoteItem,
    QuoteNumberCounter,
    QuoteProduct,
)


class QuoteRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_or_create_pricing_config(self) -> PricingConfig:
        config = self.db.get(PricingConfig, 1)
        if config is None:
            config = PricingConfig(id=1)
            self.db.add(config)
            self.db.flush()
        return config

    def list_products(
        self,
        *,
        q: str | None = None,
        page: int = 1,
        page_size: int = 20,
        active_only: bool = False,
    ) -> tuple[list[QuoteProduct], int]:
        filters = []
        if active_only:
            filters.append(QuoteProduct.is_active.is_(True))
        if q:
            pattern = f"%{q.strip()}%"
            filters.append(
                or_(
                    QuoteProduct.name.ilike(pattern),
                    QuoteProduct.category.ilike(pattern),
                )
            )
        return self._paginate_products(filters, page=page, page_size=page_size)

    def _paginate_products(
        self,
        filters: list,
        *,
        page: int,
        page_size: int,
    ) -> tuple[list[QuoteProduct], int]:
        count_stmt = select(func.count()).select_from(QuoteProduct)
        stmt: Select[tuple[QuoteProduct]] = (
            select(QuoteProduct).order_by(QuoteProduct.name.asc())
        )
        for f in filters:
            count_stmt = count_stmt.where(f)
            stmt = stmt.where(f)
        total = int(self.db.scalar(count_stmt) or 0)
        offset = max(0, (page - 1) * page_size)
        items = list(self.db.scalars(stmt.offset(offset).limit(page_size)).all())
        return items, total

    def get_product(self, product_id: UUID) -> QuoteProduct | None:
        return self.db.get(QuoteProduct, product_id)

    def add_product(self, product: QuoteProduct) -> QuoteProduct:
        self.db.add(product)
        self.db.flush()
        return product

    def delete_product(self, product: QuoteProduct) -> None:
        self.db.delete(product)

    def next_quote_number(self) -> str:
        counter = self.db.scalar(
            select(QuoteNumberCounter).where(QuoteNumberCounter.id == 1).with_for_update()
        )
        if counter is None:
            counter = QuoteNumberCounter(id=1, last_value=0)
            self.db.add(counter)
            self.db.flush()
            counter = self.db.scalar(
                select(QuoteNumberCounter).where(QuoteNumberCounter.id == 1).with_for_update()
            )
            assert counter is not None
        counter.last_value += 1
        self.db.flush()
        return f"PRO-{counter.last_value:04d}"

    def add_quote(self, quote: Quote) -> Quote:
        self.db.add(quote)
        self.db.flush()
        return quote

    def get_quote(self, quote_id: UUID) -> Quote | None:
        return self.db.scalar(
            select(Quote)
            .options(
                selectinload(Quote.items),
                joinedload(Quote.created_by_user),
            )
            .where(Quote.id == quote_id)
        )

    def list_quotes(
        self,
        *,
        status: str | None = None,
        client: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Quote], int]:
        filters = []
        if status:
            filters.append(Quote.status == status)
        if client:
            pattern = f"%{client.strip()}%"
            filters.append(
                or_(
                    Quote.client_name.ilike(pattern),
                    Quote.client_email.ilike(pattern),
                    Quote.number.ilike(pattern),
                )
            )
        if date_from:
            filters.append(func.date(Quote.created_at) >= date_from)
        if date_to:
            filters.append(func.date(Quote.created_at) <= date_to)
        return self._paginate_quotes(filters, page=page, page_size=page_size)

    def _paginate_quotes(
        self,
        filters: list,
        *,
        page: int,
        page_size: int,
    ) -> tuple[list[Quote], int]:
        count_stmt = select(func.count()).select_from(Quote)
        stmt: Select[tuple[Quote]] = (
            select(Quote)
            .options(
                selectinload(Quote.items),
                joinedload(Quote.created_by_user),
            )
            .order_by(Quote.created_at.desc())
        )
        for f in filters:
            count_stmt = count_stmt.where(f)
            stmt = stmt.where(f)
        total = int(self.db.scalar(count_stmt) or 0)
        offset = max(0, (page - 1) * page_size)
        items = list(self.db.scalars(stmt.offset(offset).limit(page_size)).unique().all())
        return items, total

    def delete_quote(self, quote: Quote) -> None:
        self.db.delete(quote)

    @staticmethod
    def total_pages(total: int, page_size: int) -> int:
        if total == 0:
            return 0
        return math.ceil(total / page_size)
