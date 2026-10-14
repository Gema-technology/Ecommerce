"""Cash on delivery — trusted customers only."""

from __future__ import annotations

from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.orders.models import Order, OrderStatus
from app.modules.payments.models import PaymentStatus
from app.modules.roles.models import User
from tests.conftest import admin_confirm_payment, login_as
from tests.test_orders_checkout import _login
from tests.test_payments import _checkout_order


def test_cod_forbidden_without_trust(
    client: TestClient,
    customer_user: User,
    admin_user: User,
) -> None:
    data = _checkout_order(client, customer_user, admin_user, sku="COD-NO", price="20.00")
    _login(client, customer_user)
    response = client.post(
        f"/api/v1/orders/{data['order']['order_id']}/payment",
        json={"method": "CASH_ON_DELIVERY"},
    )
    assert response.status_code == 403
    assert "trusted" in response.json()["detail"].lower()


def test_cod_allowed_for_trusted_customer(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    db_session: Session,
) -> None:
    customer_user.allow_cash_on_delivery = True
    db_session.commit()

    data = _checkout_order(client, customer_user, admin_user, sku="COD-OK", price="18.00")
    order_id = UUID(data["order"]["order_id"])
    _login(client, customer_user)
    response = client.post(
        f"/api/v1/orders/{order_id}/payment",
        json={"method": "CASH_ON_DELIVERY"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["provider"] == "cash_on_delivery"
    assert body["method"] == "CASH_ON_DELIVERY"
    assert body["client_action"]["type"] == "cash_on_delivery_pending"

    confirm = admin_confirm_payment(
        client, admin_user, body["id"], restore_user=customer_user
    )
    assert confirm.status_code == 200
    assert confirm.json()["status"] == PaymentStatus.SUCCEEDED.value

    db_session.expire_all()
    order = db_session.get(Order, order_id)
    assert order is not None
    assert order.status == OrderStatus.PAID.value


def test_admin_can_toggle_cod_whitelist(
    client: TestClient,
    customer_user: User,
    admin_user: User,
) -> None:
    login_as(client, admin_user)
    listed = client.get("/api/v1/admin/customers")
    assert listed.status_code == 200
    row = next(u for u in listed.json()["items"] if u["id"] == str(customer_user.id))
    assert row["allow_cash_on_delivery"] is False

    enabled = client.patch(
        f"/api/v1/admin/customers/{customer_user.id}/cash-on-delivery",
        json={"allow_cash_on_delivery": True},
    )
    assert enabled.status_code == 200
    assert enabled.json()["allow_cash_on_delivery"] is True

    me = login_as(client, customer_user)
    _ = me
    profile = client.get("/api/v1/auth/me")
    assert profile.status_code == 200
    assert profile.json()["allow_cash_on_delivery"] is True
