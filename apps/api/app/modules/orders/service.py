from math import ceil
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.modules.inventory.models import InventoryReservation, ReservationStatus
from app.modules.inventory.service import InventoryService
from app.modules.notifications.service import (
    EVENT_ORDER_SHIPPED,
    notify_order_event,
)
from app.modules.orders.models import Order, OrderStatus, OrderStatusEvent
from app.modules.orders.repository import OrderRepository
from app.modules.orders.schemas import (
    OrderItemRead,
    OrderListResponse,
    OrderRead,
    OrderReservationRead,
    OrderStatusEventRead,
    OrderStatusUpdateRequest,
    ShippingAddress,
)
from app.modules.orders.transitions import (
    allowed_transitions_for,
    is_valid_fulfillment_transition,
)
from app.modules.roles.models import User


class OrderService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = OrderRepository(db)
        self.inventory = InventoryService(db)

    def _load_reservations(self, order_id: UUID) -> list[OrderReservationRead]:
        rows = list(
            self.db.scalars(
                select(InventoryReservation)
                .options(joinedload(InventoryReservation.inventory))
                .where(InventoryReservation.order_id == order_id)
            )
            .unique()
            .all()
        )
        return [
            OrderReservationRead(
                id=r.id,
                inventory_id=r.inventory_id,
                product_id=r.inventory.product_id if r.inventory else None,
                quantity=r.quantity,
                status=r.status,
                expires_at=r.expires_at,
                created_at=r.created_at,
            )
            for r in rows
        ]

    def _load_history(self, order_id: UUID) -> list[OrderStatusEventRead]:
        rows = list(
            self.db.scalars(
                select(OrderStatusEvent)
                .where(OrderStatusEvent.order_id == order_id)
                .order_by(OrderStatusEvent.created_at.asc())
            ).all()
        )
        return [OrderStatusEventRead.model_validate(r) for r in rows]

    def _record_status_event(
        self,
        order: Order,
        *,
        from_status: str,
        to_status: str,
        actor: User | None,
        note: str | None = None,
    ) -> None:
        self.db.add(
            OrderStatusEvent(
                order_id=order.id,
                from_status=from_status,
                to_status=to_status,
                actor_user_id=actor.id if actor is not None else None,
                note=note,
            )
        )

    def _to_read(
        self,
        order: Order,
        *,
        include_customer: bool = False,
        include_reservations: bool = False,
        include_history: bool = False,
    ) -> OrderRead:
        shipping = None
        if order.shipping_address:
            shipping = ShippingAddress.model_validate(order.shipping_address)

        reservations: list[OrderReservationRead] = []
        if include_reservations:
            reservations = self._load_reservations(order.id)

        reserved_until = None
        active_expiries = [
            r.expires_at
            for r in reservations
            if r.status == ReservationStatus.ACTIVE.value and r.expires_at is not None
        ]
        if active_expiries:
            reserved_until = min(active_expiries)

        history: list[OrderStatusEventRead] = []
        if include_history:
            history = self._load_history(order.id)

        data = OrderRead(
            id=order.id,
            order_number=order.order_number,
            status=order.status,
            currency=order.currency,
            subtotal=order.subtotal,
            tax_total=order.tax_total,
            shipping_total=order.shipping_total,
            discount_total=order.discount_total,
            total=order.total,
            customer_email=order.customer_email,
            customer_name=order.customer_name,
            customer_phone=order.customer_phone,
            buyer_id_type=order.buyer_id_type,
            buyer_id_number=order.buyer_id_number,
            shipping_address=shipping,
            customer_notes=order.customer_notes,
            reserved_until=reserved_until,
            created_at=order.created_at,
            updated_at=order.updated_at,
            items=[OrderItemRead.model_validate(i) for i in order.items],
            reservations=reservations,
            allowed_transitions=allowed_transitions_for(order.status),
            status_history=history,
        )
        if include_customer:
            if not data.customer_email and order.user is not None:
                data.customer_email = order.user.email
            if not data.customer_name and order.user is not None:
                data.customer_name = (
                    f"{order.user.first_name} {order.user.last_name}".strip()
                )
            if not data.customer_phone and order.user is not None:
                data.customer_phone = order.user.phone
        return data

    def get_for_user(self, user: User, order_id: UUID) -> OrderRead:
        order = self.repo.get_by_id(order_id)
        if order is None or order.user_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
        return self._to_read(order, include_reservations=True)

    def get_by_number_for_user(self, user: User, order_number: str) -> OrderRead:
        order = self.repo.get_by_number(order_number)
        if order is None or order.user_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
        return self._to_read(order, include_reservations=True)

    def list_for_user(
        self, user: User, *, page: int = 1, page_size: int = 20
    ) -> OrderListResponse:
        items, total = self.repo.list_for_user(user.id, page=page, page_size=page_size)
        total_pages = ceil(total / page_size) if page_size else 0
        return OrderListResponse(
            items=[self._to_read(o, include_reservations=True) for o in items],
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
        )

    def cancel_for_user(self, user: User, order_id: UUID) -> OrderRead:
        try:
            return self._cancel_pending(order_id, actor=user, require_owner=True)
        except Exception:
            self.db.rollback()
            raise

    def admin_cancel(self, order_id: UUID, admin: User) -> OrderRead:
        try:
            return self._cancel_pending(order_id, actor=admin, require_owner=False)
        except Exception:
            self.db.rollback()
            raise

    def _cancel_pending(
        self,
        order_id: UUID,
        *,
        actor: User,
        require_owner: bool,
    ) -> OrderRead:
        order = self.db.scalar(
            select(Order).where(Order.id == order_id).with_for_update()
        )
        if order is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
        if require_owner and order.user_id != actor.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
        if order.status == OrderStatus.CANCELLED.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Order is already cancelled",
            )
        if order.status != OrderStatus.PENDING_PAYMENT.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only pending payment orders can be cancelled",
            )

        previous = order.status
        order.status = OrderStatus.CANCELLED.value
        self._record_status_event(
            order,
            from_status=previous,
            to_status=OrderStatus.CANCELLED.value,
            actor=actor,
            note="Cancelled while pending payment",
        )
        self.inventory.release_for_order(
            order.id,
            actor,
            terminal_status=ReservationStatus.RELEASED,
            notes="Order cancelled — reservation released",
            commit=False,
        )
        self.db.commit()
        loaded = self.repo.get_by_id(order.id)
        assert loaded is not None
        return self._to_read(
            loaded,
            include_customer=not require_owner,
            include_reservations=True,
            include_history=not require_owner,
        )

    def admin_update_status(
        self,
        order_id: UUID,
        admin: User,
        payload: OrderStatusUpdateRequest,
    ) -> OrderRead:
        """Admin-only forward fulfillment. Does not touch payment records."""
        target = payload.status
        try:
            order = self.db.scalar(
                select(Order).where(Order.id == order_id).with_for_update()
            )
            if order is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Order not found"
                )

            # Idempotent: already at target → no duplicate side effects.
            if order.status == target:
                self.db.commit()
                loaded = self.repo.get_by_id(order.id)
                assert loaded is not None
                return self._to_read(
                    loaded,
                    include_customer=True,
                    include_reservations=True,
                    include_history=True,
                )

            if not is_valid_fulfillment_transition(order.status, target):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Invalid transition from {order.status} to {target}. "
                        f"Allowed: {allowed_transitions_for(order.status) or 'none'}"
                    ),
                )

            previous = order.status
            order.status = target
            self._record_status_event(
                order,
                from_status=previous,
                to_status=target,
                actor=admin,
                note=payload.note,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        if target == OrderStatus.SHIPPED.value:
            notify_order_event(self.db, order_id, EVENT_ORDER_SHIPPED)

        loaded = self.repo.get_by_id(order_id)
        assert loaded is not None
        return self._to_read(
            loaded,
            include_customer=True,
            include_reservations=True,
            include_history=True,
        )

    def admin_get(self, order_id: UUID) -> OrderRead:
        order = self.repo.get_by_id(order_id)
        if order is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
        return self._to_read(
            order,
            include_customer=True,
            include_reservations=True,
            include_history=True,
        )

    def admin_list(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
    ) -> OrderListResponse:
        items, total = self.repo.list_all(
            page=page, page_size=page_size, status=status
        )
        pages = ceil(total / page_size) if page_size else 0
        return OrderListResponse(
            items=[
                self._to_read(o, include_customer=True, include_reservations=True)
                for o in items
            ],
            page=page,
            page_size=page_size,
            total=total,
            total_pages=pages,
        )
