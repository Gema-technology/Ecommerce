from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.modules.catalog.models import Product
from app.modules.inventory.models import Inventory, InventoryMovement, Location


DEFAULT_LOCATION_CODE = "MAIN"


class InventoryRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def ensure_default_location(self) -> Location:
        location = self.db.scalar(
            select(Location).where(Location.code == DEFAULT_LOCATION_CODE)
        )
        if location is not None:
            return location
        location = Location(
            name="Bodega Principal",
            code=DEFAULT_LOCATION_CODE,
            description="Ubicación principal de desarrollo",
            city="Ibarra",
            province="Imbabura",
            country="Ecuador",
            is_active=True,
        )
        self.db.add(location)
        self.db.flush()
        return location

    def list_locations(self, *, active_only: bool = True) -> list[Location]:
        stmt = select(Location).order_by(Location.name)
        if active_only:
            stmt = stmt.where(Location.is_active.is_(True))
        return list(self.db.scalars(stmt).all())

    def get_location(self, location_id: UUID) -> Location | None:
        return self.db.get(Location, location_id)

    def get_product(self, product_id: UUID) -> Product | None:
        return self.db.get(Product, product_id)

    def get_inventory(self, inventory_id: UUID) -> Inventory | None:
        return self.db.scalar(
            select(Inventory)
            .options(joinedload(Inventory.product), joinedload(Inventory.location))
            .where(Inventory.id == inventory_id)
        )

    def get_by_product_location(
        self,
        product_id: UUID,
        location_id: UUID,
        *,
        for_update: bool = False,
    ) -> Inventory | None:
        # PostgreSQL rejects FOR UPDATE on the nullable side of an OUTER JOIN.
        # Lock the inventory row alone, then load relationships in a second query.
        if for_update:
            locked = self.db.scalar(
                select(Inventory)
                .where(
                    Inventory.product_id == product_id,
                    Inventory.location_id == location_id,
                )
                .with_for_update()
            )
            if locked is None:
                return None
            return self.db.scalar(
                select(Inventory)
                .options(joinedload(Inventory.product), joinedload(Inventory.location))
                .where(Inventory.id == locked.id)
            )

        return self.db.scalar(
            select(Inventory)
            .options(joinedload(Inventory.product), joinedload(Inventory.location))
            .where(
                Inventory.product_id == product_id,
                Inventory.location_id == location_id,
            )
        )

    def list_inventory(
        self,
        *,
        location_id: UUID | None = None,
        product_id: UUID | None = None,
        q: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Inventory], int]:
        from sqlalchemy import func, or_

        from app.core.pagination import offset_for
        from app.modules.catalog.models import Product

        stmt = (
            select(Inventory)
            .options(joinedload(Inventory.product), joinedload(Inventory.location))
            .order_by(Inventory.updated_at.desc())
        )
        count_stmt = select(func.count()).select_from(Inventory)
        if location_id is not None:
            stmt = stmt.where(Inventory.location_id == location_id)
            count_stmt = count_stmt.where(Inventory.location_id == location_id)
        if product_id is not None:
            stmt = stmt.where(Inventory.product_id == product_id)
            count_stmt = count_stmt.where(Inventory.product_id == product_id)
        if q:
            term = f"%{q.strip()}%"
            stmt = stmt.join(Product, Product.id == Inventory.product_id).where(
                or_(Product.name.ilike(term), Product.sku.ilike(term))
            )
            count_stmt = count_stmt.join(
                Product, Product.id == Inventory.product_id
            ).where(or_(Product.name.ilike(term), Product.sku.ilike(term)))
        total = int(self.db.scalar(count_stmt) or 0)
        items = list(
            self.db.scalars(
                stmt.offset(offset_for(page, page_size)).limit(page_size)
            )
            .unique()
            .all()
        )
        return items, total

    def list_low_stock(self, *, location_id: UUID | None = None) -> list[Inventory]:
        items, _ = self.list_inventory(
            location_id=location_id, page=1, page_size=10_000
        )
        return [item for item in items if item.available_quantity <= item.reorder_point]

    def list_locations_paginated(
        self,
        *,
        q: str | None = None,
        page: int = 1,
        page_size: int = 20,
        active_only: bool = True,
    ) -> tuple[list[Location], int]:
        from sqlalchemy import func, or_

        from app.core.pagination import offset_for

        stmt = select(Location).order_by(Location.name)
        count_stmt = select(func.count()).select_from(Location)
        if active_only:
            stmt = stmt.where(Location.is_active.is_(True))
            count_stmt = count_stmt.where(Location.is_active.is_(True))
        if q:
            term = f"%{q.strip()}%"
            filt = or_(
                Location.name.ilike(term),
                Location.code.ilike(term),
                Location.city.ilike(term),
            )
            stmt = stmt.where(filt)
            count_stmt = count_stmt.where(filt)
        total = int(self.db.scalar(count_stmt) or 0)
        items = list(
            self.db.scalars(
                stmt.offset(offset_for(page, page_size)).limit(page_size)
            ).all()
        )
        return items, total

    def create_inventory(self, inventory: Inventory) -> Inventory:
        self.db.add(inventory)
        self.db.flush()
        return inventory

    def save_inventory(self, inventory: Inventory) -> Inventory:
        self.db.add(inventory)
        self.db.flush()
        return inventory

    def create_movement(self, movement: InventoryMovement) -> InventoryMovement:
        self.db.add(movement)
        self.db.flush()
        return movement

    def list_movements(
        self,
        *,
        product_id: UUID,
        location_id: UUID | None = None,
        movement_type: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[InventoryMovement], int]:
        stmt = (
            select(InventoryMovement)
            .join(Inventory)
            .options(
                joinedload(InventoryMovement.created_by_user),
                joinedload(InventoryMovement.inventory),
            )
            .where(Inventory.product_id == product_id)
            .order_by(InventoryMovement.created_at.desc())
        )
        if location_id is not None:
            stmt = stmt.where(Inventory.location_id == location_id)
        if movement_type is not None:
            stmt = stmt.where(InventoryMovement.type == movement_type)

        count_stmt = (
            select(func.count())
            .select_from(InventoryMovement)
            .join(Inventory)
            .where(Inventory.product_id == product_id)
        )
        if location_id is not None:
            count_stmt = count_stmt.where(Inventory.location_id == location_id)
        if movement_type is not None:
            count_stmt = count_stmt.where(InventoryMovement.type == movement_type)

        total = int(self.db.scalar(count_stmt) or 0)
        rows = list(
            self.db.scalars(stmt.offset((page - 1) * page_size).limit(page_size))
            .unique()
            .all()
        )
        return rows, total
