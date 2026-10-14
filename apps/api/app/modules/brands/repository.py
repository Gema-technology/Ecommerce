from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.pagination import offset_for
from app.modules.catalog.models import Brand, Category, Product, brand_categories


class BrandRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, brand_id: UUID) -> Brand | None:
        return self.db.get(Brand, brand_id)

    def get_by_slug(self, slug: str) -> Brand | None:
        return self.db.scalar(select(Brand).where(Brand.slug == slug))

    def list_all(
        self,
        *,
        active_only: bool = False,
        category_slug: str | None = None,
    ) -> list[Brand]:
        items, _ = self.list_paginated(
            is_active=True if active_only else None,
            category_slug=category_slug,
            page=1,
            page_size=10_000,
        )
        return items

    def list_paginated(
        self,
        *,
        is_active: bool | None = None,
        category_slug: str | None = None,
        q: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Brand], int]:
        stmt = select(Brand).order_by(Brand.name)
        if is_active is True:
            stmt = stmt.where(Brand.is_active.is_(True))
        elif is_active is False:
            stmt = stmt.where(Brand.is_active.is_(False))
        if q:
            term = f"%{q.strip()}%"
            stmt = stmt.where(or_(Brand.name.ilike(term), Brand.slug.ilike(term)))
        if category_slug:
            from app.modules.categories.repository import CategoryRepository

            affinity_ids = CategoryRepository(self.db).get_filter_affinity_ids_by_slug(
                category_slug
            )
            if affinity_ids is None:
                return [], 0
            stmt = (
                stmt.join(brand_categories, brand_categories.c.brand_id == Brand.id)
                .where(brand_categories.c.category_id.in_(affinity_ids))
                .distinct()
            )
        count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
        total = int(self.db.scalar(count_stmt) or 0)
        items = list(
            self.db.scalars(
                stmt.offset(offset_for(page, page_size)).limit(page_size)
            ).all()
        )
        return items, total

    def create(self, brand: Brand) -> Brand:
        self.db.add(brand)
        self.db.flush()
        return brand

    def save(self, brand: Brand) -> Brand:
        self.db.add(brand)
        self.db.flush()
        return brand

    def slug_exists(self, slug: str, *, exclude_id: UUID | None = None) -> bool:
        stmt = select(Brand.id).where(Brand.slug == slug)
        if exclude_id is not None:
            stmt = stmt.where(Brand.id != exclude_id)
        return self.db.scalar(stmt) is not None

    def count_active_products(self, brand_id: UUID) -> int:
        return int(
            self.db.scalar(
                select(func.count())
                .select_from(Product)
                .where(Product.brand_id == brand_id, Product.is_active.is_(True))
            )
            or 0
        )

    def resolve_categories(self, category_ids: list[UUID]) -> list[Category]:
        if not category_ids:
            return []
        unique_ids = list(dict.fromkeys(category_ids))
        categories = list(
            self.db.scalars(select(Category).where(Category.id.in_(unique_ids))).all()
        )
        found = {c.id for c in categories}
        missing = [cid for cid in unique_ids if cid not in found]
        if missing:
            return []
        by_id = {c.id: c for c in categories}
        return [by_id[cid] for cid in unique_ids]

    def allows_category(self, brand: Brand, category_id: UUID) -> bool:
        """True if category_id is in the union of affinity category subtrees."""
        if not brand.categories:
            return False
        from app.modules.categories.repository import CategoryRepository

        cat_repo = CategoryRepository(self.db)
        for affinity in brand.categories:
            if category_id in cat_repo.get_subtree_ids(affinity.id):
                return True
        return False
