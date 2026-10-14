from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.catalog.models import Category, Product


class CategoryRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, category_id: UUID) -> Category | None:
        return self.db.get(Category, category_id)

    def get_by_slug(self, slug: str) -> Category | None:
        return self.db.scalar(select(Category).where(Category.slug == slug))

    def list_all(self, *, active_only: bool = False) -> list[Category]:
        stmt = select(Category).order_by(Category.name)
        if active_only:
            stmt = stmt.where(Category.is_active.is_(True))
        return list(self.db.scalars(stmt).all())

    def create(self, category: Category) -> Category:
        self.db.add(category)
        self.db.flush()
        return category

    def save(self, category: Category) -> Category:
        self.db.add(category)
        self.db.flush()
        return category

    def slug_exists(self, slug: str, *, exclude_id: UUID | None = None) -> bool:
        stmt = select(Category.id).where(Category.slug == slug)
        if exclude_id is not None:
            stmt = stmt.where(Category.id != exclude_id)
        return self.db.scalar(stmt) is not None

    def count_active_products(self, category_id: UUID) -> int:
        return int(
            self.db.scalar(
                select(func.count())
                .select_from(Product)
                .where(Product.category_id == category_id, Product.is_active.is_(True))
            )
            or 0
        )

    def get_descendant_ids(self, category_id: UUID) -> set[UUID]:
        """Collect all descendant category IDs (BFS, any depth)."""
        descendants: set[UUID] = set()
        frontier = [category_id]
        while frontier:
            current = frontier.pop()
            children = list(
                self.db.scalars(select(Category.id).where(Category.parent_id == current)).all()
            )
            for child_id in children:
                if child_id not in descendants:
                    descendants.add(child_id)
                    frontier.append(child_id)
        return descendants

    def get_subtree_ids(self, category_id: UUID) -> set[UUID]:
        """Category itself plus all descendants at any depth."""
        return {category_id} | self.get_descendant_ids(category_id)

    def get_subtree_ids_by_slug(self, slug: str) -> set[UUID] | None:
        category = self.get_by_slug(slug)
        if category is None:
            return None
        return self.get_subtree_ids(category.id)

    def get_ancestor_ids(self, category_id: UUID) -> set[UUID]:
        """Collect all ancestor category IDs walking parent_id toward the root."""
        ancestors: set[UUID] = set()
        current = self.get_by_id(category_id)
        while current is not None and current.parent_id is not None:
            ancestors.add(current.parent_id)
            current = self.get_by_id(current.parent_id)
        return ancestors

    def get_filter_affinity_ids(self, category_id: UUID) -> set[UUID]:
        """IDs that match brand affinity for a category filter (ancestors + subtree)."""
        return self.get_ancestor_ids(category_id) | self.get_subtree_ids(category_id)

    def get_filter_affinity_ids_by_slug(self, slug: str) -> set[UUID] | None:
        category = self.get_by_slug(slug)
        if category is None:
            return None
        return self.get_filter_affinity_ids(category.id)
