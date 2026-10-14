from uuid import UUID
from decimal import Decimal
from datetime import UTC, datetime

from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.modules.catalog.models import Product, ProductImage
from app.modules.pricing.models import PriceType, ProductPrice
from app.modules.products.schemas import ProductSort


def _product_options():
    return (
        selectinload(Product.brand),
        selectinload(Product.category),
        selectinload(Product.images),
    )


class ProductRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, product_id: UUID) -> Product | None:
        return self.db.scalar(
            select(Product).where(Product.id == product_id).options(*_product_options())
        )

    def get_by_slug(self, slug: str) -> Product | None:
        return self.db.scalar(
            select(Product).where(Product.slug == slug).options(*_product_options())
        )

    def get_by_sku(self, sku: str) -> Product | None:
        return self.db.scalar(select(Product).where(Product.sku == sku))

    def slug_exists(self, slug: str, *, exclude_id: UUID | None = None) -> bool:
        stmt = select(Product.id).where(Product.slug == slug)
        if exclude_id is not None:
            stmt = stmt.where(Product.id != exclude_id)
        return self.db.scalar(stmt) is not None

    def sku_exists(self, sku: str, *, exclude_id: UUID | None = None) -> bool:
        stmt = select(Product.id).where(Product.sku == sku)
        if exclude_id is not None:
            stmt = stmt.where(Product.id != exclude_id)
        return self.db.scalar(stmt) is not None

    def create(self, product: Product) -> Product:
        self.db.add(product)
        self.db.flush()
        return product

    def save(self, product: Product) -> Product:
        self.db.add(product)
        self.db.flush()
        return product

    def replace_images(self, product: Product, images: list[ProductImage]) -> None:
        product.images.clear()
        self.db.flush()
        for image in images:
            product.images.append(image)
        self.db.flush()

    def _current_price_expr(self, moment: datetime):
        return (
            select(ProductPrice.amount)
            .where(
                ProductPrice.product_id == Product.id,
                ProductPrice.price_type.in_(
                    [PriceType.PROMOTIONAL.value, PriceType.RETAIL.value]
                ),
                ProductPrice.is_active.is_(True),
                ProductPrice.starts_at <= moment,
                or_(ProductPrice.ends_at.is_(None), ProductPrice.ends_at > moment),
            )
            # Prefer promotional when both exist by ordering type then starts
            .order_by(
                # PROMOTIONAL before RETAIL lexicographically? P comes before R - good
                ProductPrice.price_type.asc(),
                ProductPrice.starts_at.desc(),
            )
            .limit(1)
            .scalar_subquery()
            .correlate(Product)
        )

    def list_filtered(
        self,
        *,
        category_slug: str | None = None,
        brand_slug: str | None = None,
        is_active: bool | None = True,
        min_price: Decimal | None = None,
        max_price: Decimal | None = None,
        search: str | None = None,
        sort: ProductSort = ProductSort.NEWEST,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Product], int]:
        from app.modules.catalog.models import Brand

        moment = datetime.now(UTC)
        current_price = self._current_price_expr(moment)

        stmt = select(Product).options(*_product_options())
        count_stmt = select(func.count()).select_from(Product)

        if is_active is not None:
            stmt = stmt.where(Product.is_active.is_(is_active))
            count_stmt = count_stmt.where(Product.is_active.is_(is_active))

        if category_slug:
            from app.modules.categories.repository import CategoryRepository

            subtree_ids = CategoryRepository(self.db).get_subtree_ids_by_slug(category_slug)
            if subtree_ids is None:
                # Unknown slug → empty result set
                stmt = stmt.where(Product.id.is_(None))
                count_stmt = count_stmt.where(Product.id.is_(None))
            else:
                stmt = stmt.where(Product.category_id.in_(subtree_ids))
                count_stmt = count_stmt.where(Product.category_id.in_(subtree_ids))

        if brand_slug:
            stmt = stmt.join(Product.brand).where(Brand.slug == brand_slug)
            count_stmt = count_stmt.join(Product.brand).where(Brand.slug == brand_slug)

        if search:
            term = f"%{search.strip()}%"
            search_filter = or_(
                Product.name.ilike(term),
                Product.sku.ilike(term),
                Product.slug.ilike(term),
                Product.short_description.ilike(term),
            )
            stmt = stmt.where(search_filter)
            count_stmt = count_stmt.where(search_filter)

        if min_price is not None or max_price is not None:
            price_exists = (
                select(ProductPrice.id)
                .where(
                    ProductPrice.product_id == Product.id,
                    ProductPrice.price_type.in_(
                        [PriceType.RETAIL.value, PriceType.PROMOTIONAL.value]
                    ),
                    ProductPrice.is_active.is_(True),
                    ProductPrice.starts_at <= moment,
                    or_(ProductPrice.ends_at.is_(None), ProductPrice.ends_at > moment),
                )
                .exists()
            )
            stmt = stmt.where(price_exists)
            count_stmt = count_stmt.where(price_exists)
            if min_price is not None:
                stmt = stmt.where(current_price >= min_price)
                count_stmt = count_stmt.where(current_price >= min_price)
            if max_price is not None:
                stmt = stmt.where(current_price <= max_price)
                count_stmt = count_stmt.where(current_price <= max_price)

        if sort == ProductSort.PRICE_ASC:
            stmt = stmt.order_by(asc(current_price), Product.name.asc())
        elif sort == ProductSort.PRICE_DESC:
            stmt = stmt.order_by(desc(current_price), Product.name.asc())
        elif sort == ProductSort.NAME_ASC:
            stmt = stmt.order_by(Product.name.asc())
        elif sort == ProductSort.NAME_DESC:
            stmt = stmt.order_by(Product.name.desc())
        elif sort == ProductSort.RELEVANCE and search:
            # Simple relevance: name match first, then newest
            stmt = stmt.order_by(Product.name.asc(), Product.created_at.desc())
        else:
            stmt = stmt.order_by(Product.created_at.desc())

        total = int(self.db.scalar(count_stmt) or 0)
        offset = max(page - 1, 0) * page_size
        items = list(self.db.scalars(stmt.offset(offset).limit(page_size)).all())
        return items, total
