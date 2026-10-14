from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.inventory.models import (
    Inventory,
    InventoryMovement,
    InventoryReservation,
    MovementType,
)
from app.modules.orders.models import Order, OrderStatus
from app.modules.payments.models import Payment, PaymentEvent, PaymentStatus
from app.modules.roles.models import User
from app.modules.roles.schemas import ROLE_CUSTOMER
from tests.conftest import admin_confirm_payment, create_user_with_role
from tests.test_orders_checkout import _add_to_cart, _checkout_body, _login, _seed_sellable


def _checkout_order(
    client: TestClient,
    customer: User,
    admin: User,
    *,
    sku: str = "PAY-OK",
    price: str = "1199.99",
    qty: int = 1,
    stock: int = 5,
) -> dict:
    product = _seed_sellable(client, admin, sku=sku, price=price, stock=stock)
    _add_to_cart(client, customer, product["id"], qty)
    response = client.post("/api/v1/checkout", json=_checkout_body())
    assert response.status_code == 200, response.text
    return {"order": response.json(), "product": product}


def _webhook(
    client: TestClient,
    *,
    payment_id: str,
    event_id: str,
    event_type: str = "payment.succeeded",
    secret: str | None = None,
) -> object:
    return client.post(
        "/api/v1/payments/webhooks/manual",
        headers={"X-GEMA-Payment-Secret": secret or settings.payment_webhook_secret},
        json={
            "event_id": event_id,
            "event_type": event_type,
            "payment_id": payment_id,
        },
    )


def test_create_payment_uses_order_total_and_usd(
    client: TestClient,
    customer_user: User,
    admin_user: User,
) -> None:
    data = _checkout_order(client, customer_user, admin_user)
    order = data["order"]
    _login(client, customer_user)

    response = client.post(f"/api/v1/orders/{order['order_id']}/payment", json={})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["payment_id"] == body["id"]
    assert body["order_id"] == order["order_id"]
    assert body["order_number"] == order["order_number"]
    assert body["status"] in {PaymentStatus.PENDING.value, PaymentStatus.PROCESSING.value}
    assert Decimal(str(body["amount"])) == Decimal(str(order["total"]))
    assert body["currency"] == "USD"
    assert body["provider"] == "manual"
    assert "amount" not in (response.request.content.decode() if response.request.content else "")


def test_create_payment_rejects_paid_and_cancelled(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    db_session: Session,
) -> None:
    data = _checkout_order(client, customer_user, admin_user, sku="PAY-PAID")
    order_id = UUID(data["order"]["order_id"])
    _login(client, customer_user)
    pay = client.post(f"/api/v1/orders/{order_id}/payment", json={}).json()
    assert admin_confirm_payment(
        client, admin_user, pay["id"], restore_user=customer_user
    ).status_code == 200

    again = client.post(f"/api/v1/orders/{order_id}/payment", json={})
    assert again.status_code == 409

    data2 = _checkout_order(client, customer_user, admin_user, sku="PAY-CAN")
    cancelled_id = UUID(data2["order"]["order_id"])
    order = db_session.get(Order, cancelled_id)
    assert order is not None
    order.status = OrderStatus.CANCELLED.value
    db_session.commit()
    _login(client, customer_user)
    assert client.post(f"/api/v1/orders/{cancelled_id}/payment", json={}).status_code == 409


def test_payment_ownership(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    db_session: Session,
) -> None:
    other = create_user_with_role(
        db_session,
        email="other-pay@example.com",
        password="secure-password",
        role_name=ROLE_CUSTOMER,
    )
    data = _checkout_order(client, customer_user, admin_user, sku="PAY-OWN")
    order_id = data["order"]["order_id"]
    _login(client, customer_user)
    payment = client.post(f"/api/v1/orders/{order_id}/payment", json={}).json()

    _login(client, other)
    assert client.post(f"/api/v1/orders/{order_id}/payment", json={}).status_code == 404
    assert client.get(f"/api/v1/payments/{payment['id']}").status_code == 404
    assert client.get(f"/api/v1/orders/{order_id}/payments").status_code == 404
    assert client.get(f"/api/v1/admin/payments/{payment['id']}").status_code == 403
    assert (
        client.post(f"/api/v1/admin/payments/{payment['id']}/confirm?success=true").status_code
        == 403
    )
    assert client.post(f"/api/v1/payments/{payment['id']}/confirm?success=true").status_code == 404


