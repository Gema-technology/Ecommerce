from datetime import UTC, datetime
from decimal import Decimal
from math import ceil
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.modules.catalog.models import Product
from app.modules.commerce.tax import RIMPE_NEGOCIO_POPULAR, calculate_tax, store_tax_regime
from app.modules.inventory.models import InventoryReservation, ReservationStatus
from app.modules.inventory.schemas import MovementRequest
from app.modules.inventory.service import InventoryService
from app.modules.notifications.service import (
    EVENT_ORDER_PAID,
    EVENT_ORDER_SHIPPED,
    notify_order_event,
)
from app.modules.orders.models import Order, OrderItem, OrderStatus, OrderStatusEvent
from app.modules.orders.repository import OrderRepository
from app.modules.orders.schemas import (
    CounterSaleRequest,
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
from app.modules.payments.models import Payment, PaymentStatus
from app.modules.pricing.models import PriceCurrency
from app.modules.pricing.service import PricingService
from app.modules.roles.models import User
from app.modules.sri.models import FiscalDocument
from app.modules.users.service import UserService


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
            channel=order.channel,
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

    def remove_incorrect_iva(self, order_id: UUID, admin: User) -> OrderRead:
        order = self.db.scalar(select(Order).where(Order.id == order_id).with_for_update())
        if order is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
        if order.status == OrderStatus.CANCELLED.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Un pedido cancelado no se corrige",
            )
        tax = Decimal(order.tax_total or 0)
        if tax <= 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Este pedido no tiene IVA",
            )
        if store_tax_regime(self.db) != RIMPE_NEGOCIO_POPULAR:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Solo se quita el IVA cuando la tienda está en RIMPE Negocio Popular"
                ),
            )
        documents = list(
            self.db.scalars(
                select(FiscalDocument).where(FiscalDocument.order_id == order.id)
            ).all()
        )
        for document in documents:
            if document.status in {"CANCELLED", "REJECTED"}:
                continue
            if Decimal(document.tax_total or 0) > 0:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"El comprobante {document.document_number} ya incluye IVA. "
                        "Ese documento no se reescribe desde el pedido."
                    ),
                )

        old_total = Decimal(order.total)
        corrected = (
            Decimal(order.subtotal)
            - Decimal(order.discount_total or 0)
            + Decimal(order.shipping_total or 0)
        ).quantize(Decimal("0.0001"))
        order.tax_total = Decimal("0.0000")
        order.total = corrected
        payments = list(
            self.db.scalars(select(Payment).where(Payment.order_id == order.id)).all()
        )
        for payment in payments:
            if payment.provider == "manual" and Decimal(payment.amount) == old_total:
                payment.amount = corrected
        self._record_status_event(
            order,
            from_status=order.status,
            to_status=order.status,
            actor=admin,
            note="Se quitó el IVA. RIMPE Negocio Popular no lo cobra.",
        )
        self.db.commit()
        return self.admin_get(order_id)

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

    def create_counter_sale(self, admin: User, payload: CounterSaleRequest) -> OrderRead:
        """Sell in store for cash and consume stock. No customer account is required."""
        try:
            order = self._create_counter_sale(admin, payload)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        if order.customer_email:
            notify_order_event(self.db, order.id, EVENT_ORDER_PAID)

        loaded = self.repo.get_by_id(order.id)
        assert loaded is not None
        return self._to_read(
            loaded,
            include_customer=True,
            include_reservations=True,
            include_history=True,
        )

    def _create_counter_sale(self, admin: User, payload: CounterSaleRequest) -> Order:
        product_ids = [item.product_id for item in payload.items]
        if len(product_ids) != len(set(product_ids)):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Cada producto solo puede aparecer una vez",
            )

        customer: User | None = None
        if payload.customer_id is not None:
            customer = UserService(self.db)._require_customer(payload.customer_id)
            if not customer.is_active:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="El cliente está inactivo",
                )

        pricing = PricingService(self.db)
        price_map = pricing.map_effective_prices(product_ids)
        lines: list[tuple[Product, int, Decimal, Decimal]] = []
        subtotal = Decimal("0")
        discount_total = Decimal("0")

        for item in payload.items:
            product = self.db.scalar(
                select(Product).where(Product.id == item.product_id).with_for_update()
            )
            if product is None or not product.is_active:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Product unavailable",
                )
            effective = price_map.get(product.id)
            if effective is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Price unavailable for product: {product.name}",
                )
            unit = Decimal(effective.amount).quantize(Decimal("0.0001"))
            line_discount = Decimal(effective.unit_discount * item.quantity).quantize(
                Decimal("0.0001")
            )
            line_total = Decimal(unit * item.quantity).quantize(Decimal("0.0001"))
            subtotal += line_total
            discount_total += line_discount
            lines.append((product, item.quantity, unit, line_discount))

        subtotal = subtotal.quantize(Decimal("0.0001"))
        discount_total = discount_total.quantize(Decimal("0.0001"))
        merchandise = (subtotal - discount_total).quantize(Decimal("0.0001"))
        if merchandise < 0:
            merchandise = Decimal("0.0000")
        tax_total = calculate_tax(
            taxable_subtotal=merchandise,
            tax_regime=store_tax_regime(self.db),
        )
        total = (merchandise + tax_total).quantize(Decimal("0.0001"))

        if customer is not None:
            buyer_name = f"{customer.first_name} {customer.last_name}".strip()
            buyer_email = customer.email
            buyer_phone = customer.phone
            buyer_id = customer.id
        else:
            buyer_name = payload.customer_name
            buyer_email = None
            buyer_phone = payload.customer_phone
            buyer_id = None

        id_type = payload.buyer_id_type
        id_number = payload.buyer_id_number
        if id_type is None and customer is not None and customer.tax_id:
            id_type = customer.tax_id_type
            id_number = customer.tax_id
        if customer is not None and id_type and id_number:
            customer.tax_id_type = id_type
            customer.tax_id = id_number

        address_line = payload.address_line or (customer.address_line if customer else None)
        city = payload.city or (customer.city if customer else None)
        province = payload.province or (customer.province if customer else None)
        country = payload.country or (customer.country if customer else None) or "Ecuador"
        reference = payload.address_reference or (
            customer.address_reference if customer else None
        )
        postal_code = payload.postal_code or (customer.postal_code if customer else None)
        if id_type and not (address_line and city and province and buyer_phone):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="La factura necesita teléfono, dirección, ciudad y provincia",
            )
        shipping_address = None
        if address_line and city and province:
            shipping_address = {
                "recipient_name": buyer_name or "Consumidor final",
                "phone": buyer_phone or "",
                "address_line": address_line,
                "reference": reference,
                "city": city,
                "province": province,
                "country": country,
                "postal_code": postal_code,
            }
            if customer is not None:
                customer.address_line = address_line
                customer.address_reference = reference
                customer.city = city
                customer.province = province
                customer.country = country
                customer.postal_code = postal_code

        order = Order(
            user_id=buyer_id,
            channel="COUNTER",
            order_number=self.repo.next_order_number(),
            status=OrderStatus.PAID.value,
            currency=PriceCurrency.USD.value,
            subtotal=subtotal,
            tax_total=tax_total,
            shipping_total=Decimal("0.0000"),
            discount_total=discount_total,
            total=total,
            customer_email=buyer_email,
            customer_name=buyer_name,
            customer_phone=buyer_phone,
            customer_notes=payload.customer_notes,
            buyer_id_type=id_type,
            buyer_id_number=id_number,
            shipping_address=shipping_address,
        )
        self.repo.add(order)

        for product, quantity, unit, line_discount in lines:
            line_total = Decimal(unit * quantity).quantize(Decimal("0.0001"))
            self.repo.add_item(
                OrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    product_name_snapshot=product.name,
                    sku_snapshot=product.sku,
                    unit_price=unit,
                    quantity=quantity,
                    line_total=line_total,
                    line_discount=line_discount,
                )
            )
            try:
                self.inventory.sale(
                    product.id,
                    MovementRequest(
                        quantity=quantity,
                        reference_type="order",
                        reference_id=str(order.id),
                        notes=f"Venta en mostrador {order.order_number}",
                    ),
                    admin,
                    commit=False,
                )
            except HTTPException as exc:
                if exc.status_code == status.HTTP_409_CONFLICT:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Stock insuficiente para {product.name}",
                    ) from exc
                if exc.status_code == status.HTTP_404_NOT_FOUND:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"El producto {product.name} no tiene inventario",
                    ) from exc
                raise

        now = datetime.now(UTC)
        self.db.add(
            Payment(
                order_id=order.id,
                provider="manual",
                provider_payment_id=f"counter_{order.id}",
                method="CASH",
                status=PaymentStatus.SUCCEEDED.value,
                amount=total,
                currency=PriceCurrency.USD.value,
                metadata_json={
                    "source": "counter_sale",
                    "collected_by": str(admin.id),
                },
                paid_at=now,
            )
        )
        self.db.add(
            OrderStatusEvent(
                order_id=order.id,
                from_status=OrderStatus.PENDING_PAYMENT.value,
                to_status=OrderStatus.PAID.value,
                actor_user_id=admin.id,
                note="Venta en mostrador.",
            )
        )
        self.db.flush()
        return order
