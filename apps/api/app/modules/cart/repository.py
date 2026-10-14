from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.modules.cart.models import Cart, CartItem, CartStatus
from app.modules.catalog.models import Product


class CartRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_active_cart(self, user_id: UUID, *, for_update: bool = False) -> Cart | None:
        stmt: Select[tuple[Cart]] = (
            select(Cart)
            .where(Cart.user_id == user_id, Cart.status == CartStatus.ACTIVE.value)
            .options(
                selectinload(Cart.items).joinedload(CartItem.product).selectinload(Product.images)
            )
        )
        if for_update:
            # Lock only carts rows — joined/selectin loads must not inherit FOR UPDATE
            # (Postgres rejects FOR UPDATE on the nullable side of an outer join).
            stmt = stmt.with_for_update(of=Cart)
        return self.db.scalar(stmt)

    def create_cart(self, user_id: UUID) -> Cart:
        cart = Cart(user_id=user_id, status=CartStatus.ACTIVE.value)
        self.db.add(cart)
        self.db.flush()
        return cart

    def get_item(self, item_id: UUID, *, for_update: bool = False) -> CartItem | None:
        stmt = (
            select(CartItem)
            .where(CartItem.id == item_id)
            .options(
                joinedload(CartItem.cart),
                joinedload(CartItem.product).selectinload(Product.images),
            )
        )
        if for_update:
            stmt = stmt.with_for_update(of=CartItem)
        return self.db.scalar(stmt)

    def get_item_by_product(
        self,
        cart_id: UUID,
        product_id: UUID,
        *,
        for_update: bool = False,
    ) -> CartItem | None:
        stmt = select(CartItem).where(
            CartItem.cart_id == cart_id,
            CartItem.product_id == product_id,
        )
        if for_update:
            stmt = stmt.with_for_update(of=CartItem)
        return self.db.scalar(stmt)

    def add_item(self, cart_id: UUID, product_id: UUID, quantity: int) -> CartItem:
        item = CartItem(cart_id=cart_id, product_id=product_id, quantity=quantity)
        self.db.add(item)
        self.db.flush()
        return item

    def delete_item(self, item: CartItem) -> None:
        self.db.delete(item)
        self.db.flush()

    def clear_items(self, cart_id: UUID) -> int:
        items = list(
            self.db.scalars(select(CartItem).where(CartItem.cart_id == cart_id)).all()
        )
        for item in items:
            self.db.delete(item)
        self.db.flush()
        return len(items)

    def get_product(self, product_id: UUID) -> Product | None:
        return self.db.scalar(
            select(Product)
            .where(Product.id == product_id)
            .options(selectinload(Product.images))
        )