def test_payment_success_consumes_reservation_once(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    db_session: Session,
) -> None:
    data = _checkout_order(
        client, customer_user, admin_user, sku="PAY-SUC", price="50.00", qty=2, stock=10
    )
    order_id = UUID(data["order"]["order_id"])
    product_id = UUID(data["product"]["id"])
    _login(client, customer_user)
    payment = client.post(f"/api/v1/orders/{order_id}/payment", json={}).json()

    ok = admin_confirm_payment(client, admin_user, payment["id"])
    assert ok.status_code == 200, ok.text
    assert ok.json()["status"] == PaymentStatus.SUCCEEDED.value

    db_session.expire_all()
    order = db_session.get(Order, order_id)
    assert order is not None
    assert order.status == OrderStatus.PAID.value

    inv = db_session.scalar(select(Inventory).where(Inventory.product_id == product_id))
    assert inv is not None
    assert inv.quantity == 8
    assert inv.reserved_quantity == 0

    reservations = list(
        db_session.scalars(
            select(InventoryReservation).where(InventoryReservation.order_id == order_id)
        ).all()
    )
    assert len(reservations) == 1
    assert reservations[0].status == "CONSUMED"

    movements = list(
        db_session.scalars(
            select(InventoryMovement).where(
                InventoryMovement.reference_type == "order",
                InventoryMovement.reference_id == str(order_id),
                InventoryMovement.type == MovementType.SALE.value,
            )
        ).all()
    )
    assert len(movements) == 1
    assert movements[0].quantity == 2

    # Idempotent confirm
    again = admin_confirm_payment(client, admin_user, payment["id"])
    assert again.status_code == 200
    assert again.json()["status"] == PaymentStatus.SUCCEEDED.value

    db_session.expire_all()
    movements2 = list(
        db_session.scalars(
            select(InventoryMovement).where(
                InventoryMovement.reference_type == "order",
                InventoryMovement.reference_id == str(order_id),
                InventoryMovement.type == MovementType.SALE.value,
            )
        ).all()
    )
    assert len(movements2) == 1


def test_payment_failure_releases_reservation_keeps_order_pending(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    db_session: Session,
) -> None:
    data = _checkout_order(client, customer_user, admin_user, sku="PAY-FAIL", qty=1, stock=4)
    order_id = UUID(data["order"]["order_id"])
    product_id = UUID(data["product"]["id"])
    _login(client, customer_user)
    payment = client.post(f"/api/v1/orders/{order_id}/payment", json={}).json()

    fail = admin_confirm_payment(client, admin_user, payment["id"], success=False)
    assert fail.status_code == 200
    assert fail.json()["status"] == PaymentStatus.FAILED.value

    db_session.expire_all()
    order = db_session.get(Order, order_id)
    assert order is not None
    assert order.status == OrderStatus.PENDING_PAYMENT.value

    inv = db_session.scalar(select(Inventory).where(Inventory.product_id == product_id))
    assert inv is not None
    assert inv.quantity == 4
    assert inv.reserved_quantity == 0

    reservations = list(
        db_session.scalars(
            select(InventoryReservation).where(InventoryReservation.order_id == order_id)
        ).all()
    )
    assert reservations[0].status == "RELEASED"

    movements = list(
        db_session.scalars(
            select(InventoryMovement).where(
                InventoryMovement.reference_type == "order",
                InventoryMovement.reference_id == str(order_id),
                InventoryMovement.type == MovementType.SALE.value,
            )
        ).all()
    )
    assert movements == []


