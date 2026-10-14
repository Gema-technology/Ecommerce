from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.catalog.models import Category
from app.modules.categories.repository import CategoryRepository
from app.modules.categories.schemas import CategoryCreate, CategoryRead, CategoryUpdate
from app.shared.slug import slugify


class CategoryService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = CategoryRepository(db)

    def _unique_slug(self, base: str, *, exclude_id: UUID | None = None) -> str:
        candidate = slugify(base)
        if not self.repo.slug_exists(candidate, exclude_id=exclude_id):
            return candidate
        counter = 2
        while self.repo.slug_exists(f"{candidate}-{counter}", exclude_id=exclude_id):
            counter += 1
        return f"{candidate}-{counter}"

    def _validate_parent(self, parent_id: UUID | None, *, self_id: UUID | None = None) -> None:
        if parent_id is None:
            return
        parent = self.repo.get_by_id(parent_id)
        if parent is None or not parent.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Parent category not found",
            )
        if self_id is not None:
            if parent_id == self_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Category cannot be its own parent",
                )
            if parent_id in self.repo.get_descendant_ids(self_id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Circular category hierarchy is not allowed",
                )

    def create(self, data: CategoryCreate) -> CategoryRead:
        self._validate_parent(data.parent_id)
        base_slug = data.slug or data.name
        slug = self._unique_slug(base_slug)
        category = Category(
            name=data.name,
            slug=slug,
            description=data.description,
            image_url=data.image_url,
            parent_id=data.parent_id,
            is_active=data.is_active,
        )
        self.repo.create(category)
        self.db.commit()
        self.db.refresh(category)
        return CategoryRead.model_validate(category)

    def list_categories(self, *, active_only: bool = True) -> list[CategoryRead]:
        return [CategoryRead.model_validate(c) for c in self.repo.list_all(active_only=active_only)]

    def get_by_slug(self, slug: str) -> CategoryRead:
        category = self.repo.get_by_slug(slug)
        if category is None or not category.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
        return CategoryRead.model_validate(category)

    def update(self, category_id: UUID, data: CategoryUpdate) -> CategoryRead:
        category = self.repo.get_by_id(category_id)
        if category is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

        updates = data.model_dump(exclude_unset=True)
        if "parent_id" in updates:
            self._validate_parent(updates["parent_id"], self_id=category.id)
        if "name" in updates and "slug" not in updates:
            updates["slug"] = self._unique_slug(updates["name"], exclude_id=category.id)
        elif "slug" in updates and updates["slug"]:
            updates["slug"] = self._unique_slug(updates["slug"], exclude_id=category.id)

        for key, value in updates.items():
            setattr(category, key, value)

        self.repo.save(category)
        self.db.commit()
        self.db.refresh(category)
        return CategoryRead.model_validate(category)

    def soft_delete(self, category_id: UUID) -> CategoryRead:
        category = self.repo.get_by_id(category_id)
        if category is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
        if self.repo.count_active_products(category_id) > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot deactivate category with active products",
            )
        category.is_active = False
        self.repo.save(category)
        self.db.commit()
        self.db.refresh(category)
        return CategoryRead.model_validate(category)
