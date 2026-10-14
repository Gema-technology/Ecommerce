from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.roles.models import User
from app.modules.roles.schemas import ROLE_CUSTOMER
from tests.conftest import create_user_with_role


def _login(client: TestClient, user: User) -> None:
    client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "secure-password"},
    )


def _seed_product(
    client: TestClient,
    admin: User,
    *,
    sku: str = "CART-1",
    price: str | None = "350.00",
) -> dict:
    _login(client, admin)
    category = client.post(
        "/api/v1/admin/categories", json={"name": f"Cat-{sku}"}
    ).json()
    brand = client.post(
        "/api/v1/admin/brands",
        json={"name": f"Brand-{sku}", "category_ids": [category["id"]]},
    ).json()
    product = client.post(
        "/api/v1/admin/products",
        json={
            "sku": sku,
            "name": f"Product {sku}",
            "brand_id": brand["id"],
            "category_id": category["id"],
            "images": [
                {
                    "url": f"https://cdn.example.com/{sku}.jpg",
                    "alt_text": sku,
                    "sort_order": 0,
                    "is_primary": True,
                }
            ],
        },
    ).json()
    if price is not None:
        assert (
            client.post(
                f"/api/v1/admin/products/{product['id']}/prices",
                json={
                    "price_type": "RETAIL",
                    "amount": price,
                    "currency": "USD",
                    "starts_at": datetime.now(UTC).isoformat(),
                },
            ).status_code
            == 201
        )
    return product


def test_get_or_create_active_cart(client: TestClient, customer_user: User) -> None:
    _login(client, customer_user)
    first = client.get("/api/v1/cart")
    assert first.status_code == 200, first.text
    data = first.json()
    assert data["status"] == "ACTIVE"
    assert data["items"] == []
    assert Decimal(data["subtotal"]) == Decimal("0")
    assert data["item_count"] == 0

    second = client.get("/api/v1/cart")
    assert second.status_code == 200
    assert second.json()["id"] == data["id"]


def test_unauthenticated_cart(client: TestClient) -> None:
    assert client.get("/api/v1/cart").status_code == 401
    assert (
        client.post(
            "/api/v1/cart/items",
            json={"product_id": str(uuid4()), "quantity": 1},
        ).status_code
        == 401
    )


def test_add_product_and_increment(
    client: TestClient, customer_user: User, admin_user: User
) -> None:
    product = _seed_product(client, admin_user, sku="ADD-1", price="100.00")
    _login(client, customer_user)

    added = client.post(
        "/api/v1/cart/items",
        json={"product_id": product["id"], "quantity": 1},
    )
    assert added.status_code == 200, added.text
    body = added.json()
    assert body["item_count"] == 1
    assert Decimal(body["subtotal"]) == Decimal("100.0000")
    assert len(body["items"]) == 1
    assert body["items"][0]["quantity"] == 1
    assert Decimal(body["items"][0]["line_total"]) == Decimal("100.0000")
    assert body["items"][0]["product"]["name"] == "Product ADD-1"
    assert body["items"][0]["product"]["image"].endswith("ADD-1.jpg")

    again = client.post(
        "/api/v1/cart/items",
        json={"product_id": product["id"], "quantity": 2},
    )
    assert again.status_code == 200
    body = again.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["quantity"] == 3
    assert body["item_count"] == 3
    assert Decimal(body["subtotal"]) == Decimal("300.0000")


def test_add_invalid_quantity_and_missing_inactive(
    client: TestClient, customer_user: User, admin_user: User
) -> None:
    product = _seed_product(client, admin_user, sku="VAL-1")
    _login(client, customer_user)

    assert (
        client.post(
            "/api/v1/cart/items",
            json={"product_id": product["id"], "quantity": 0},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/cart/items",
            json={"product_id": str(uuid4()), "quantity": 1},
        ).status_code
        == 404
    )

    _login(client, admin_user)
    assert (
        client.patch(
            f"/api/v1/admin/products/{product['id']}",
            json={"is_active": False},
        ).status_code
        == 200
    )
    _login(client, customer_user)
    inactive = client.post(
        "/api/v1/cart/items",
        json={"product_id": product["id"], "quantity": 1},
    )
    assert inactive.status_code == 400
    assert "not active" in inactive.json()["detail"].lower()


def test_update_and_remove_item(
    client: TestClient, customer_user: User, admin_user: User
) -> None:
    product = _seed_product(client, admin_user, sku="UPD-1", price="50.00")
    _login(client, customer_user)
    cart = client.post(
        "/api/v1/cart/items",
        json={"product_id": product["id"], "quantity": 2},
    ).json()
    item_id = cart["items"][0]["id"]

    updated = client.patch(
        f"/api/v1/cart/items/{item_id}",
        json={"quantity": 5},
    )
    assert updated.status_code == 200
    assert updated.json()["items"][0]["quantity"] == 5
    assert Decimal(updated.json()["subtotal"]) == Decimal("250.0000")

    zeroed = client.patch(
        f"/api/v1/cart/items/{item_id}",
        json={"quantity": 0},
    )
    assert zeroed.status_code == 200
    assert zeroed.json()["items"] == []

    cart = client.post(
        "/api/v1/cart/items",
        json={"product_id": product["id"], "quantity": 1},
    ).json()
    item_id = cart["items"][0]["id"]
    removed = client.delete(f"/api/v1/cart/items/{item_id}")
    assert removed.status_code == 200
    assert removed.json()["items"] == []


