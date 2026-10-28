from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.modules.cart.models import Cart, CartItem, CartStatus
from app.modules.cart.repository import CartRepository
from app.modules.catalog.models import Product
from app.modules.commerce.tax import charges_iva, store_tax_regime
from app.modules.commerce.totals import compute_order_totals
from app.modules.inventory.models import InventoryReservation, ReservationStatus
from app.modules.inventory.schemas import MovementRequest
from app.modules.inventory.service import InventoryService
from app.modules.notifications.service import EVENT_ORDER_CREATED, notify_order_event
from app.modules.orders.models import Order, OrderItem, OrderStatus
from app.modules.orders.repository import OrderRepository
from app.modules.orders.schemas import (
    CheckoutItemRead,
    CheckoutPreviewItemRead,
    CheckoutPreviewRequest,
    CheckoutPreviewResponse,
    CheckoutRequest,
    CheckoutResponse,
    ShippingAddress,
)
from app.modules.pricing.models import PriceCurrency
from app.modules.pricing.schemas import EffectivePrice
from app.modules.pricing.service import PricingService
from app.modules.roles.models import User
from app.modules.store_config.service import StoreConfigService


def _money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal("0.0001"))


class _LinePayload:
    __slots__ = ("item", "product", "effective")

    def __init__(
        self,
        item: CartItem,
        product: Product,
        effective: EffectivePrice,
    ) -> None:
        self.item = item
        self.product = product
        self.effective = effective


