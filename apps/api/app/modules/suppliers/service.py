from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.modules.suppliers.models import Supplier, SupplierProduct
from app.modules.suppliers.repository import SupplierRepository
from app.core.pagination import total_pages
from app.modules.suppliers.schemas import (
    ProductSupplierItem,
    ProductSupplierLinkCreate,
    ProductSuppliersResponse,
    SupplierCreate,
    SupplierListResponse,
    SupplierProductCreate,
    SupplierProductRead,
    SupplierProductUpdate,
    SupplierRead,
    SupplierUpdate,
)


class SupplierService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = SupplierRepository(db)

    def create(self, data: SupplierCreate) -> SupplierRead:
        if self.repo.tax_id_exists(data.tax_id, data.tax_id_type.value):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Supplier with this tax_id and tax_id_type already exists",
            )
        supplier = Supplier(
            business_name=data.business_name,
            commercial_name=data.commercial_name,
            tax_id=data.tax_id,
            tax_id_type=data.tax_id_type.value,
            email=data.email,
            phone=data.phone,
            website_url=data.website_url,
            address=data.address,
            city=data.city,
            province=data.province,
            country=data.country,
            contact_name=data.contact_name,
            notes=data.notes,
            is_active=data.is_active,
        )
        self.repo.create(supplier)
        self.db.commit()
        self.db.refresh(supplier)
        return SupplierRead.model_validate(supplier)

    def list_suppliers(
        self,
        *,
        active_only: bool | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> SupplierListResponse:
        items, total = self.repo.list_all(
            active_only=active_only,
            search=search,
            page=page,
            page_size=page_size,
        )
        return SupplierListResponse(
            items=[SupplierRead.model_validate(s) for s in items],
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages(total, page_size),
        )

    def get_by_id(self, supplier_id: UUID) -> SupplierRead:
        supplier = self.repo.get_by_id(supplier_id)
        if supplier is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
        return SupplierRead.model_validate(supplier)

    def update(self, supplier_id: UUID, data: SupplierUpdate) -> SupplierRead:
        supplier = self.repo.get_by_id(supplier_id)
        if supplier is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")

        updates = data.model_dump(exclude_unset=True)
        if "tax_id_type" in updates and updates["tax_id_type"] is not None:
            updates["tax_id_type"] = updates["tax_id_type"].value

        tax_id = updates.get("tax_id", supplier.tax_id)
        tax_id_type = updates.get("tax_id_type", supplier.tax_id_type)
        if self.repo.tax_id_exists(tax_id, tax_id_type, exclude_id=supplier.id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Supplier with this tax_id and tax_id_type already exists",
            )

        for key, value in updates.items():
            setattr(supplier, key, value)

        self.repo.save(supplier)
        self.db.commit()
        self.db.refresh(supplier)
        return SupplierRead.model_validate(supplier)

    def soft_delete(self, supplier_id: UUID) -> SupplierRead:
        supplier = self.repo.get_by_id(supplier_id)
        if supplier is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
        supplier.is_active = False
        self.repo.save(supplier)
        self.db.commit()
        self.db.refresh(supplier)
        return SupplierRead.model_validate(supplier)

    def _to_supplier_product_read(self, item: SupplierProduct) -> SupplierProductRead:
        data = SupplierProductRead.model_validate(item)
        if item.product is not None:
            data.product_name = item.product.name
            data.product_sku = item.product.sku
        return data

    def create_supplier_product(
        self,
        supplier_id: UUID,
        data: SupplierProductCreate,
    ) -> SupplierProductRead:
        supplier = self.repo.get_by_id(supplier_id)
        if supplier is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
        if not supplier.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot create supplier product for inactive supplier",
            )

        product = self.repo.get_product(data.product_id)
        if product is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
        if not product.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot create supplier product for inactive product",
            )

        if self.repo.get_supplier_product_by_pair(supplier_id, data.product_id) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Supplier already linked to this product",
            )

        item = SupplierProduct(
            supplier_id=supplier_id,
            product_id=data.product_id,
            supplier_sku=data.supplier_sku,
            supplier_product_name=data.supplier_product_name,
            cost=Decimal(data.cost),
            currency=data.currency.value,
            availability=data.availability.value,
            lead_time_days=data.lead_time_days,
            minimum_order_quantity=data.minimum_order_quantity,
            supplier_url=data.supplier_url,
            last_checked_at=datetime.now(UTC),
            is_active=data.is_active,
        )
        self.repo.create_supplier_product(item)
        self.db.commit()
        item = self.repo.get_supplier_product(supplier_id, item.id)
        assert item is not None
        return self._to_supplier_product_read(item)

    def list_supplier_products(
        self,
        supplier_id: UUID,
        *,
        active_only: bool | None = None,
    ) -> list[SupplierProductRead]:
        if self.repo.get_by_id(supplier_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")
        return [
            self._to_supplier_product_read(item)
            for item in self.repo.list_supplier_products(supplier_id, active_only=active_only)
        ]

    def update_supplier_product(
        self,
        supplier_id: UUID,
        supplier_product_id: UUID,
        data: SupplierProductUpdate,
    ) -> SupplierProductRead:
        item = self.repo.get_supplier_product(supplier_id, supplier_product_id)
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Supplier product not found",
            )

        updates = data.model_dump(exclude_unset=True)
        mark_checked = updates.pop("mark_checked", False)
        if "currency" in updates and updates["currency"] is not None:
            updates["currency"] = updates["currency"].value
        if "availability" in updates and updates["availability"] is not None:
            updates["availability"] = updates["availability"].value
        if "cost" in updates and updates["cost"] is not None:
            updates["cost"] = Decimal(updates["cost"])

        checked_fields = {
            "supplier_sku",
            "supplier_product_name",
            "cost",
            "currency",
            "availability",
            "lead_time_days",
            "minimum_order_quantity",
            "supplier_url",
        }
        should_touch_checked = mark_checked or bool(checked_fields.intersection(updates))

        for key, value in updates.items():
            setattr(item, key, value)

        if should_touch_checked:
            item.last_checked_at = datetime.now(UTC)

        self.repo.save_supplier_product(item)
        self.db.commit()
        item = self.repo.get_supplier_product(supplier_id, supplier_product_id)
        assert item is not None
        return self._to_supplier_product_read(item)

    def soft_delete_supplier_product(
        self,
        supplier_id: UUID,
        supplier_product_id: UUID,
    ) -> SupplierProductRead:
        item = self.repo.get_supplier_product(supplier_id, supplier_product_id)
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Supplier product not found",
            )
        item.is_active = False
        self.repo.save_supplier_product(item)
        self.db.commit()
        item = self.repo.get_supplier_product(supplier_id, supplier_product_id)
        assert item is not None
        return self._to_supplier_product_read(item)

    def list_product_suppliers(self, product_id: UUID) -> ProductSuppliersResponse:
        product = self.repo.get_product(product_id)
        if product is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

        items = self.repo.list_product_suppliers(product_id)
        return ProductSuppliersResponse(
            product={"id": str(product.id), "name": product.name, "sku": product.sku},
            suppliers=[
                ProductSupplierItem(
                    supplier_product_id=item.id,
                    supplier_id=item.supplier_id,
                    supplier_name=item.supplier.commercial_name or item.supplier.business_name,
                    supplier_sku=item.supplier_sku,
                    cost=item.cost,
                    currency=item.currency,
                    availability=item.availability,
                    lead_time_days=item.lead_time_days,
                    minimum_order_quantity=item.minimum_order_quantity,
                    supplier_url=item.supplier_url,
                    last_checked_at=item.last_checked_at,
                    is_active=item.is_active,
                )
                for item in items
            ],
        )

    def link_product_supplier(
        self,
        product_id: UUID,
        data: ProductSupplierLinkCreate,
    ) -> SupplierProductRead:
        return self.create_supplier_product(
            data.supplier_id,
            SupplierProductCreate(
                product_id=product_id,
                supplier_sku=data.supplier_sku,
                supplier_product_name=data.supplier_product_name,
                cost=data.cost,
                currency=data.currency,
                availability=data.availability,
                lead_time_days=data.lead_time_days,
                minimum_order_quantity=data.minimum_order_quantity,
                supplier_url=data.supplier_url,
                is_active=data.is_active,
            ),
        )
