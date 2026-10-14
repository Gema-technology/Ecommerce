from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.pagination import total_pages
from app.modules.brands.repository import BrandRepository
from app.modules.brands.schemas import BrandCreate, BrandListResponse, BrandRead, BrandUpdate
from app.modules.catalog.models import Brand
from app.shared.slug import slugify


class BrandService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = BrandRepository(db)

    def _unique_slug(self, base: str, *, exclude_id: UUID | None = None) -> str:
        candidate = slugify(base)
        if not self.repo.slug_exists(candidate, exclude_id=exclude_id):
            return candidate
        counter = 2
        while self.repo.slug_exists(f"{candidate}-{counter}", exclude_id=exclude_id):
            counter += 1
        return f"{candidate}-{counter}"

    def _to_read(self, brand: Brand) -> BrandRead:
        return BrandRead.from_brand(brand)

    def _set_categories(self, brand: Brand, category_ids: list[UUID]) -> None:
        if not category_ids:
            brand.categories = []
            return
        categories = self.repo.resolve_categories(category_ids)
        if not categories:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One or more categories not found",
            )
        brand.categories = categories

    def create(self, data: BrandCreate) -> BrandRead:
        slug = self._unique_slug(data.slug or data.name)
        brand = Brand(
            name=data.name,
            slug=slug,
            description=data.description,
            logo_url=data.logo_url,
            website_url=data.website_url,
            is_active=data.is_active,
        )
        self._set_categories(brand, data.category_ids)
        self.repo.create(brand)
        self.db.commit()
        self.db.refresh(brand)
        return self._to_read(brand)

    def list_brands(
        self,
        *,
        active_only: bool = True,
        category_slug: str | None = None,
    ) -> list[BrandRead]:
        items = self.repo.list_all(
            active_only=active_only, category_slug=category_slug
        )
        return [self._to_read(b) for b in items]

    def list_brands_paginated(
        self,
        *,
        category_slug: str | None = None,
        q: str | None = None,
        page: int = 1,
        page_size: int = 20,
        is_active: bool | None = None,
    ) -> BrandListResponse:
        items, total = self.repo.list_paginated(
            is_active=is_active,
            category_slug=category_slug,
            q=q,
            page=page,
            page_size=page_size,
        )
        return BrandListResponse(
            items=[self._to_read(b) for b in items],
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages(total, page_size),
        )

    def get_by_slug(self, slug: str) -> BrandRead:
        brand = self.repo.get_by_slug(slug)
        if brand is None or not brand.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found")
        return self._to_read(brand)

    def update(self, brand_id: UUID, data: BrandUpdate) -> BrandRead:
        brand = self.repo.get_by_id(brand_id)
        if brand is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found")

        updates = data.model_dump(exclude_unset=True, exclude={"category_ids"})
        if "name" in updates and "slug" not in updates:
            updates["slug"] = self._unique_slug(updates["name"], exclude_id=brand.id)
        elif "slug" in updates and updates["slug"]:
            updates["slug"] = self._unique_slug(updates["slug"], exclude_id=brand.id)

        for key, value in updates.items():
            setattr(brand, key, value)

        if data.category_ids is not None:
            self._set_categories(brand, data.category_ids)

        self.repo.save(brand)
        self.db.commit()
        self.db.refresh(brand)
        return self._to_read(brand)

    def soft_delete(self, brand_id: UUID) -> BrandRead:
        brand = self.repo.get_by_id(brand_id)
        if brand is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found")
        if self.repo.count_active_products(brand_id) > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot deactivate brand with active products",
            )
        brand.is_active = False
        self.repo.save(brand)
        self.db.commit()
        self.db.refresh(brand)
        return self._to_read(brand)
