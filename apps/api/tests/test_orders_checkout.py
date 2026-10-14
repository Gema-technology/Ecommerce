from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.cart.models import Cart, CartStatus
from app.modules.inventory.models import Inventory, InventoryReservation
from app.modules.orders.models import Order, OrderStatus
from app.modules.roles.models import User
from app.modules.roles.schemas import ROLE_CUSTOMER
from tests.conftest import create_user_with_role


def _checkout_body(**overrides: object) -> dict:
    body: dict = {
        "shipping_address": {
            "recipient_name": "Buyer Test",
            "phone": "0999999999",
            "address_line": "Av. Teodoro Gomez 123",
            "reference": "Casa blanca",
            "city": "Ibarra",
            "province": "Imbabura",
            "country": "Ecuador",
            "postal_code": "100150",
        },
        "customer_notes": "Entregar en horario laboral",
    }
    body.update(overrides)
    return body


def _login(client: TestClient, user: User) -> None:
    client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "secure-password"},
    )


def _seed_sellable(
    client: TestClient,
    admin: User,
    *,
    sku: str,
    price: str = "100.00",
    stock: int = 10,
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
        },
    ).json()
    assert (
        client.post(
            f"/api/v1/admin/products/{product['id']}/prices",
            json={
                "price_type": "RETAIL",
                "amount": price,
                "starts_at": datetime.now(UTC).isoformat(),
            },
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/api/v1/admin/inventory",
            json={"product_id": product["id"]},
        ).status_code
        == 201
    )
    if stock:
        assert (
            client.post(
                f"/api/v1/admin/inventory/{product['id']}/purchase",
                json={"quantity": stock},
            ).status_code
            == 200
        )
    return product


def _add_to_cart(client: TestClient, customer: User, product_id: str, qty: int = 1) -> None:
    _login(client, customer)
    assert (
        client.post(
            "/api/v1/cart/items",
            json={"product_id": product_id, "quantity": qty},
        ).status_code
        == 200
    )


def test_checkout_success_creates_order_and_reserves(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    db_session: Session,
) -> None:
    product = _seed_sellable(client, admin_user, sku="CHK-OK", price="1199.99", stock=5)
    _add_to_cart(client, customer_user, product["id"], 2)

    response = client.post("/api/v1/checkout", json=_checkout_body())
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == OrderStatus.PENDING_PAYMENT.value
    assert body["order_number"].startswith("GEMA-")
    assert Decimal(str(body["subtotal"])) == Decimal("2399.9800")
    assert Decimal(str(body["total"])) == Decimal("2399.9800")
    assert Decimal(str(body["tax_total"])) == Decimal("0")
    assert len(body["items"]) == 1
    assert body["items"][0]["product_name"] == "Product CHK-OK"
    assert Decimal(str(body["items"][0]["unit_price"])) == Decimal("1199.9900")
    assert body["shipping_address"]["city"] == "Ibarra"
    assert body["shipping_address"]["recipient_name"] == "Buyer Test"
    assert body["customer_notes"] == "Entregar en horario laboral"

    order = db_session.get(Order, UUID(body["order_id"]))
    assert order is not None
    db_session.refresh(order)
    assert order.items[0].product_name_snapshot == "Product CHK-OK"
    assert order.items[0].sku_snapshot == "CHK-OK"
    assert order.shipping_address["city"] == "Ibarra"
    assert order.customer_notes == "Entregar en horario laboral"

    cart = db_session.scalar(
        select(Cart).where(Cart.id == order.cart_id)
    )
    assert cart is not None
    assert cart.status == CartStatus.CONVERTED.value

    db_session.expire_all()
    inv = db_session.scalar(
        select(Inventory).where(Inventory.product_id == UUID(product["id"]))
    )
    assert inv is not None
    assert inv.quantity == 5
    assert inv.reserved_quantity == 2

    reservations = list(
        db_session.scalars(
            select(InventoryReservation).where(
                InventoryReservation.order_id == order.id
            )
        ).all()
    )
    assert len(reservations) == 1
    assert reservations[0].quantity == 2
    assert reservations[0].status == "ACTIVE"
    assert reservations[0].expires_at is not None

    # active cart is gone; new get creates empty
    cart_resp = client.get("/api/v1/cart").json()
    assert cart_resp["items"] == []
    assert cart_resp["status"] == "ACTIVE"


def test_checkout_empty_cart(client: TestClient, customer_user: User) -> None:
    _login(client, customer_user)
    client.get("/api/v1/cart")
    assert client.post("/api/v1/checkout", json=_checkout_body()).status_code == 400


def test_checkout_inactive_product(
    client: TestClient, customer_user: User, admin_user: User
) -> None:
    product = _seed_sellable(client, admin_user, sku="CHK-INA")
    _add_to_cart(client, customer_user, product["id"])
    _login(client, admin_user)
    assert (
        client.patch(
            f"/api/v1/admin/products/{product['id']}",
            json={"is_active": False},
        ).status_code
        == 200
    )
    _login(client, customer_user)
    assert client.post("/api/v1/checkout", json=_checkout_body()).status_code == 409