def test_multiple_attempts_then_success(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    db_session: Session,
) -> None:
    data = _checkout_order(client, customer_user, admin_user, sku="PAY-MULTI")
    order_id = data["order"]["order_id"]
    product_id = UUID(data["product"]["id"])
    _login(client, customer_user)

    p1 = client.post(f"/api/v1/orders/{order_id}/payment", json={}).json()
    assert (
        admin_confirm_payment(
            client, admin_user, p1["id"], success=False, restore_user=customer_user
        ).status_code
        == 200
    )
    db_session.expire_all()
    inv = db_session.scalar(select(Inventory).where(Inventory.product_id == product_id))
    assert inv is not None
    assert inv.reserved_quantity == 0

    p2 = client.post(f"/api/v1/orders/{order_id}/payment", json={}).json()
    db_session.expire_all()
    inv = db_session.scalar(select(Inventory).where(Inventory.product_id == product_id))
    assert inv is not None
    assert inv.reserved_quantity == 1
    assert (
        admin_confirm_payment(
            client, admin_user, p2["id"], success=False, restore_user=customer_user
        ).status_code
        == 200
    )
    p3 = client.post(f"/api/v1/orders/{order_id}/payment", json={}).json()
    assert admin_confirm_payment(
        client, admin_user, p3["id"], restore_user=customer_user
    ).status_code == 200

    history = client.get(f"/api/v1/orders/{order_id}/payments").json()["items"]
    assert len(history) == 3
    by_id = {item["id"]: item["status"] for item in history}
    assert by_id[p1["id"]] == PaymentStatus.FAILED.value
    assert by_id[p2["id"]] == PaymentStatus.FAILED.value
    assert by_id[p3["id"]] == PaymentStatus.SUCCEEDED.value

    blocked = client.post(f"/api/v1/orders/{order_id}/payment", json={})
    assert blocked.status_code == 409

    db_session.expire_all()
    order = db_session.get(Order, UUID(order_id))
    assert order is not None
    assert order.status == OrderStatus.PAID.value


def test_webhook_success_and_idempotency(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    db_session: Session,
) -> None:
    data = _checkout_order(client, customer_user, admin_user, sku="PAY-WH")
    order_id = UUID(data["order"]["order_id"])
    _login(client, customer_user)
    payment = client.post(f"/api/v1/orders/{order_id}/payment", json={}).json()

    # no auth required for webhook; secret is the auth
    client.cookies.clear()
    first = _webhook(client, payment_id=payment["id"], event_id="evt-1")
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "processed"

    second = _webhook(client, payment_id=payment["id"], event_id="evt-1")
    assert second.status_code == 200
    assert second.json()["status"] == "already_processed"

    db_session.expire_all()
    events = list(
        db_session.scalars(
            select(PaymentEvent).where(PaymentEvent.provider_event_id == "evt-1")
        ).all()
    )
    assert len(events) == 1

    movements_count = db_session.scalar(
        select(func.count()).select_from(InventoryMovement).where(
            InventoryMovement.reference_type == "order",
            InventoryMovement.reference_id == str(order_id),
            InventoryMovement.type == MovementType.SALE.value,
        )
    )
    assert movements_count == 1

    order = db_session.get(Order, order_id)
    assert order is not None
    assert order.status == OrderStatus.PAID.value


def test_webhook_invalid_secret(
    client: TestClient,
    customer_user: User,
    admin_user: User,
) -> None:
    data = _checkout_order(client, customer_user, admin_user, sku="PAY-SEC")
    _login(client, customer_user)
    payment = client.post(
        f"/api/v1/orders/{data['order']['order_id']}/payment", json={}
    ).json()
    client.cookies.clear()
    bad = _webhook(
        client,
        payment_id=payment["id"],
        event_id="evt-bad",
        secret="wrong-secret",
    )
    assert bad.status_code == 401