class CheckoutService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.carts = CartRepository(db)
        self.orders = OrderRepository(db)
        self.pricing = PricingService(db)
        self.inventory = InventoryService(db)

    def preview(self, user: User, payload: CheckoutPreviewRequest) -> CheckoutPreviewResponse:
        cart, line_payload = self._load_cart_lines(user, for_update=False)
        return self._build_preview(cart, line_payload, payload.shipping_address)

    def checkout(self, user: User, payload: CheckoutRequest) -> CheckoutResponse:
        try:
            return self._checkout(user, payload)
        except Exception:
            self.db.rollback()
            raise

    def _load_cart_lines(
        self,
        user: User,
        *,
        for_update: bool,
    ) -> tuple[Cart, list[_LinePayload]]:
        query = (
            select(Cart)
            .where(
                Cart.user_id == user.id,
                Cart.status == CartStatus.ACTIVE.value,
            )
            .options(selectinload(Cart.items).joinedload(CartItem.product))
        )
        if for_update:
            query = query.with_for_update()
        cart = self.db.scalar(query)
        if cart is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No active cart",
            )
        if not cart.items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cart is empty",
            )

        product_ids = [item.product_id for item in cart.items]
        price_map = self.pricing.map_effective_prices(product_ids)
        line_payload: list[_LinePayload] = []
        price_changes: list[dict[str, str]] = []

        for item in cart.items:
            product = item.product
            if product is None:
                product = self.db.get(Product, item.product_id)
            if product is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Product unavailable",
                )
            if not product.is_active:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Product unavailable: {product.name}",
                )
            if item.quantity <= 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid quantity",
                )
            effective = price_map.get(product.id)
            if effective is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Price unavailable for product: {product.name}",
                )

            current = _money(effective.amount)
            if item.quoted_unit_price is not None and _money(item.quoted_unit_price) != current:
                price_changes.append(
                    {
                        "product_id": str(product.id),
                        "product_name": product.name,
                        "previous_unit_price": str(_money(item.quoted_unit_price)),
                        "current_unit_price": str(current),
                        "currency": effective.currency.value,
                    }
                )
            line_payload.append(_LinePayload(item, product, effective))

        if price_changes:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "PRICE_CHANGED",
                    "message": (
                        "One or more product prices have changed. "
                        "Refresh your cart to continue."
                    ),
                    "items": price_changes,
                },
            )

        return cart, line_payload

    def _summarize_lines(
        self, line_payload: list[_LinePayload]
    ) -> tuple[Decimal, Decimal, list[CheckoutPreviewItemRead]]:
        subtotal = Decimal("0")
        discount_total = Decimal("0")
        items: list[CheckoutPreviewItemRead] = []

        for entry in line_payload:
            item = entry.item
            product = entry.product
            effective = entry.effective
            unit = _money(effective.amount)
            qty = Decimal(item.quantity)
            line_discount = _money(effective.unit_discount * qty)
            line_total = _money(unit * qty)
            subtotal += line_total
            discount_total += line_discount
            items.append(
                CheckoutPreviewItemRead(
                    product_id=product.id,
                    product_name=product.name,
                    sku=product.sku,
                    quantity=item.quantity,
                    unit_price=unit,
                    unit_discount=_money(effective.unit_discount),
                    line_discount=line_discount,
                    line_total=line_total,
                    price_type=effective.price_type.value,
                )
            )

        return _money(subtotal), _money(discount_total), items

    def _build_preview(
        self,
        cart: Cart,
        line_payload: list[_LinePayload],
        shipping_address: ShippingAddress | None,
    ) -> CheckoutPreviewResponse:
        subtotal, discount_total, items = self._summarize_lines(line_payload)
        store_config = StoreConfigService(self.db).get_read()
        tax_regime = store_tax_regime(self.db)
        totals = compute_order_totals(
            subtotal=subtotal,
            discount_total=discount_total,
            shipping_address=shipping_address,
            store_config=store_config,
            tax_regime=tax_regime,
        )
        currency = (
            line_payload[0].effective.currency.value
            if line_payload
            else PriceCurrency.USD.value
        )
        return CheckoutPreviewResponse(
            currency=currency,
            subtotal=totals.subtotal,
            tax_total=totals.tax_total,
            shipping_total=totals.shipping_total,
            discount_total=totals.discount_total,
            total=totals.total,
            shipping_method=totals.shipping_method,
            tax_enabled=charges_iva(tax_regime=tax_regime),
            items=items,
        )

    def _checkout(self, user: User, payload: CheckoutRequest) -> CheckoutResponse:
        cart, line_payload = self._load_cart_lines(user, for_update=True)
        subtotal, discount_total, preview_items = self._summarize_lines(line_payload)
        store_config = StoreConfigService(self.db).get_read()
        tax_regime = store_tax_regime(self.db)
        totals = compute_order_totals(
            subtotal=subtotal,
            discount_total=discount_total,
            shipping_address=payload.shipping_address,
            store_config=store_config,
            tax_regime=tax_regime,
        )

        customer_name = payload.shipping_address.recipient_name
        customer_phone = payload.shipping_address.phone
        customer_email = user.email

        order_number = self.orders.next_order_number()
        order = Order(
            user_id=user.id,
            order_number=order_number,
            status=OrderStatus.PENDING_PAYMENT.value,
            currency=PriceCurrency.USD.value,
            subtotal=totals.subtotal,
            tax_total=totals.tax_total,
            shipping_total=totals.shipping_total,
            discount_total=totals.discount_total,
            total=totals.total,
            shipping_address=payload.shipping_address.model_dump(),
            customer_email=customer_email,
            customer_name=customer_name,
            customer_phone=customer_phone,
            customer_notes=payload.customer_notes,
            buyer_id_type=payload.buyer_id_type,
            buyer_id_number=payload.buyer_id_number,
            cart_id=cart.id,
        )
        self.orders.add(order)

        checkout_items: list[CheckoutItemRead] = []
        expires_at = datetime.now(UTC) + timedelta(hours=settings.reservation_ttl_hours)

        for entry in line_payload:
            item = entry.item
            product = entry.product
            effective = entry.effective
            unit = _money(effective.amount)
            line_discount = _money(effective.unit_discount * Decimal(item.quantity))
            line_total = _money(unit * Decimal(item.quantity))
            self.orders.add_item(
                OrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    product_name_snapshot=product.name,
                    sku_snapshot=product.sku,
                    unit_price=unit,
                    quantity=item.quantity,
                    line_total=line_total,
                    line_discount=line_discount,
                )
            )
            checkout_items.append(
                CheckoutItemRead(
                    product_id=product.id,
                    product_name=product.name,
                    quantity=item.quantity,
                    unit_price=unit,
                    unit_discount=_money(effective.unit_discount),
                    line_discount=line_discount,
                    line_total=line_total,
                    price_type=effective.price_type.value,
                )
            )

            op = self.inventory.reserve(
                product.id,
                MovementRequest(
                    quantity=item.quantity,
                    reference_type="order",
                    reference_id=str(order.id),
                    notes=f"Checkout reservation for {order_number}",
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

        cart.status = CartStatus.CONVERTED.value
        self.db.flush()
        self.db.commit()

        notify_order_event(self.db, order.id, EVENT_ORDER_CREATED)

        loaded = self.orders.get_by_id(order.id)
        assert loaded is not None
        return CheckoutResponse(
            order_id=loaded.id,
            order_number=loaded.order_number,
            status=loaded.status,
            currency=loaded.currency,
            subtotal=loaded.subtotal,
            tax_total=loaded.tax_total,
            shipping_total=loaded.shipping_total,
            discount_total=loaded.discount_total,
            total=loaded.total,
            customer_email=loaded.customer_email,
            customer_name=loaded.customer_name,
            customer_phone=loaded.customer_phone,
            buyer_id_type=loaded.buyer_id_type,
            buyer_id_number=loaded.buyer_id_number,
            shipping_address=ShippingAddress.model_validate(loaded.shipping_address)
            if loaded.shipping_address
            else None,
            customer_notes=loaded.customer_notes,
            items=checkout_items,
        )
