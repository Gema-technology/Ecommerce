from datetime import datetime
from math import ceil
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.inventory.models import (
    Inventory,
    InventoryMovement,
    MovementDirection,
    MovementType,
    ReservationStatus,
)
from app.modules.inventory.repository import InventoryRepository
from app.modules.inventory.schemas import (
    AdjustmentRequest,
    InventoryCreate,
    InventoryListResponse,
    InventoryMovementRead,
    InventoryOperationResponse,
    InventoryRead,
    InventoryThresholdUpdate,
    LocationBrief,
    LocationCreate,
    LocationListResponse,
    LocationRead,
    MovementListResponse,
    MovementRequest,
)
from app.modules.roles.models import User


class InventoryService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = InventoryRepository(db)

    def _to_inventory_read(self, item: Inventory) -> InventoryRead:
        return InventoryRead(
            id=item.id,
            product_id=item.product_id,
            product_name=item.product.name,
            product_sku=item.product.sku,
            location=LocationBrief.model_validate(item.location),
            quantity=item.quantity,
            reserved_quantity=item.reserved_quantity,
            available_quantity=item.available_quantity,
            reorder_point=item.reorder_point,
            reorder_quantity=item.reorder_quantity,
        )

    def _to_movement_read(self, movement: InventoryMovement) -> InventoryMovementRead:
        sign = 1 if movement.direction == MovementDirection.IN.value else -1
        return InventoryMovementRead(
            id=movement.id,
            inventory_id=movement.inventory_id,
            type=MovementType(movement.type),
            quantity=movement.quantity,
            direction=MovementDirection(movement.direction),
            signed_quantity=sign * movement.quantity,
            reference_type=movement.reference_type,
            reference_id=movement.reference_id,
            notes=movement.notes,
            created_by=movement.created_by,
            created_by_email=(
                movement.created_by_user.email if movement.created_by_user else None
            ),
            created_at=movement.created_at,
        )

    def _resolve_location_id(self, location_id: UUID | None) -> UUID:
        if location_id is not None:
            location = self.repo.get_location(location_id)
            if location is None or not location.is_active:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Location not found",
                )
            return location.id
        return self.repo.ensure_default_location().id

    def list_locations(self) -> list[LocationRead]:
        self.repo.ensure_default_location()
        self.db.commit()
        return [LocationRead.model_validate(loc) for loc in self.repo.list_locations()]

    def list_locations_paginated(
        self,
        *,
        q: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> LocationListResponse:
        from app.core.pagination import total_pages

        self.repo.ensure_default_location()
        self.db.commit()
        items, total = self.repo.list_locations_paginated(
            q=q, page=page, page_size=page_size
        )
        return LocationListResponse(
            items=[LocationRead.model_validate(loc) for loc in items],
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages(total, page_size),
        )

    def create_location(self, data: LocationCreate) -> LocationRead:
        from app.modules.inventory.models import Location

        location = Location(
            name=data.name,
            code=data.code,
            description=data.description,
            city=data.city,
            province=data.province,
            country=data.country,
            is_active=data.is_active,
        )
        self.db.add(location)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Location code already exists",
            ) from exc
        self.db.refresh(location)
        return LocationRead.model_validate(location)

    def create_inventory(self, data: InventoryCreate) -> InventoryRead:
        product = self.repo.get_product(data.product_id)
        if product is None or not product.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found",
            )
        location_id = self._resolve_location_id(data.location_id)
        existing = self.repo.get_by_product_location(data.product_id, location_id)
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Inventory already exists for this product and location",
            )
        inventory = Inventory(
            product_id=data.product_id,
            location_id=location_id,
            quantity=0,
            reserved_quantity=0,
            reorder_point=data.reorder_point,
            reorder_quantity=data.reorder_quantity,
        )
        self.repo.create_inventory(inventory)
        self.db.commit()
        loaded = self.repo.get_inventory(inventory.id)
        assert loaded is not None
        return self._to_inventory_read(loaded)

    def list_inventory(
        self,
        *,
        location_id: UUID | None = None,
        product_id: UUID | None = None,
        q: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> InventoryListResponse:
        from app.core.pagination import total_pages

        self.repo.ensure_default_location()
        items, total = self.repo.list_inventory(
            location_id=location_id,
            product_id=product_id,
            q=q,
            page=page,
            page_size=page_size,
        )
        return InventoryListResponse(
            items=[self._to_inventory_read(item) for item in items],
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages(total, page_size),
        )

    def get_product_inventory(
        self,
        product_id: UUID,
        *,
        location_id: UUID | None = None,
    ) -> InventoryRead:
        location_id = self._resolve_location_id(location_id)
        item = self.repo.get_by_product_location(product_id, location_id)
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Inventory not found",
            )
        return self._to_inventory_read(item)

    def update_thresholds(
        self,
        product_id: UUID,
        data: InventoryThresholdUpdate,
        *,
        location_id: UUID | None = None,
    ) -> InventoryRead:
        location_id = self._resolve_location_id(location_id)
        item = self.repo.get_by_product_location(product_id, location_id, for_update=True)
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Inventory not found",
            )
        updates = data.model_dump(exclude_unset=True)
        for key, value in updates.items():
            setattr(item, key, value)
        self.repo.save_inventory(item)
        self.db.commit()
        loaded = self.repo.get_by_product_location(product_id, location_id)
        assert loaded is not None
        return self._to_inventory_read(loaded)

    def list_low_stock(self, *, location_id: UUID | None = None) -> list[InventoryRead]:
        return [
            self._to_inventory_read(item)
            for item in self.repo.list_low_stock(location_id=location_id)
        ]

    def list_movements(
        self,
        product_id: UUID,
        *,
        location_id: UUID | None = None,
        movement_type: MovementType | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> MovementListResponse:
        rows, total = self.repo.list_movements(
            product_id=product_id,
            location_id=location_id,
            movement_type=movement_type.value if movement_type else None,
            page=page,
            page_size=page_size,
        )
        return MovementListResponse(
            items=[self._to_movement_read(row) for row in rows],
            page=page,
            page_size=page_size,
            total=total,
            total_pages=ceil(total / page_size) if total else 0,
        )

    def _get_locked_inventory(
        self,
        product_id: UUID,
        location_id: UUID | None,
        *,
        create_if_missing: bool = False,
    ) -> Inventory:
        resolved_location = self._resolve_location_id(location_id)
        item = self.repo.get_by_product_location(
            product_id, resolved_location, for_update=True
        )
        if item is None:
            if not create_if_missing:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Inventory not found",
                )
            product = self.repo.get_product(product_id)
            if product is None or not product.is_active:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Product not found",
                )
            item = Inventory(
                product_id=product_id,
                location_id=resolved_location,
                quantity=0,
                reserved_quantity=0,
                reorder_point=0,
                reorder_quantity=0,
            )
            self.repo.create_inventory(item)
            item = self.repo.get_by_product_location(
                product_id, resolved_location, for_update=True
            )
            assert item is not None
        return item

    def _apply_movement(
        self,
        *,
        product_id: UUID,
        user: User,
        movement_type: MovementType,
        quantity: int,
        direction: MovementDirection,
        location_id: UUID | None,
        reference_type: str | None,
        reference_id: str | None,
        notes: str | None,
        create_if_missing: bool = False,
        commit: bool = True,
    ) -> InventoryOperationResponse:
        if quantity <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="quantity must be positive",
            )

        inventory = self._get_locked_inventory(
            product_id,
            location_id,
            create_if_missing=create_if_missing,
        )

        if movement_type == MovementType.PURCHASE:
            inventory.quantity += quantity
        elif movement_type == MovementType.RETURN:
            inventory.quantity += quantity
        elif movement_type == MovementType.SALE:
            if quantity > inventory.available_quantity:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Insufficient available quantity",
                )
            inventory.quantity -= quantity
        elif movement_type == MovementType.DAMAGE:
            if quantity > inventory.quantity:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Insufficient on-hand quantity",
                )
            # Reduce on-hand; reserved must remain <= quantity
            if inventory.reserved_quantity > inventory.quantity - quantity:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Cannot damage stock below reserved quantity",
                )
            inventory.quantity -= quantity
        elif movement_type == MovementType.RESERVATION:
            if quantity > inventory.available_quantity:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Insufficient available quantity",
                )
            inventory.reserved_quantity += quantity
        elif movement_type == MovementType.RELEASE:
            if quantity > inventory.reserved_quantity:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Cannot release more than reserved",
                )
            inventory.reserved_quantity -= quantity
        elif movement_type == MovementType.ADJUSTMENT:
            if direction == MovementDirection.IN:
                inventory.quantity += quantity
            else:
                if quantity > inventory.quantity:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Adjustment would result in negative stock",
                    )
                if inventory.reserved_quantity > inventory.quantity - quantity:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Adjustment would leave reserved above on-hand",
                    )
                inventory.quantity -= quantity
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported movement type",
            )

        movement = InventoryMovement(
            inventory_id=inventory.id,
            type=movement_type.value,
            quantity=quantity,
            direction=direction.value,
            reference_type=reference_type,
            reference_id=reference_id,
            notes=notes,
            created_by=user.id,
        )
        self.repo.save_inventory(inventory)
        self.repo.create_movement(movement)
        if commit:
            self.db.commit()
            loaded = self.repo.get_inventory(inventory.id)
            assert loaded is not None
            self.db.refresh(movement)
            movement = self.db.get(InventoryMovement, movement.id)
            assert movement is not None
            return InventoryOperationResponse(
                inventory=self._to_inventory_read(loaded),
                movement=self._to_movement_read(movement),
            )

        self.db.flush()
        return InventoryOperationResponse(
            inventory=self._to_inventory_read(inventory),
            movement=self._to_movement_read(movement),
        )

    def purchase(
        self, product_id: UUID, data: MovementRequest, user: User
    ) -> InventoryOperationResponse:
        return self._apply_movement(
            product_id=product_id,
            user=user,
            movement_type=MovementType.PURCHASE,
            quantity=data.quantity,
            direction=MovementDirection.IN,
            location_id=data.location_id,
            reference_type=data.reference_type,
            reference_id=data.reference_id,
            notes=data.notes,
            create_if_missing=True,
        )

    def sale(
        self,
        product_id: UUID,
        data: MovementRequest,
        user: User,
        *,
        commit: bool = True,
    ) -> InventoryOperationResponse:
        return self._apply_movement(
            product_id=product_id,
            user=user,
            movement_type=MovementType.SALE,
            quantity=data.quantity,
            direction=MovementDirection.OUT,
            location_id=data.location_id,
            reference_type=data.reference_type,
            reference_id=data.reference_id,
            notes=data.notes,
            commit=commit,
        )

    def reserve(
        self,
        product_id: UUID,
        data: MovementRequest,
        user: User,
        *,
        commit: bool = True,
    ) -> InventoryOperationResponse:
        return self._apply_movement(
            product_id=product_id,
            user=user,
            movement_type=MovementType.RESERVATION,
            quantity=data.quantity,
            direction=MovementDirection.IN,
            location_id=data.location_id,
            reference_type=data.reference_type,
            reference_id=data.reference_id,
            notes=data.notes,
            commit=commit,
        )

    def release(
        self,
        product_id: UUID,
        data: MovementRequest,
        user: User,
        *,
        commit: bool = True,
    ) -> InventoryOperationResponse:
        return self._apply_movement(
            product_id=product_id,
            user=user,
            movement_type=MovementType.RELEASE,
            quantity=data.quantity,
            direction=MovementDirection.OUT,
            location_id=data.location_id,
            reference_type=data.reference_type,
            reference_id=data.reference_id,
            notes=data.notes,
            commit=commit,
        )

    def return_stock(
        self, product_id: UUID, data: MovementRequest, user: User
    ) -> InventoryOperationResponse:
        return self._apply_movement(
            product_id=product_id,
            user=user,
            movement_type=MovementType.RETURN,
            quantity=data.quantity,
            direction=MovementDirection.IN,
            location_id=data.location_id,
            reference_type=data.reference_type,
            reference_id=data.reference_id,
            notes=data.notes,
            create_if_missing=True,
        )

    def damage(
        self, product_id: UUID, data: MovementRequest, user: User
    ) -> InventoryOperationResponse:
        return self._apply_movement(
            product_id=product_id,
            user=user,
            movement_type=MovementType.DAMAGE,
            quantity=data.quantity,
            direction=MovementDirection.OUT,
            location_id=data.location_id,
            reference_type=data.reference_type,
            reference_id=data.reference_id,
            notes=data.notes,
        )

    def adjust(
        self, product_id: UUID, data: AdjustmentRequest, user: User
    ) -> InventoryOperationResponse:
        direction = (
            MovementDirection.IN if data.delta > 0 else MovementDirection.OUT
        )
        return self._apply_movement(
            product_id=product_id,
            user=user,
            movement_type=MovementType.ADJUSTMENT,
            quantity=abs(data.delta),
            direction=direction,
            location_id=data.location_id,
            reference_type=data.reference_type,
            reference_id=data.reference_id,
            notes=data.notes,
            create_if_missing=data.delta > 0,
        )

    def consume_for_order(
        self,
        order_id: UUID,
        user: User,
        *,
        commit: bool = True,
    ) -> list[InventoryOperationResponse]:
        """Consume ACTIVE reservations: decrease on-hand and reserved together."""
        from sqlalchemy import select

        from app.modules.inventory.models import InventoryReservation, ReservationStatus

        reservations = list(
            self.db.scalars(
                select(InventoryReservation)
                .where(
                    InventoryReservation.order_id == order_id,
                    InventoryReservation.status == ReservationStatus.ACTIVE.value,
                )
                .with_for_update()
            ).all()
        )
        results: list[InventoryOperationResponse] = []
        for reservation in reservations:
            # Resolve inventory after locking the reservation row (no OUTER JOIN + FOR UPDATE).
            inv_row = self.db.get(Inventory, reservation.inventory_id)
            if inv_row is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Inventory not found for reservation",
                )
            inventory = self.repo.get_by_product_location(
                inv_row.product_id,
                inv_row.location_id,
                for_update=True,
            )
            if inventory is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Inventory not found for reservation",
                )
            qty = reservation.quantity
            if qty > inventory.reserved_quantity or qty > inventory.quantity:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Cannot consume reservation: insufficient stock",
                )
            inventory.quantity -= qty
            inventory.reserved_quantity -= qty
            movement = InventoryMovement(
                inventory_id=inventory.id,
                type=MovementType.SALE.value,
                quantity=qty,
                direction=MovementDirection.OUT.value,
                reference_type="order",
                reference_id=str(order_id),
                notes="Payment success — reservation consumed",
                created_by=user.id,
            )
            self.repo.save_inventory(inventory)
            self.repo.create_movement(movement)
            reservation.status = ReservationStatus.CONSUMED.value
            self.db.flush()
            results.append(
                InventoryOperationResponse(
                    inventory=self._to_inventory_read(inventory),
                    movement=self._to_movement_read(movement),
                )
            )
        if commit:
            self.db.commit()
        return results

    def release_for_order(
        self,
        order_id: UUID,
        user: User,
        *,
        terminal_status: ReservationStatus = ReservationStatus.RELEASED,
        notes: str | None = None,
        commit: bool = True,
    ) -> list[InventoryOperationResponse]:
        """Release ACTIVE reservations for an order (idempotent if none remain).

        ``terminal_status`` must be RELEASED or EXPIRED. Confirm-on-pay uses
        ``consume_for_order`` (→ CONSUMED), not this method.
        """
        from sqlalchemy import select

        from app.modules.inventory.models import InventoryReservation

        if terminal_status not in {
            ReservationStatus.RELEASED,
            ReservationStatus.EXPIRED,
        }:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid reservation terminal status",
            )

        from sqlalchemy import update

        reservations = list(
            self.db.scalars(
                select(InventoryReservation)
                .where(
                    InventoryReservation.order_id == order_id,
                    InventoryReservation.status == ReservationStatus.ACTIVE.value,
                )
                .with_for_update()
            ).all()
        )
        results: list[InventoryOperationResponse] = []
        default_notes = (
            "Reservation expired"
            if terminal_status == ReservationStatus.EXPIRED
            else "Reservation released"
        )
        for reservation in reservations:
            # Claim ACTIVE→terminal atomically before mutating stock. FOR UPDATE alone is
            # insufficient on dialects that ignore row locks (e.g. SQLite in tests).
            claimed = self.db.execute(
                update(InventoryReservation)
                .where(
                    InventoryReservation.id == reservation.id,
                    InventoryReservation.status == ReservationStatus.ACTIVE.value,
                )
                .values(status=terminal_status.value)
            )
            if claimed.rowcount != 1:
                continue
            reservation.status = terminal_status.value

            inv_row = self.db.get(Inventory, reservation.inventory_id)
            if inv_row is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Inventory not found for reservation",
                )
            inventory = self.repo.get_by_product_location(
                inv_row.product_id,
                inv_row.location_id,
                for_update=True,
            )
            if inventory is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Inventory not found for reservation",
                )
            qty = reservation.quantity
            if qty > inventory.reserved_quantity:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Cannot release more than reserved",
                )
            inventory.reserved_quantity -= qty
            movement = InventoryMovement(
                inventory_id=inventory.id,
                type=MovementType.RELEASE.value,
                quantity=qty,
                direction=MovementDirection.OUT.value,
                reference_type="order",
                reference_id=str(order_id),
                notes=notes or default_notes,
                created_by=user.id,
            )
            self.repo.save_inventory(inventory)
            self.repo.create_movement(movement)
            self.db.flush()
            results.append(
                InventoryOperationResponse(
                    inventory=self._to_inventory_read(inventory),
                    movement=self._to_movement_read(movement),
                )
            )
        if commit:
            self.db.commit()
        return results

    def ensure_active_holds_for_order(
        self,
        order: "Order",  # noqa: F821
        user: User,
        *,
        commit: bool = False,
    ) -> None:
        """Re-create ACTIVE holds when a PENDING_PAYMENT order lost them (e.g. payment fail)."""
        from datetime import UTC, datetime, timedelta

        from sqlalchemy import func, select

        from app.core.config import settings
        from app.modules.inventory.models import InventoryReservation
        from app.modules.inventory.schemas import MovementRequest
        from app.modules.orders.models import OrderStatus

        if order.status != OrderStatus.PENDING_PAYMENT.value:
            return

        active_count = int(
            self.db.scalar(
                select(func.count())
                .select_from(InventoryReservation)
                .where(
                    InventoryReservation.order_id == order.id,
                    InventoryReservation.status == ReservationStatus.ACTIVE.value,
                )
            )
            or 0
        )
        if active_count > 0:
            return

        consumed_count = int(
            self.db.scalar(
                select(func.count())
                .select_from(InventoryReservation)
                .where(
                    InventoryReservation.order_id == order.id,
                    InventoryReservation.status == ReservationStatus.CONSUMED.value,
                )
            )
            or 0
        )
        if consumed_count > 0:
            return

        expires_at = datetime.now(UTC) + timedelta(hours=settings.reservation_ttl_hours)
        items = list(order.items or [])
        if not items:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Order has no items to reserve",
            )
        for item in items:
            op = self.reserve(
                item.product_id,
                MovementRequest(
                    quantity=item.quantity,
                    reference_type="order",
                    reference_id=str(order.id),
                    notes=f"Re-reserve after release for {order.order_number}",
                ),
                user,
                commit=False,
            )
            self.db.add(
                InventoryReservation(
                    inventory_id=op.inventory.id,
                    order_id=order.id,
                    quantity=item.quantity,
                    status=ReservationStatus.ACTIVE.value,
                    expires_at=expires_at,
                )
            )
        self.db.flush()
        if commit:
            self.db.commit()

    def _acquire_expire_job_lock(self) -> None:
        """Serialize expire jobs on PostgreSQL (no-op on SQLite / other dialects).

        Uses a transaction-scoped advisory lock so overlapping cron/sidecars wait
        instead of racing. Released automatically on commit or rollback.
        """
        from sqlalchemy import text

        bind = self.db.get_bind()
        if bind.dialect.name != "postgresql":
            return
        # Stable key for 'gema.expire_reservations' (32-bit signed).
        self.db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": 742_653_601})

    def expire_due_reservations(
        self,
        *,
        now: datetime | None = None,
        commit: bool = True,
    ) -> dict[str, int]:
        """Expire ACTIVE reservations past ``expires_at`` and cancel PENDING_PAYMENT orders.

        Safe to run repeatedly (cron / internal HTTP). Idempotent per reservation row.
        Concurrent callers are serialized via advisory lock (Postgres) + row FOR UPDATE.
        Expiry is driven by ``expires_at`` in the database — process restarts do not
        lose due work and do not require in-memory scheduling state.
        """
        from datetime import UTC
        from datetime import datetime as dt

        from sqlalchemy import select

        from app.modules.inventory.models import InventoryReservation
        from app.modules.orders.models import Order, OrderStatus

        self._acquire_expire_job_lock()

        moment = now or dt.now(UTC)
        due = list(
            self.db.scalars(
                select(InventoryReservation)
                .where(
                    InventoryReservation.status == ReservationStatus.ACTIVE.value,
                    InventoryReservation.expires_at.is_not(None),
                    InventoryReservation.expires_at <= moment,
                )
                .with_for_update()
            ).all()
        )
        order_ids = sorted({row.order_id for row in due}, key=str)
        expired_reservations = 0
        cancelled_orders = 0

        for order_id in order_ids:
            order = self.db.scalar(
                select(Order).where(Order.id == order_id).with_for_update()
            )
            if order is None:
                continue
            if order.status == OrderStatus.PAID.value:
                # Paid orders must already be CONSUMED; do not release stock.
                continue

            actor = order.user
            if actor is None:
                actor = self.db.get(User, order.user_id)
            if actor is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Order owner missing for reservation expiry",
                )

            released = self.release_for_order(
                order_id,
                actor,
                terminal_status=ReservationStatus.EXPIRED,
                notes="Reservation TTL expired",
                commit=False,
            )
            expired_reservations += len(released)

            # Claim cancel atomically so overlapping expire jobs don't double-count.
            if order.status == OrderStatus.PENDING_PAYMENT.value:
                from sqlalchemy import update

                cancelled = self.db.execute(
                    update(Order)
                    .where(
                        Order.id == order_id,
                        Order.status == OrderStatus.PENDING_PAYMENT.value,
                    )
                    .values(status=OrderStatus.CANCELLED.value)
                )
                if cancelled.rowcount == 1:
                    order.status = OrderStatus.CANCELLED.value
                    cancelled_orders += 1
                    self.db.flush()

        if commit:
            self.db.commit()
        return {
            "expired_reservations": expired_reservations,
            "cancelled_orders": cancelled_orders,
        }
