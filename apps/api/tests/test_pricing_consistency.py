"""Pricing consistency: cart and checkout share effective price resolution."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.orders.models import Order
from app.modules.roles.models import User
from tests.test_orders_checkout import _add_to_cart, _checkout_body, _login, _seed_sellable


def test_cart_and_checkout_same_retail_price(
    client: TestClient, customer_user: User, admin_user: User
) -> None:
    product = _seed_sellable(client, admin_user, sku="PC-SAME", price="199.99")
    _add_to_cart(client, customer_user, product["id"], 2)

    cart = client.get("/api/v1/cart").json()
    assert Decimal(str(cart["items"][0]["unit_price"])) == Decimal("199.9900")
    assert Decimal(str(cart["subtotal"])) == Decimal("399.9800")
    assert cart["items"][0]["product"]["price"]["price_type"] == "RETAIL"

    order = client.post("/api/v1/checkout", json=_checkout_body()).json()
    assert Decimal(str(order["items"][0]["unit_price"])) == Decimal("199.9900")
    assert Decimal(str(order["subtotal"])) == Decimal("399.9800")
    assert order["items"][0]["price_type"] == "RETAIL"


def test_cart_and_checkout_use_active_promotion(
    client: TestClient, customer_user: User, admin_user: User
) -> None:
    product = _seed_sellable(client, admin_user, sku="PC-PROMO", price="500.00")
    _login(client, admin_user)
    assert (
        client.post(
            f"/api/v1/admin/products/{product['id']}/prices",
            json={
                "price_type": "PROMOTIONAL",
                "amount": "420.00",
                "starts_at": datetime.now(UTC).isoformat(),
            },
        ).status_code
        == 201
    )

    _add_to_cart(client, customer_user, product["id"], 1)
    cart = client.get("/api/v1/cart").json()
    assert Decimal(str(cart["items"][0]["unit_price"])) == Decimal("420.0000")
    assert Decimal(str(cart["items"][0]["unit_discount"])) == Decimal("80.0000")
    assert cart["items"][0]["product"]["price"]["price_type"] == "PROMOTIONAL"

    order = client.post("/api/v1/checkout", json=_checkout_body()).json()
    assert Decimal(str(order["items"][0]["unit_price"])) == Decimal("420.0000")
    assert Decimal(str(order["discount_total"])) == Decimal("80.0000")
    assert order["items"][0]["price_type"] == "PROMOTIONAL"


def test_expired_promotion_falls_back_to_retail(
    client: TestClient, customer_user: User, admin_user: User
) -> None:
    product = _seed_sellable(client, admin_user, sku="PC-EXP", price="300.00")
    _login(client, admin_user)
    past = (datetime.now(UTC) - timedelta(days=2)).isoformat()
    ended = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    assert (
        client.post(
            f"/api/v1/admin/products/{product['id']}/prices",
            json={
                "price_type": "PROMOTIONAL",
                "amount": "200.00",
                "starts_at": past,
                "ends_at": ended,
            },
        ).status_code
        == 201
    )

    _add_to_cart(client, customer_user, product["id"], 1)
    cart = client.get("/api/v1/cart").json()
    assert Decimal(str(cart["items"][0]["unit_price"])) == Decimal("300.0000")
    assert cart["items"][0]["product"]["price"]["price_type"] == "RETAIL"

    order = client.post("/api/v1/checkout", json=_checkout_body()).json()
    assert Decimal(str(order["items"][0]["unit_price"])) == Decimal("300.0000")
    assert order["items"][0]["price_type"] == "RETAIL"


def test_price_changed_blocks_checkout(
    client: TestClient, customer_user: User, admin_user: User
) -> None:
    product = _seed_sellable(client, admin_user, sku="PC-CHG", price="999.00")
    _add_to_cart(client, customer_user, product["id"], 1)

    _login(client, admin_user)
    old = client.get(f"/api/v1/admin/products/{product['id']}/prices").json()[0]
    client.patch(
        f"/api/v1/admin/products/{product['id']}/prices/{old['id']}",
        json={"is_active": False, "ends_at": datetime.now(UTC).isoformat()},
    )
    assert (
        client.post(
            f"/api/v1/admin/products/{product['id']}/prices",
            json={
                "price_type": "RETAIL",
                "amount": "1049.00",
                "starts_at": datetime.now(UTC).isoformat(),
            },
        ).status_code
        == 201
    )

    _login(client, customer_user)
    response = client.post("/api/v1/checkout", json=_checkout_body())
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "PRICE_CHANGED"
    assert Decimal(str(detail["items"][0]["previous_unit_price"])) == Decimal("999.0000")
    assert Decimal(str(detail["items"][0]["current_unit_price"])) == Decimal("1049.0000")


def test_order_snapshot_stable_after_catalog_price_change(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    db_session: Session,
) -> None:
    product = _seed_sellable(client, admin_user, sku="PC-SNAP", price="150.00")
    _add_to_cart(client, customer_user, product["id"], 1)
    order_body = client.post("/api/v1/checkout", json=_checkout_body()).json()
    order_id = UUID(order_body["order_id"])
    assert Decimal(str(order_body["items"][0]["unit_price"])) == Decimal("150.0000")

    _login(client, admin_user)
    old = client.get(f"/api/v1/admin/products/{product['id']}/prices").json()[0]
    client.patch(
        f"/api/v1/admin/products/{product['id']}/prices/{old['id']}",
        json={"is_active": False, "ends_at": datetime.now(UTC).isoformat()},
    )
    assert (
        client.post(
            f"/api/v1/admin/products/{product['id']}/prices",
            json={
                "price_type": "RETAIL",
                "amount": "999.00",
                "starts_at": datetime.now(UTC).isoformat(),
            },
        ).status_code
        == 201
    )

    db_session.expire_all()
    order = db_session.get(Order, order_id)
    assert order is not None
    assert Decimal(str(order.items[0].unit_price)) == Decimal("150.0000")
    assert Decimal(str(order.total)) == Decimal("150.0000")

    _login(client, customer_user)
    detail = client.get(f"/api/v1/orders/{order_id}").json()
    assert Decimal(str(detail["items"][0]["unit_price"])) == Decimal("150.0000")


def test_add_to_cart_ignores_client_supplied_prices(
    client: TestClient, customer_user: User, admin_user: User
) -> None:
    """Frontend-sent price fields must never affect cart totals."""
    product = _seed_sellable(client, admin_user, sku="PC-IGN", price="250.00")
    _login(client, customer_user)
    response = client.post(
        "/api/v1/cart/items",
        json={
            "product_id": product["id"],
            "quantity": 1,
            "price": "1.00",
            "unit_price": "1.00",
            "subtotal": "1.00",
            "total": "1.00",
            "discount": "999.00",
        },
    )
    assert response.status_code == 200
    cart = client.get("/api/v1/cart").json()
    assert Decimal(str(cart["items"][0]["unit_price"])) == Decimal("250.0000")
    assert Decimal(str(cart["subtotal"])) == Decimal("250.0000")
    assert Decimal(str(cart["items"][0]["quoted_unit_price"])) == Decimal("250.0000")
