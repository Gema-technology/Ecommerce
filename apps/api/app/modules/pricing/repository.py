from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.modules.pricing.models import PriceType, ProductPrice
from app.modules.suppliers.models import SupplierProduct


class PricingRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, price_id: UUID) -> ProductPrice | None:
        return self.db.scalar(
            select(ProductPrice)
            .options(
                joinedload(ProductPrice.created_by_user),
                joinedload(ProductPrice.supplier_product).joinedload(
                    SupplierProduct.supplier
                ),
            )
            .where(ProductPrice.id == price_id)
        )

    def list_for_product(
        self,
        product_id: UUID,
        *,
        price_type: str | None = None,
        active_only: bool | None = None,
    ) -> list[ProductPrice]:
        stmt = (
            select(ProductPrice)
            .options(
                joinedload(ProductPrice.created_by_user),
                joinedload(ProductPrice.supplier_product).joinedload(
                    SupplierProduct.supplier
                ),
            )
            .where(ProductPrice.product_id == product_id)
            .order_by(ProductPrice.starts_at.desc(), ProductPrice.created_at.desc())
        )
        if price_type is not None:
            stmt = stmt.where(ProductPrice.price_type == price_type)
        if active_only is True:
            stmt = stmt.where(ProductPrice.is_active.is_(True))
        return list(self.db.scalars(stmt).unique().all())

    def create(self, price: ProductPrice) -> ProductPrice:
        self.db.add(price)
        self.db.flush()
        return price

    def save(self, price: ProductPrice) -> ProductPrice:
        self.db.add(price)
        self.db.flush()
        return price

    def find_overlapping(
        self,
        *,
        product_id: UUID,
        price_type: str,
        starts_at: datetime,
        ends_at: datetime | None,
        exclude_id: UUID | None = None,
    ) -> ProductPrice | None:
        """Find an active price of the same type whose validity overlaps [starts_at, ends_at]."""
        # Overlap: existing.starts_at <= new.ends_at AND new.starts_at <= existing.ends_at
        # null ends_at means open-ended (+inf)
        conditions = [
            ProductPrice.product_id == product_id,
            ProductPrice.price_type == price_type,
            ProductPrice.is_active.is_(True),
        ]
        if ends_at is None:
            # new is open-ended: overlaps anything that hasn't ended before starts_at
            conditions.append(
                or_(ProductPrice.ends_at.is_(None), ProductPrice.ends_at > starts_at)
            )
        else:
            conditions.append(ProductPrice.starts_at < ends_at)
            conditions.append(
                or_(ProductPrice.ends_at.is_(None), ProductPrice.ends_at > starts_at)
            )

        stmt = select(ProductPrice).where(and_(*conditions))
        if exclude_id is not None:
            stmt = stmt.where(ProductPrice.id != exclude_id)
        return self.db.scalar(stmt.limit(1))

    def get_current_price(
        self,
        product_id: UUID,
        *,
        price_type: str = PriceType.RETAIL.value,
        at: datetime | None = None,
    ) -> ProductPrice | None:
        moment = at or datetime.now(UTC)
        stmt = (
            select(ProductPrice)
            .where(
                ProductPrice.product_id == product_id,
                ProductPrice.price_type == price_type,
                ProductPrice.is_active.is_(True),
                ProductPrice.starts_at <= moment,
                or_(ProductPrice.ends_at.is_(None), ProductPrice.ends_at > moment),
            )
            .order_by(ProductPrice.starts_at.desc())
            .limit(1)
        )
        return self.db.scalar(stmt)

    def map_current_retail_prices(
        self,
        product_ids: list[UUID],
        *,
        at: datetime | None = None,
    ) -> dict[UUID, ProductPrice]:
        if not product_ids:
            return {}
        moment = at or datetime.now(UTC)
        rows = list(
            self.db.scalars(
                select(ProductPrice)
                .where(
                    ProductPrice.product_id.in_(product_ids),
                    ProductPrice.price_type == PriceType.RETAIL.value,
                    ProductPrice.is_active.is_(True),
                    ProductPrice.starts_at <= moment,
                    or_(ProductPrice.ends_at.is_(None), ProductPrice.ends_at > moment),
                )
                .order_by(ProductPrice.product_id, ProductPrice.starts_at.desc())
            ).all()
        )
        result: dict[UUID, ProductPrice] = {}
        for row in rows:
            if row.product_id not in result:
                result[row.product_id] = row
        return result

    def get_supplier_product(self, supplier_product_id: UUID) -> SupplierProduct | None:
        return self.db.scalar(
            select(SupplierProduct)
            .options(joinedload(SupplierProduct.supplier))
            .where(SupplierProduct.id == supplier_product_id)
        )
