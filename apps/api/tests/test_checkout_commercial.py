"""Commercial checkout: shipping, tax, totals, preview, snapshots."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.orders.models import Order, OrderStatus
from app.modules.roles.models import User
from tests.test_orders_checkout import (
    _add_to_cart,
    _checkout_body,
    _login,
    _seed_sellable,
)


def test_checkout_preview_with_shipping(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "shipping_flat_rate", Decimal("5.00"))
    monkeypatch.setattr(settings, "shipping_free_threshold", Decimal("500.00"))
    product = _seed_sellable(client, admin_user, sku="PREV-SHP", price="50.00", stock=5)
    _add_to_cart(client, customer_user, product["id"], 1)
    _login(client, customer_user)

    preview = client.post(
        "/api/v1/checkout/preview",
        json={"shipping_address": _checkout_body()["shipping_address"]},
    )
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert Decimal(str(body["subtotal"])) == Decimal("50.0000")
    assert Decimal(str(body["shipping_total"])) == Decimal("5.0000")
    assert Decimal(str(body["total"])) == Decimal("55.0000")
    assert body["shipping_method"] == "standard"


def test_checkout_preview_free_shipping_above_threshold(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "shipping_free_threshold", Decimal("100.00"))
    product = _seed_sellable(client, admin_user, sku="PREV-FREE", price="150.00", stock=3)
    _add_to_cart(client, customer_user, product["id"], 1)
    _login(client, customer_user)

    preview = client.post("/api/v1/checkout/preview", json={})
    assert preview.status_code == 200
    assert Decimal(str(preview.json()["shipping_total"])) == Decimal("0.0000")
    assert preview.json()["shipping_method"] == "free"


def test_checkout_total_includes_shipping(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    monkeypatch,
    db_session: Session,
) -> None:
    monkeypatch.setattr(settings, "shipping_flat_rate", Decimal("5.00"))
    monkeypatch.setattr(settings, "shipping_free_threshold", Decimal("500.00"))
    product = _seed_sellable(client, admin_user, sku="CHK-SHP", price="50.00", stock=3)
    _add_to_cart(client, customer_user, product["id"], 1)
    _login(client, customer_user)

    response = client.post("/api/v1/checkout", json=_checkout_body())
    assert response.status_code == 200, response.text
    body = response.json()
    assert Decimal(str(body["shipping_total"])) == Decimal("5.0000")
    assert Decimal(str(body["total"])) == Decimal("55.0000")

    order = db_session.get(Order, UUID(body["order_id"]))
    assert order is not None
    assert order.customer_email == customer_user.email
    assert order.customer_name == "Buyer Test"
    assert order.customer_phone == "0999999999"


def test_checkout_rejects_invalid_phone(
    client: TestClient,
    customer_user: User,
    admin_user: User,
) -> None:
    product = _seed_sellable(client, admin_user, sku="CHK-PHN", price="10.00")
    _add_to_cart(client, customer_user, product["id"])
    _login(client, customer_user)
    body = _checkout_body()
    body["shipping_address"]["phone"] = "123"
    response = client.post("/api/v1/checkout", json=body)
    assert response.status_code == 422


def test_checkout_rejects_invalid_address(
    client: TestClient,
    customer_user: User,
    admin_user: User,
) -> None:
    product = _seed_sellable(client, admin_user, sku="CHK-ADDR", price="10.00")
    _add_to_cart(client, customer_user, product["id"])
    _login(client, customer_user)
    body = _checkout_body()
    body["shipping_address"]["address_line"] = "   "
    response = client.post("/api/v1/checkout", json=body)
    assert response.status_code == 422


def test_checkout_tax_when_enabled(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "commerce_tax_enabled", True)
    monkeypatch.setattr(settings, "commerce_tax_rate", Decimal("0.15"))
    monkeypatch.setattr(settings, "shipping_free_threshold", Decimal("1000.00"))
    monkeypatch.setattr(settings, "shipping_flat_rate", Decimal("0.00"))
    product = _seed_sellable(client, admin_user, sku="CHK-TAX", price="100.00", stock=2)
    _add_to_cart(client, customer_user, product["id"], 1)
    _login(client, customer_user)

    preview = client.post("/api/v1/checkout/preview", json={})
    assert preview.status_code == 200
    body = preview.json()
    assert Decimal(str(body["tax_total"])) == Decimal("15.0000")
    assert Decimal(str(body["total"])) == Decimal("115.0000")

    checkout = client.post("/api/v1/checkout", json=_checkout_body())
    assert checkout.status_code == 200
    assert Decimal(str(checkout.json()["tax_total"])) == Decimal("15.0000")


def test_order_snapshot_persists_after_user_change(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    db_session: Session,
) -> None:
    product = _seed_sellable(client, admin_user, sku="CHK-SNAP", price="25.00")
    _add_to_cart(client, customer_user, product["id"])
    _login(client, customer_user)
    order = client.post("/api/v1/checkout", json=_checkout_body()).json()

    customer_user.email = "changed@example.com"
    customer_user.first_name = "Changed"
    db_session.commit()

    _login(client, customer_user)
    detail = client.get(f"/api/v1/orders/{order['order_id']}").json()
    assert detail["customer_email"] == "customer@example.com"
    assert detail["customer_name"] == "Buyer Test"
    assert detail["shipping_address"]["city"] == "Ibarra"
    assert detail["customer_notes"] == "Entregar en horario laboral"