def test_webhook_failure(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    db_session: Session,
) -> None:
    data = _checkout_order(client, customer_user, admin_user, sku="PAY-WHF")
    order_id = UUID(data["order"]["order_id"])
    product_id = UUID(data["product"]["id"])
    _login(client, customer_user)
    payment = client.post(f"/api/v1/orders/{order_id}/payment", json={}).json()
    client.cookies.clear()
    resp = _webhook(
        client,
        payment_id=payment["id"],
        event_id="evt-fail",
        event_type="payment.failed",
    )
    assert resp.status_code == 200

    db_session.expire_all()
    pay = db_session.get(Payment, UUID(payment["id"]))
    assert pay is not None
    assert pay.status == PaymentStatus.FAILED.value
    order = db_session.get(Order, order_id)
    assert order is not None
    assert order.status == OrderStatus.PENDING_PAYMENT.value
    inv = db_session.scalar(select(Inventory).where(Inventory.product_id == product_id))
    assert inv is not None
    assert inv.reserved_quantity == 0
    reservation = db_session.scalar(
        select(InventoryReservation).where(InventoryReservation.order_id == order_id)
    )
    assert reservation is not None
    assert reservation.status == "RELEASED"


def test_admin_payments(
    client: TestClient,
    customer_user: User,
    admin_user: User,
) -> None:
    data = _checkout_order(client, customer_user, admin_user, sku="PAY-ADM")
    _login(client, customer_user)
    payment = client.post(
        f"/api/v1/orders/{data['order']['order_id']}/payment", json={}
    ).json()

    _login(client, admin_user)
    listed = client.get("/api/v1/admin/payments")
    assert listed.status_code == 200
    ids = {item["id"] for item in listed.json()["items"]}
    assert payment["id"] in ids

    detail = client.get(f"/api/v1/admin/payments/{payment['id']}")
    assert detail.status_code == 200
    assert detail.json()["id"] == payment["id"]


def test_second_success_webhook_does_not_double_consume(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    db_session: Session,
) -> None:
    data = _checkout_order(client, customer_user, admin_user, sku="PAY-DBL", qty=1, stock=3)
    order_id = UUID(data["order"]["order_id"])
    product_id = UUID(data["product"]["id"])
    _login(client, customer_user)
    p1 = client.post(f"/api/v1/orders/{order_id}/payment", json={}).json()
    client.cookies.clear()
    assert _webhook(client, payment_id=p1["id"], event_id="evt-a").status_code == 200

    # Simulate a second payment that somehow gets a late success (should not consume again)
    _login(client, customer_user)
    # order is paid — cannot create; create orphan via DB for concurrency edge
    from app.modules.payments.models import PaymentMethod

    orphan = Payment(
        order_id=order_id,
        provider="manual",
        provider_payment_id="manual_orphan",
        method=PaymentMethod.CARD.value,
        status=PaymentStatus.PROCESSING.value,
        amount=Decimal("1199.9900"),
        currency="USD",
        metadata_json={},
    )
    db_session.add(orphan)
    db_session.commit()
    orphan_id = str(orphan.id)

    client.cookies.clear()
    resp = _webhook(client, payment_id=orphan_id, event_id="evt-b")
    assert resp.status_code == 200

    db_session.expire_all()
    orphan_loaded = db_session.get(Payment, UUID(orphan_id))
    assert orphan_loaded is not None
    assert orphan_loaded.status == PaymentStatus.FAILED.value

    inv = db_session.scalar(select(Inventory).where(Inventory.product_id == product_id))
    assert inv is not None
    assert inv.quantity == 2
    movements_count = db_session.scalar(
        select(func.count()).select_from(InventoryMovement).where(
            InventoryMovement.reference_type == "order",
            InventoryMovement.reference_id == str(order_id),
            InventoryMovement.type == MovementType.SALE.value,
        )
    )
    assert movements_count == 1