def test_checkout_missing_price(
    client: TestClient, customer_user: User, admin_user: User
) -> None:
    _login(client, admin_user)
    category = client.post("/api/v1/admin/categories", json={"name": "NP"}).json()
    brand = client.post(
        "/api/v1/admin/brands",
        json={"name": "NP", "category_ids": [category["id"]]},
    ).json()
    product = client.post(
        "/api/v1/admin/products",
        json={
            "sku": "NOPRICE",
            "name": "No Price",
            "brand_id": brand["id"],
            "category_id": category["id"],
        },
    ).json()
    client.post("/api/v1/admin/inventory", json={"product_id": product["id"]})
    client.post(
        f"/api/v1/admin/inventory/{product['id']}/purchase",
        json={"quantity": 3},
    )
    _add_to_cart(client, customer_user, product["id"])
    assert client.post("/api/v1/checkout", json=_checkout_body()).status_code == 409


def test_checkout_detects_price_change_then_sync(
    client: TestClient, customer_user: User, admin_user: User
) -> None:
    product = _seed_sellable(client, admin_user, sku="CHK-PRC", price="350.00")
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
                "amount": "370.00",
                "starts_at": datetime.now(UTC).isoformat(),
            },
        ).status_code
        == 201
    )

    _login(client, customer_user)
    conflict = client.post("/api/v1/checkout", json=_checkout_body())
    assert conflict.status_code == 409, conflict.text
    detail = conflict.json()["detail"]
    assert detail["code"] == "PRICE_CHANGED"
    assert Decimal(str(detail["items"][0]["previous_unit_price"])) == Decimal("350.0000")
    assert Decimal(str(detail["items"][0]["current_unit_price"])) == Decimal("370.0000")

    synced = client.post("/api/v1/cart/sync-prices")
    assert synced.status_code == 200
    assert Decimal(str(synced.json()["items"][0]["unit_price"])) == Decimal("370.0000")

    body = client.post("/api/v1/checkout", json=_checkout_body()).json()
    assert Decimal(str(body["items"][0]["unit_price"])) == Decimal("370.0000")
    assert Decimal(str(body["total"])) == Decimal("370.0000")


def test_checkout_insufficient_stock(
    client: TestClient, customer_user: User, admin_user: User
) -> None:
    product = _seed_sellable(client, admin_user, sku="CHK-STK", stock=1)
    _add_to_cart(client, customer_user, product["id"], 2)
    assert client.post("/api/v1/checkout", json=_checkout_body()).status_code == 409


def test_checkout_rejects_converted_cart(
    client: TestClient, customer_user: User, admin_user: User
) -> None:
    product = _seed_sellable(client, admin_user, sku="CHK-CVT", stock=3)
    _add_to_cart(client, customer_user, product["id"])
    assert client.post("/api/v1/checkout", json=_checkout_body()).status_code == 200
    # empty new cart → 400; double checkout on same cart not possible via API
    assert client.post("/api/v1/checkout", json=_checkout_body()).status_code == 400


def test_overselling_sequential_last_unit(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    db_session: Session,
) -> None:
    product = _seed_sellable(client, admin_user, sku="CHK-LAST", stock=1)
    other = create_user_with_role(
        db_session,
        email="buyer2@example.com",
        password="secure-password",
        role_name=ROLE_CUSTOMER,
    )
    _add_to_cart(client, customer_user, product["id"], 1)
    assert client.post("/api/v1/checkout", json=_checkout_body()).status_code == 200

    _add_to_cart(client, other, product["id"], 1)
    assert client.post("/api/v1/checkout", json=_checkout_body()).status_code == 409


def test_customer_order_ownership(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    db_session: Session,
) -> None:
    product = _seed_sellable(client, admin_user, sku="CHK-OWN")
    _add_to_cart(client, customer_user, product["id"])
    order = client.post("/api/v1/checkout", json=_checkout_body()).json()

    other = create_user_with_role(
        db_session,
        email="nosy@example.com",
        password="secure-password",
        role_name=ROLE_CUSTOMER,
    )
    _login(client, other)
    assert client.get(f"/api/v1/orders/{order['order_id']}").status_code == 404
    assert (
        client.get(f"/api/v1/orders/by-number/{order['order_number']}").status_code
        == 404
    )

    _login(client, customer_user)
    mine = client.get(f"/api/v1/orders/{order['order_id']}")
    assert mine.status_code == 200
    assert mine.json()["order_number"] == order["order_number"]
    listed = client.get("/api/v1/orders").json()
    assert listed["total"] >= 1
    assert any(i["id"] == order["order_id"] for i in listed["items"])


def test_admin_can_list_orders(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    super_admin_user: User,
) -> None:
    product = _seed_sellable(client, admin_user, sku="CHK-ADM")
    _add_to_cart(client, customer_user, product["id"])
    order = client.post("/api/v1/checkout", json=_checkout_body()).json()

    _login(client, customer_user)
    assert client.get("/api/v1/admin/orders").status_code == 403

    _login(client, admin_user)
    admin_list = client.get("/api/v1/admin/orders")
    assert admin_list.status_code == 200
    assert any(i["id"] == order["order_id"] for i in admin_list.json()["items"])
    detail = client.get(f"/api/v1/admin/orders/{order['order_id']}")
    assert detail.status_code == 200
    assert detail.json()["customer_email"] == customer_user.email
    assert len(detail.json()["reservations"]) == 1

    _login(client, super_admin_user)
    assert client.get("/api/v1/admin/orders").status_code == 200


def test_unauthenticated_checkout(client: TestClient) -> None:
    assert client.post("/api/v1/checkout", json=_checkout_body()).status_code == 401
    assert client.get("/api/v1/orders").status_code == 401
