"""Admin order fulfillment transitions + authorization."""

from __future__ import annotations

from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.orders.models import Order, OrderStatus
from app.modules.payments.models import PaymentStatus
from app.modules.roles.models import User
from tests.test_orders_checkout import _checkout_body, _login, _seed_sellable
from tests.test_payments import _checkout_order


def _pay_manual(
    client: TestClient,
    customer: User,
    admin: User,
    *,
    sku: str,
) -> dict:
    data = _checkout_order(client, customer, admin, sku=sku, price="20.00")
    order_id = data["order"]["order_id"]
    _login(client, customer)
    pay = client.post(f"/api/v1/orders/{order_id}/payment", json={}).json()
    _login(client, admin)
    confirmed = client.post(
        f"/api/v1/admin/payments/{pay['id']}/confirm",
        params={"success": True},
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == PaymentStatus.SUCCEEDED.value
    return {"order_id": order_id, "payment_id": pay["id"]}


def test_admin_fulfillment_happy_path(
    client: TestClient, customer_user: User, admin_user: User, db_session: Session
) -> None:
    paid = _pay_manual(client, customer_user, admin_user, sku="FF-HAPPY")
    order_id = paid["order_id"]
    _login(client, admin_user)

    for target in ("PROCESSING", "SHIPPED", "DELIVERED"):
        res = client.patch(
            f"/api/v1/admin/orders/{order_id}/status",
            json={"status": target},
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["status"] == target
        assert target in [h["to_status"] for h in body["status_history"]]

    detail = client.get(f"/api/v1/admin/orders/{order_id}").json()
    assert detail["status"] == OrderStatus.DELIVERED.value
    assert detail["allowed_transitions"] == []
    assert len(detail["status_history"]) >= 4  # PAID + 3 fulfillment

    db_session.expire_all()
    order = db_session.get(Order, UUID(order_id))
    assert order is not None
    assert order.status == OrderStatus.DELIVERED.value


def test_customer_cannot_patch_fulfillment_status(
    client: TestClient, customer_user: User, admin_user: User
) -> None:
    paid = _pay_manual(client, customer_user, admin_user, sku="FF-CUST")
    _login(client, customer_user)
    res = client.patch(
        f"/api/v1/admin/orders/{paid['order_id']}/status",
        json={"status": "PROCESSING"},
    )
    assert res.status_code == 403


def test_invalid_transition_rejected(
    client: TestClient, customer_user: User, admin_user: User
) -> None:
    paid = _pay_manual(client, customer_user, admin_user, sku="FF-BAD")
    _login(client, admin_user)
    res = client.patch(
        f"/api/v1/admin/orders/{paid['order_id']}/status",
        json={"status": "SHIPPED"},
    )
    assert res.status_code == 409
    assert "Invalid transition" in res.json()["detail"]


def test_duplicate_transition_is_idempotent(
    client: TestClient, customer_user: User, admin_user: User, db_session: Session
) -> None:
    paid = _pay_manual(client, customer_user, admin_user, sku="FF-IDEM")
    order_id = paid["order_id"]
    _login(client, admin_user)
    first = client.patch(
        f"/api/v1/admin/orders/{order_id}/status",
        json={"status": "PROCESSING"},
    )
    assert first.status_code == 200
    history_len = len(first.json()["status_history"])
    second = client.patch(
        f"/api/v1/admin/orders/{order_id}/status",
        json={"status": "PROCESSING"},
    )
    assert second.status_code == 200
    assert second.json()["status"] == "PROCESSING"
    assert len(second.json()["status_history"]) == history_len


def test_cannot_cancel_paid_or_shipped_order(
    client: TestClient, customer_user: User, admin_user: User
) -> None:
    paid = _pay_manual(client, customer_user, admin_user, sku="FF-NOCANCEL")
    order_id = paid["order_id"]
    _login(client, admin_user)
    assert (
        client.post(f"/api/v1/admin/orders/{order_id}/cancel").status_code == 409
    )
    client.patch(
        f"/api/v1/admin/orders/{order_id}/status",
        json={"status": "PROCESSING"},
    )
    client.patch(
        f"/api/v1/admin/orders/{order_id}/status",
        json={"status": "SHIPPED"},
    )
    assert (
        client.post(f"/api/v1/admin/orders/{order_id}/cancel").status_code == 409
    )


def test_fulfillment_does_not_change_payment_status(
    client: TestClient, customer_user: User, admin_user: User
) -> None:
    paid = _pay_manual(client, customer_user, admin_user, sku="FF-PAY")
    _login(client, admin_user)
    client.patch(
        f"/api/v1/admin/orders/{paid['order_id']}/status",
        json={"status": "PROCESSING"},
    )
    payment = client.get(f"/api/v1/admin/payments/{paid['payment_id']}").json()
    assert payment["status"] == PaymentStatus.SUCCEEDED.value


def test_cannot_mark_paid_via_fulfillment_endpoint(
    client: TestClient, customer_user: User, admin_user: User
) -> None:
    product = _seed_sellable(client, admin_user, sku="FF-NOPAID")
    _login(client, customer_user)
    client.post(
        "/api/v1/cart/items",
        json={"product_id": product["id"], "quantity": 1},
    )
    order = client.post("/api/v1/checkout", json=_checkout_body()).json()
    _login(client, admin_user)
    res = client.patch(
        f"/api/v1/admin/orders/{order['order_id']}/status",
        json={"status": "PROCESSING"},
    )
    assert res.status_code == 409
    # PAID is not an allowed body value for the schema either
    bad = client.patch(
        f"/api/v1/admin/orders/{order['order_id']}/status",
        json={"status": "PAID"},
    )
    assert bad.status_code == 422
