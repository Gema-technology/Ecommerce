from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.core.pagination import offset_for
from app.modules.catalog.models import Product
from app.modules.suppliers.models import Supplier, SupplierProduct


class SupplierRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, supplier_id: UUID) -> Supplier | None:
        return self.db.get(Supplier, supplier_id)

    def list_all(
        self,
        *,
        active_only: bool | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Supplier], int]:
        filters = []
        if active_only is True:
            filters.append(Supplier.is_active.is_(True))
        elif active_only is False:
            filters.append(Supplier.is_active.is_(False))
        if search:
            term = f"%{search.strip()}%"
            filters.append(
                or_(
                    Supplier.business_name.ilike(term),
                    Supplier.commercial_name.ilike(term),
                    Supplier.tax_id.ilike(term),
                )
            )
        count_stmt = select(func.count()).select_from(Supplier)
        stmt = select(Supplier).order_by(Supplier.business_name)
        for f in filters:
            count_stmt = count_stmt.where(f)
            stmt = stmt.where(f)
        total = int(self.db.scalar(count_stmt) or 0)
        items = list(
            self.db.scalars(
                stmt.offset(offset_for(page, page_size)).limit(page_size)
            ).all()
        )
        return items, total

    def create(self, supplier: Supplier) -> Supplier:
        self.db.add(supplier)
        self.db.flush()
        return supplier

    def save(self, supplier: Supplier) -> Supplier:
        self.db.add(supplier)
        self.db.flush()
        return supplier

    def tax_id_exists(
        self,
        tax_id: str,
        tax_id_type: str,
        *,
        exclude_id: UUID | None = None,
    ) -> bool:
        stmt = select(Supplier.id).where(
            Supplier.tax_id == tax_id,
            Supplier.tax_id_type == tax_id_type,
        )
        if exclude_id is not None:
            stmt = stmt.where(Supplier.id != exclude_id)
        return self.db.scalar(stmt) is not None

    def get_product(self, product_id: UUID) -> Product | None:
        return self.db.get(Product, product_id)

    def get_supplier_product(
        self,
        supplier_id: UUID,
        supplier_product_id: UUID,
    ) -> SupplierProduct | None:
        return self.db.scalar(
            select(SupplierProduct)
            .options(joinedload(SupplierProduct.product))
            .where(
                SupplierProduct.id == supplier_product_id,
                SupplierProduct.supplier_id == supplier_id,
            )
        )

    def get_supplier_product_by_pair(
        self,
        supplier_id: UUID,
        product_id: UUID,
    ) -> SupplierProduct | None:
        return self.db.scalar(
            select(SupplierProduct).where(
                SupplierProduct.supplier_id == supplier_id,
                SupplierProduct.product_id == product_id,
            )
        )

    def list_supplier_products(
        self,
        supplier_id: UUID,
        *,
        active_only: bool | None = None,
    ) -> list[SupplierProduct]:
        stmt = (
            select(SupplierProduct)
            .options(joinedload(SupplierProduct.product))
            .where(SupplierProduct.supplier_id == supplier_id)
            .order_by(SupplierProduct.created_at.desc())
        )
        if active_only is True:
            stmt = stmt.where(SupplierProduct.is_active.is_(True))
        return list(self.db.scalars(stmt).unique().all())

    def list_product_suppliers(
        self,
        product_id: UUID,
        *,
        active_only: bool | None = None,
    ) -> list[SupplierProduct]:
        stmt = (
            select(SupplierProduct)
            .options(joinedload(SupplierProduct.supplier))
            .where(SupplierProduct.product_id == product_id)
            .order_by(SupplierProduct.cost.asc())
        )
        if active_only is True:
            stmt = stmt.where(SupplierProduct.is_active.is_(True))
        return list(self.db.scalars(stmt).unique().all())

    def create_supplier_product(self, item: SupplierProduct) -> SupplierProduct:
        self.db.add(item)
        self.db.flush()
        return item

    def save_supplier_product(self, item: SupplierProduct) -> SupplierProduct:
        self.db.add(item)
        self.db.flush()
        return item