def test_cannot_access_other_user_item(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    db_session: Session,
) -> None:
    product = _seed_product(client, admin_user, sku="OWN-1", price="10.00")
    other = create_user_with_role(
        db_session,
        email="other-customer@example.com",
        password="secure-password",
        role_name=ROLE_CUSTOMER,
    )

    _login(client, customer_user)
    cart = client.post(
        "/api/v1/cart/items",
        json={"product_id": product["id"], "quantity": 1},
    ).json()
    item_id = cart["items"][0]["id"]

    _login(client, other)
    assert client.patch(
        f"/api/v1/cart/items/{item_id}",
        json={"quantity": 9},
    ).status_code == 404
    assert client.delete(f"/api/v1/cart/items/{item_id}").status_code == 404

    own = client.get("/api/v1/cart").json()
    assert own["items"] == []


def test_clear_cart(client: TestClient, customer_user: User, admin_user: User) -> None:
    p1 = _seed_product(client, admin_user, sku="CLR-1", price="20.00")
    p2 = _seed_product(client, admin_user, sku="CLR-2", price="30.00")
    _login(client, customer_user)
    client.post("/api/v1/cart/items", json={"product_id": p1["id"], "quantity": 1})
    client.post("/api/v1/cart/items", json={"product_id": p2["id"], "quantity": 2})
    cart_id = client.get("/api/v1/cart").json()["id"]

    cleared = client.delete("/api/v1/cart")
    assert cleared.status_code == 200
    body = cleared.json()
    assert body["id"] == cart_id
    assert body["status"] == "ACTIVE"
    assert body["items"] == []
    assert body["item_count"] == 0


def test_price_uses_current_retail_and_decimal(
    client: TestClient, customer_user: User, admin_user: User
) -> None:
    product = _seed_product(client, admin_user, sku="PRC-1", price="350.00")
    _login(client, customer_user)
    client.post("/api/v1/cart/items", json={"product_id": product["id"], "quantity": 2})

    _login(client, admin_user)
    history = client.get(f"/api/v1/admin/products/{product['id']}/prices").json()
    old_id = history[0]["id"]
    assert (
        client.patch(
            f"/api/v1/admin/products/{product['id']}/prices/{old_id}",
            json={"ends_at": datetime.now(UTC).isoformat(), "is_active": False},
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/v1/admin/products/{product['id']}/prices",
            json={
                "price_type": "RETAIL",
                "amount": "330.00",
                "starts_at": datetime.now(UTC).isoformat(),
            },
        ).status_code
        == 201
    )

    _login(client, customer_user)
    cart = client.get("/api/v1/cart").json()
    assert Decimal(str(cart["items"][0]["product"]["price"]["amount"])) == Decimal("330.0000")
    assert Decimal(str(cart["items"][0]["line_total"])) == Decimal("660.0000")
    assert Decimal(str(cart["subtotal"])) == Decimal("660.0000")


def test_inactive_product_remains_visible(
    client: TestClient, customer_user: User, admin_user: User
) -> None:
    product = _seed_product(client, admin_user, sku="INA-1", price="99.00")
    _login(client, customer_user)
    client.post("/api/v1/cart/items", json={"product_id": product["id"], "quantity": 1})

    _login(client, admin_user)
    assert (
        client.patch(
            f"/api/v1/admin/products/{product['id']}",
            json={"is_active": False},
        ).status_code
        == 200
    )

    _login(client, customer_user)
    cart = client.get("/api/v1/cart").json()
    assert len(cart["items"]) == 1
    assert cart["items"][0]["available"] is False
    assert cart["items"][0]["product"]["is_active"] is False
    assert Decimal(str(cart["subtotal"])) == Decimal("0")


def test_add_to_cart_does_not_change_inventory(
    client: TestClient,
    customer_user: User,
    admin_user: User,
) -> None:
    product = _seed_product(client, admin_user, sku="INV-1", price="40.00")
    _login(client, admin_user)
    assert (
        client.post(
            "/api/v1/admin/inventory",
            json={"product_id": product["id"]},
        ).status_code
        == 201
    )
    assert (
        client.post(
            f"/api/v1/admin/inventory/{product['id']}/purchase",
            json={"quantity": 10},
        ).status_code
        == 200
    )
    before = client.get(f"/api/v1/admin/inventory/{product['id']}").json()

    _login(client, customer_user)
    assert (
        client.post(
            "/api/v1/cart/items",
            json={"product_id": product["id"], "quantity": 3},
        ).status_code
        == 200
    )

    _login(client, admin_user)
    after = client.get(f"/api/v1/admin/inventory/{product['id']}").json()
    assert after["quantity"] == before["quantity"]
    assert after["reserved_quantity"] == before["reserved_quantity"]
    assert after["quantity"] == "10.0000" or Decimal(str(after["quantity"])) == Decimal("10")
    assert Decimal(str(after["reserved_quantity"])) == Decimal("0")
