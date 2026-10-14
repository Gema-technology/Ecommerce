from decimal import Decimal
from math import ceil
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.modules.brands.repository import BrandRepository
from app.modules.catalog.models import Product, ProductImage
from app.modules.categories.repository import CategoryRepository
from app.modules.inventory.models import Inventory
from app.modules.inventory.repository import DEFAULT_LOCATION_CODE
from app.modules.pricing.schemas import PublicPrice
from app.modules.pricing.service import PricingService
from app.modules.products.repository import ProductRepository
from app.modules.products.schemas import (
    AvailabilityStatus,
    ProductCreate,
    ProductImageInput,
    ProductListResponse,
    ProductRead,
    ProductSort,
    ProductUpdate,
)
from app.shared.slug import slugify


class ProductService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = ProductRepository(db)
        self.brands = BrandRepository(db)
        self.categories = CategoryRepository(db)
        self.pricing = PricingService(db)

    def _unique_slug(self, base: str, *, exclude_id: UUID | None = None) -> str:
        candidate = slugify(base)
        if not self.repo.slug_exists(candidate, exclude_id=exclude_id):
            return candidate
        counter = 2
        while self.repo.slug_exists(f"{candidate}-{counter}", exclude_id=exclude_id):
            counter += 1
        return f"{candidate}-{counter}"

    def _ensure_brand(self, brand_id: UUID) -> None:
        brand = self.brands.get_by_id(brand_id)
        if brand is None or not brand.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Brand not found",
            )

    def _ensure_category(self, category_id: UUID) -> None:
        category = self.categories.get_by_id(category_id)
        if category is None or not category.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Category not found",
            )

    def _ensure_brand_category_affinity(self, brand_id: UUID, category_id: UUID) -> None:
        brand = self.brands.get_by_id(brand_id)
        if brand is None or not brand.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Brand not found",
            )
        if not self.brands.allows_category(brand, category_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Brand not allowed for this category",
            )

    def _build_images(self, images: list[ProductImageInput]) -> list[ProductImage]:
        if not images:
            return []
        primary_count = sum(1 for img in images if img.is_primary)
        result: list[ProductImage] = []
        for index, img in enumerate(images):
            is_primary = img.is_primary if primary_count > 0 else index == 0
            if primary_count > 1 and img.is_primary and any(r.is_primary for r in result):
                is_primary = False
            result.append(
                ProductImage(
                    url=img.url,
                    alt_text=img.alt_text,
                    sort_order=img.sort_order if img.sort_order else index,
                    is_primary=is_primary,
                )
            )
        if result and not any(i.is_primary for i in result):
            result[0].is_primary = True
        return result

    @staticmethod
    def _status_from_inventory(inv: Inventory | None) -> AvailabilityStatus:
        if inv is None:
            return AvailabilityStatus.UNKNOWN
        available = inv.quantity - inv.reserved_quantity
        if available <= 0:
            return AvailabilityStatus.OUT_OF_STOCK
        if available <= inv.reorder_point:
            return AvailabilityStatus.LOW_STOCK
        return AvailabilityStatus.IN_STOCK

    def map_availability(
        self, product_ids: list[UUID]
    ) -> dict[UUID, AvailabilityStatus]:
        if not product_ids:
            return {}
        rows = list(
            self.db.scalars(
                select(Inventory)
                .options(joinedload(Inventory.location))
                .where(Inventory.product_id.in_(product_ids))
            ).unique().all()
        )
        by_product: dict[UUID, list[Inventory]] = {pid: [] for pid in product_ids}
        for row in rows:
            by_product[row.product_id].append(row)

        result: dict[UUID, AvailabilityStatus] = {}
        for pid, inventories in by_product.items():
            if not inventories:
                result[pid] = AvailabilityStatus.UNKNOWN
                continue
            main = next(
                (
                    i
                    for i in inventories
                    if i.location and i.location.code == DEFAULT_LOCATION_CODE
                ),
                inventories[0],
            )
            result[pid] = self._status_from_inventory(main)
        return result

    def _to_read(
        self,
        product: Product,
        price: PublicPrice | None = None,
        availability: AvailabilityStatus = AvailabilityStatus.UNKNOWN,
    ) -> ProductRead:
        data = ProductRead.model_validate(product)
        data.price = price
        data.availability = availability
        return data

    def _attach_public_fields(self, products: list[Product]) -> list[ProductRead]:
        ids = [p.id for p in products]
        price_map = self.pricing.map_public_prices(ids)
        avail_map = self.map_availability(ids)
        return [
            self._to_read(
                p,
                price_map.get(p.id),
                avail_map.get(p.id, AvailabilityStatus.UNKNOWN),
            )
            for p in products
        ]

    def create(self, data: ProductCreate) -> ProductRead:
        if self.repo.sku_exists(data.sku):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="SKU already exists",
            )
        self._ensure_brand(data.brand_id)
        self._ensure_category(data.category_id)
        self._ensure_brand_category_affinity(data.brand_id, data.category_id)

        slug = self._unique_slug(data.slug or data.name)
        product = Product(
            sku=data.sku,
            name=data.name,
            slug=slug,
            short_description=data.short_description,
            description=data.description,
            model=data.model,
            brand_id=data.brand_id,
            category_id=data.category_id,
            specifications=data.specifications or {},
            weight=data.weight,
            warranty_months=data.warranty_months,
            is_active=data.is_active,
        )
        self.repo.create(product)
        for image in self._build_images(data.images):
            image.product_id = product.id
            product.images.append(image)
        self.db.commit()
        loaded = self.repo.get_by_id(product.id)
        assert loaded is not None
        return self._to_read(loaded)

    def list_products(
        self,
        *,
        category: str | None = None,
        brand: str | None = None,
        is_active: bool | None = True,
        min_price: Decimal | None = None,
        max_price: Decimal | None = None,
        search: str | None = None,
        sort: ProductSort = ProductSort.NEWEST,
        page: int = 1,
        page_size: int = 20,
    ) -> ProductListResponse:
        page = max(page, 1)
        page_size = min(max(page_size, 1), 100)
        items, total = self.repo.list_filtered(
            category_slug=category,
            brand_slug=brand,
            is_active=is_active,
            min_price=min_price,
            max_price=max_price,
            search=search,
            sort=sort,
            page=page,
            page_size=page_size,
        )
        return ProductListResponse(
            items=self._attach_public_fields(items),
            page=page,
            page_size=page_size,
            total=total,
            total_pages=ceil(total / page_size) if total else 0,
        )

    def get_by_slug(self, slug: str) -> ProductRead:
        product = self.repo.get_by_slug(slug)
        if product is None or not product.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
        return self._attach_public_fields([product])[0]

    def update(self, product_id: UUID, data: ProductUpdate) -> ProductRead:
        product = self.repo.get_by_id(product_id)
        if product is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

        updates = data.model_dump(exclude_unset=True, exclude={"images"})
        if "brand_id" in updates:
            self._ensure_brand(updates["brand_id"])
        if "category_id" in updates:
            self._ensure_category(updates["category_id"])
        next_brand_id = updates.get("brand_id", product.brand_id)
        next_category_id = updates.get("category_id", product.category_id)
        if "brand_id" in updates or "category_id" in updates:
            self._ensure_brand_category_affinity(next_brand_id, next_category_id)
        if "name" in updates and "slug" not in updates:
            updates["slug"] = self._unique_slug(updates["name"], exclude_id=product.id)
        elif "slug" in updates and updates["slug"]:
            updates["slug"] = self._unique_slug(updates["slug"], exclude_id=product.id)

        for key, value in updates.items():
            setattr(product, key, value)

        if data.images is not None:
            self.repo.replace_images(product, self._build_images(data.images))

        self.repo.save(product)
        self.db.commit()
        loaded = self.repo.get_by_id(product.id)
        assert loaded is not None
        return self._attach_public_fields([loaded])[0]

    def soft_delete(self, product_id: UUID) -> ProductRead:
        product = self.repo.get_by_id(product_id)
        if product is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
        product.is_active = False
        self.repo.save(product)
        self.db.commit()
        loaded = self.repo.get_by_id(product.id)
        assert loaded is not None
        return self._to_read(loaded)
