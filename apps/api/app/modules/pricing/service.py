from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.catalog.models import Product
from app.modules.pricing.models import PriceCurrency, PriceType, ProductPrice
from app.modules.pricing.repository import PricingRepository
from app.modules.pricing.schemas import (
    EffectivePrice,
    MarginResult,
    ProductPriceCreate,
    ProductPriceRead,
    ProductPriceUpdate,
    PublicPrice,
)
from app.modules.roles.models import User
from sqlalchemy import or_, select


def _aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def calculate_margin(
    sale_price: Decimal,
    cost: Decimal,
    *,
    cost_source: str | None = None,
) -> MarginResult:
    sale = Decimal(sale_price)
    cst = Decimal(cost)
    margin_amount = sale - cst
    if sale == 0:
        margin_percentage = None
    else:
        margin_percentage = (margin_amount / sale) * Decimal("100")
    return MarginResult(
        sale_price=sale,
        cost=cst,
        margin_amount=margin_amount,
        margin_percentage=margin_percentage,
        cost_source=cost_source,
    )


class PricingService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = PricingRepository(db)

    def _to_read(self, price: ProductPrice) -> ProductPriceRead:
        supplier_name = None
        if price.supplier_product is not None and price.supplier_product.supplier is not None:
            supplier = price.supplier_product.supplier
            supplier_name = supplier.commercial_name or supplier.business_name
        return ProductPriceRead(
            id=price.id,
            product_id=price.product_id,
            price_type=PriceType(price.price_type),
            amount=price.amount,
            currency=PriceCurrency(price.currency),
            starts_at=price.starts_at,
            ends_at=price.ends_at,
            is_active=price.is_active,
            cost_reference=price.cost_reference,
            supplier_product_id=price.supplier_product_id,
            created_by=price.created_by,
            created_at=price.created_at,
            updated_at=price.updated_at,
            created_by_email=price.created_by_user.email if price.created_by_user else None,
            supplier_name=supplier_name,
        )

    def _ensure_product(self, product_id: UUID) -> Product:
        product = self.db.get(Product, product_id)
        if product is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
        return product

    def _ensure_no_overlap(
        self,
        *,
        product_id: UUID,
        price_type: str,
        starts_at: datetime,
        ends_at: datetime | None,
        exclude_id: UUID | None = None,
    ) -> None:
        conflict = self.repo.find_overlapping(
            product_id=product_id,
            price_type=price_type,
            starts_at=starts_at,
            ends_at=ends_at,
            exclude_id=exclude_id,
        )
        if conflict is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Overlapping active price exists for this product and price_type",
            )

    def create_price(
        self,
        product_id: UUID,
        data: ProductPriceCreate,
        user: User,
    ) -> ProductPriceRead:
        self._ensure_product(product_id)
        starts_at = data.starts_at or datetime.now(UTC)
        if data.ends_at is not None and data.ends_at <= starts_at:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="ends_at must be after starts_at",
            )

        cost_reference = data.cost_reference
        supplier_product_id = data.supplier_product_id
        if supplier_product_id is not None:
            sp = self.repo.get_supplier_product(supplier_product_id)
            if sp is None or sp.product_id != product_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="supplier_product_id must belong to this product",
                )
            if cost_reference is None:
                cost_reference = Decimal(sp.cost)

        if data.is_active:
            self._ensure_no_overlap(
                product_id=product_id,
                price_type=data.price_type.value,
                starts_at=starts_at,
                ends_at=data.ends_at,
            )

        price = ProductPrice(
            product_id=product_id,
            price_type=data.price_type.value,
            amount=Decimal(data.amount),
            currency=data.currency.value,
            starts_at=starts_at,
            ends_at=data.ends_at,
            is_active=data.is_active,
            cost_reference=cost_reference,
            supplier_product_id=supplier_product_id,
            created_by=user.id,
        )
        self.repo.create(price)
        self.db.commit()
        loaded = self.repo.get_by_id(price.id)
        assert loaded is not None
        return self._to_read(loaded)

    def list_prices(
        self,
        product_id: UUID,
        *,
        price_type: PriceType | None = None,
        active_only: bool | None = None,
    ) -> list[ProductPriceRead]:
        self._ensure_product(product_id)
        return [
            self._to_read(p)
            for p in self.repo.list_for_product(
                product_id,
                price_type=price_type.value if price_type else None,
                active_only=active_only,
            )
        ]

    def get_price_history(self, product_id: UUID) -> list[ProductPriceRead]:
        return self.list_prices(product_id)

    def get_current_price(
        self,
        product_id: UUID,
        *,
        price_type: PriceType = PriceType.RETAIL,
    ) -> ProductPriceRead | None:
        self._ensure_product(product_id)
        price = self.repo.get_current_price(product_id, price_type=price_type.value)
        return self._to_read(price) if price else None

    def get_public_price(self, product_id: UUID) -> PublicPrice | None:
        effective = self.resolve_effective_price(product_id)
        if effective is None:
            return None
        return PublicPrice(
            amount=effective.amount,
            currency=effective.currency,
            price_type=effective.price_type,
            compare_at_amount=effective.compare_at_amount,
        )

    def resolve_effective_price(
        self,
        product_id: UUID,
        *,
        at: datetime | None = None,
    ) -> EffectivePrice | None:
        """Single source of truth: active PROMOTIONAL wins over RETAIL."""
        mapped = self.map_effective_prices([product_id], at=at)
        return mapped.get(product_id)

    def map_effective_prices(
        self,
        product_ids: list[UUID],
        *,
        at: datetime | None = None,
    ) -> dict[UUID, EffectivePrice | None]:
        if not product_ids:
            return {}

        moment = at or datetime.now(UTC)
        rows = list(
            self.db.scalars(
                select(ProductPrice)
                .where(
                    ProductPrice.product_id.in_(product_ids),
                    ProductPrice.price_type.in_(
                        [PriceType.PROMOTIONAL.value, PriceType.RETAIL.value]
                    ),
                    ProductPrice.is_active.is_(True),
                    ProductPrice.starts_at <= moment,
                    or_(ProductPrice.ends_at.is_(None), ProductPrice.ends_at > moment),
                )
                .order_by(
                    ProductPrice.product_id,
                    ProductPrice.price_type.asc(),  # PROMOTIONAL before RETAIL
                    ProductPrice.starts_at.desc(),
                )
            ).all()
        )

        by_product: dict[UUID, list[ProductPrice]] = {pid: [] for pid in product_ids}
        for row in rows:
            by_product[row.product_id].append(row)

        result: dict[UUID, EffectivePrice | None] = {pid: None for pid in product_ids}
        for pid, price_rows in by_product.items():
            if not price_rows:
                continue
            # First row is preferred type (promo then retail), latest starts_at
            seen_types: set[str] = set()
            chosen: ProductPrice | None = None
            retail: ProductPrice | None = None
            for row in price_rows:
                if row.price_type not in seen_types:
                    seen_types.add(row.price_type)
                    if chosen is None:
                        chosen = row
                    if row.price_type == PriceType.RETAIL.value:
                        retail = row
            if chosen is None:
                continue
            compare_at = None
            if (
                chosen.price_type == PriceType.PROMOTIONAL.value
                and retail is not None
                and retail.amount > chosen.amount
            ):
                compare_at = retail.amount
            result[pid] = EffectivePrice(
                amount=chosen.amount,
                currency=PriceCurrency(chosen.currency),
                price_type=PriceType(chosen.price_type),
                compare_at_amount=compare_at,
            )
        return result

    def map_public_prices(self, product_ids: list[UUID]) -> dict[UUID, PublicPrice | None]:
        return {
            pid: (
                None
                if eff is None
                else PublicPrice(
                    amount=eff.amount,
                    currency=eff.currency,
                    price_type=eff.price_type,
                    compare_at_amount=eff.compare_at_amount,
                )
            )
            for pid, eff in self.map_effective_prices(product_ids).items()
        }
    def update_price(
        self,
        product_id: UUID,
        price_id: UUID,
        data: ProductPriceUpdate,
    ) -> ProductPriceRead:
        self._ensure_product(product_id)
        price = self.repo.get_by_id(price_id)
        if price is None or price.product_id != product_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Price not found")

        now = datetime.now(UTC)
        updates = data.model_dump(exclude_unset=True)
        has_started = _aware(price.starts_at) <= now

        # Historical prices: do not silently change amount/currency/starts_at
        if has_started:
            forbidden = {"amount", "currency", "starts_at"}
            attempted = forbidden.intersection(updates)
            if attempted:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Cannot modify amount/currency/starts_at of a price that has already started; create a new price instead",
                )

        if "currency" in updates and updates["currency"] is not None:
            updates["currency"] = updates["currency"].value
        if "amount" in updates and updates["amount"] is not None:
            updates["amount"] = Decimal(updates["amount"])
        if "cost_reference" in updates and updates["cost_reference"] is not None:
            updates["cost_reference"] = Decimal(updates["cost_reference"])

        if "supplier_product_id" in updates and updates["supplier_product_id"] is not None:
            sp = self.repo.get_supplier_product(updates["supplier_product_id"])
            if sp is None or sp.product_id != product_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="supplier_product_id must belong to this product",
                )
            if "cost_reference" not in updates:
                updates["cost_reference"] = Decimal(sp.cost)

        starts_at = _aware(updates.get("starts_at", price.starts_at))
        ends_at = updates.get("ends_at", price.ends_at)
        if ends_at is not None:
            ends_at = _aware(ends_at)
        is_active = updates.get("is_active", price.is_active)
        if ends_at is not None and ends_at <= starts_at:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="ends_at must be after starts_at",
            )

        will_be_active = bool(is_active)
        if will_be_active:
            self._ensure_no_overlap(
                product_id=product_id,
                price_type=price.price_type,
                starts_at=starts_at,
                ends_at=ends_at,
                exclude_id=price.id,
            )

        for key, value in updates.items():
            setattr(price, key, value)

        self.repo.save(price)
        self.db.commit()
        loaded = self.repo.get_by_id(price.id)
        assert loaded is not None
        return self._to_read(loaded)

    def deactivate_price(self, product_id: UUID, price_id: UUID) -> ProductPriceRead:
        return self.update_price(
            product_id, price_id, ProductPriceUpdate(is_active=False)
        )

    def activate_price(self, product_id: UUID, price_id: UUID) -> ProductPriceRead:
        return self.update_price(
            product_id, price_id, ProductPriceUpdate(is_active=True)
        )

    def calculate_margin_for_product(
        self,
        product_id: UUID,
        *,
        supplier_product_id: UUID | None = None,
        price_type: PriceType = PriceType.RETAIL,
    ) -> MarginResult:
        current = self.get_current_price(product_id, price_type=price_type)
        if current is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No current price found",
            )

        cost = current.cost_reference
        cost_source = current.supplier_name

        if supplier_product_id is not None:
            sp = self.repo.get_supplier_product(supplier_product_id)
            if sp is None or sp.product_id != product_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="supplier_product_id must belong to this product",
                )
            cost = Decimal(sp.cost)
            supplier = sp.supplier
            cost_source = (
                (supplier.commercial_name or supplier.business_name) if supplier else None
            )
        elif cost is None:
            # Prefer explicit supplier_product on the price, else require selection
            if current.supplier_product_id:
                sp = self.repo.get_supplier_product(current.supplier_product_id)
                if sp is not None:
                    cost = Decimal(sp.cost)
                    supplier = sp.supplier
                    cost_source = (
                        (supplier.commercial_name or supplier.business_name)
                        if supplier
                        else None
                    )
            else:
                # Multiple suppliers possible — do not pick arbitrarily
                from app.modules.suppliers.models import SupplierProduct as SP

                sps = list(
                    self.db.scalars(
                        select(SP).where(SP.product_id == product_id, SP.is_active.is_(True))
                    ).all()
                )
                if len(sps) == 1:
                    cost = Decimal(sps[0].cost)
                    sp = self.repo.get_supplier_product(sps[0].id)
                    if sp and sp.supplier:
                        cost_source = sp.supplier.commercial_name or sp.supplier.business_name
                elif len(sps) > 1:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Multiple supplier costs available; provide supplier_product_id",
                    )
                else:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="No cost reference available",
                    )

        assert cost is not None
        return calculate_margin(current.amount, cost, cost_source=cost_source)
