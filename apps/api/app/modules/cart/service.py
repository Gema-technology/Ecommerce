from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.cart.models import Cart, CartItem, CartStatus
from app.modules.cart.repository import CartRepository
from app.modules.cart.schemas import (
    CartItemCreate,
    CartItemRead,
    CartItemUpdate,
    CartProductPrice,
    CartProductSummary,
    CartRead,
)
from app.modules.catalog.models import Product, ProductImage
from app.modules.pricing.models import PriceCurrency
from app.modules.pricing.schemas import EffectivePrice
from app.modules.pricing.service import PricingService
from app.modules.products.schemas import AvailabilityStatus
from app.modules.products.service import ProductService
from app.modules.roles.models import User


def _money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal("0.0001"))


class CartService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = CartRepository(db)
        self.pricing = PricingService(db)
        self.products = ProductService(db)

    def get_or_create_active_cart(self, user: User) -> Cart:
        cart = self.repo.get_active_cart(user.id, for_update=True)
        if cart is not None:
            return cart
        try:
            cart = self.repo.create_cart(user.id)
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            cart = self.repo.get_active_cart(user.id)
            if cart is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Could not create cart",
                ) from None
            return cart
        return self.repo.get_active_cart(user.id) or cart

    def get_cart(self, user: User) -> CartRead:
        cart = self.get_or_create_active_cart(user)
        loaded = self.repo.get_active_cart(user.id)
        assert loaded is not None
        return self._to_read(loaded)

    def add_item(self, user: User, payload: CartItemCreate) -> CartRead:
        cart = self.get_or_create_active_cart(user)
        product = self.repo.get_product(payload.product_id)
        if product is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
        if not product.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Product is not active",
            )

        effective = self.pricing.resolve_effective_price(payload.product_id)
        quoted = _money(effective.amount) if effective is not None else None

        existing = self.repo.get_item_by_product(
            cart.id, payload.product_id, for_update=True
        )
        if existing is not None:
            existing.quantity += payload.quantity
            if quoted is not None:
                existing.quoted_unit_price = quoted
            self.db.flush()
        else:
            try:
                item = self.repo.add_item(cart.id, payload.product_id, payload.quantity)
                item.quoted_unit_price = quoted
                self.db.flush()
            except IntegrityError:
                self.db.rollback()
                cart = self.get_or_create_active_cart(user)
                existing = self.repo.get_item_by_product(
                    cart.id, payload.product_id, for_update=True
                )
                if existing is None:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Could not add item to cart",
                    ) from None
                existing.quantity += payload.quantity
                if quoted is not None:
                    existing.quoted_unit_price = quoted
                self.db.flush()
        self.db.commit()
        return self.get_cart(user)

    def update_item(self, user: User, item_id: UUID, payload: CartItemUpdate) -> CartRead:
        item = self._owned_item(user, item_id, for_update=True)
        if payload.quantity == 0:
            self.repo.delete_item(item)
        else:
            if item.product is not None and not item.product.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Product is not active",
                )
            item.quantity = payload.quantity
            effective = self.pricing.resolve_effective_price(item.product_id)
            if effective is not None:
                item.quoted_unit_price = _money(effective.amount)
            self.db.flush()
        self.db.commit()
        return self.get_cart(user)

    def remove_item(self, user: User, item_id: UUID) -> CartRead:
        item = self._owned_item(user, item_id, for_update=True)
        self.repo.delete_item(item)
        self.db.commit()
        return self.get_cart(user)

    def clear_cart(self, user: User) -> CartRead:
        cart = self.get_or_create_active_cart(user)
        self.repo.clear_items(cart.id)
        self.db.commit()
        return self.get_cart(user)

    def sync_quoted_prices(self, user: User) -> CartRead:
        """Refresh quoted prices to current effective prices after client acknowledgment."""
        cart = self.get_or_create_active_cart(user)
        loaded = self.repo.get_active_cart(user.id, for_update=True)
        assert loaded is not None
        product_ids = [item.product_id for item in loaded.items]
        price_map = self.pricing.map_effective_prices(product_ids)
        for item in loaded.items:
            effective = price_map.get(item.product_id)
            if effective is None:
                continue
            item.quoted_unit_price = _money(effective.amount)
        self.db.commit()
        return self.get_cart(user)

    def _owned_item(
        self, user: User, item_id: UUID, *, for_update: bool = False
    ) -> CartItem:
        item = self.repo.get_item(item_id, for_update=for_update)
        if item is None or item.cart is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Cart item not found"
            )
        if item.cart.user_id != user.id or item.cart.status != CartStatus.ACTIVE.value:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart item not found")
        return item

    def _primary_image(self, product: Product) -> str | None:
        if not product.images:
            return None
        primary = next((img for img in product.images if img.is_primary), None)
        image: ProductImage | None = primary or min(
            product.images, key=lambda i: i.sort_order
        )
        return image.url if image else None

    def _to_read(self, cart: Cart) -> CartRead:
        product_ids = [item.product_id for item in cart.items]
        price_map = self.pricing.map_effective_prices(product_ids)
        avail_map = self.products.map_availability(product_ids)

        items_read: list[CartItemRead] = []
        subtotal = Decimal("0")
        discount_total = Decimal("0")
        currency = PriceCurrency.USD
        item_count = 0
        has_price_changes = False

        for item in cart.items:
            product = item.product
            if product is None:
                continue
            effective: EffectivePrice | None = price_map.get(product.id)
            available = product.is_active
            line_total: Decimal | None = None
            unit_price: Decimal | None = None
            unit_discount = Decimal("0")
            line_discount = Decimal("0")
            price_summary: CartProductPrice | None = None
            price_changed = False

            if effective is not None:
                unit_price = _money(effective.amount)
                unit_discount = _money(effective.unit_discount)
                line_discount = _money(unit_discount * Decimal(item.quantity))
                price_summary = CartProductPrice(
                    amount=unit_price,
                    currency=effective.currency,
                    price_type=effective.price_type,
                )
                currency = effective.currency
                if available:
                    line_total = _money(unit_price * Decimal(item.quantity))
                    subtotal += line_total
                    discount_total += line_discount
                if item.quoted_unit_price is not None and _money(
                    item.quoted_unit_price
                ) != unit_price:
                    price_changed = True
                    has_price_changes = True

            item_count += item.quantity
            items_read.append(
                CartItemRead(
                    id=item.id,
                    quantity=item.quantity,
                    unit_price=unit_price,
                    unit_discount=unit_discount,
                    line_discount=line_discount,
                    line_total=line_total,
                    quoted_unit_price=item.quoted_unit_price,
                    price_changed=price_changed,
                    available=available,
                    product=CartProductSummary(
                        id=product.id,
                        name=product.name,
                        slug=product.slug,
                        sku=product.sku,
                        image=self._primary_image(product),
                        price=price_summary,
                        is_active=product.is_active,
                        availability=avail_map.get(
                            product.id, AvailabilityStatus.UNKNOWN
                        ),
                    ),
                )
            )

        return CartRead(
            id=cart.id,
            status=cart.status,
            items=items_read,
            subtotal=_money(subtotal),
            discount_total=_money(discount_total),
            currency=currency,
            item_count=item_count,
            has_price_changes=has_price_changes,
        )
