"""Transactional email: claim/dedupe, SMTP failure isolation, event hooks."""

from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import config as config_mod
from app.modules.notifications.models import NotificationDispatch
from app.modules.notifications.service import (
    EVENT_ORDER_CREATED,
    EVENT_ORDER_PAID,
    NotificationService,
    set_email_transport,
)
from app.modules.notifications.smtp import MemoryTransport
from app.modules.orders.models import Order
from app.modules.roles.models import User
from tests.test_order_fulfillment import _pay_manual
from tests.test_orders_checkout import _checkout_body, _login, _seed_sellable
from tests.test_payments import _checkout_order


@pytest.fixture
def memory_mail(monkeypatch: pytest.MonkeyPatch):
    transport = MemoryTransport()
    set_email_transport(transport)
    monkeypatch.setattr(config_mod.settings, "email_enabled", True)
    monkeypatch.setattr(config_mod.settings, "smtp_host", "smtp.test.local")
    monkeypatch.setattr(config_mod.settings, "smtp_from", "noreply@example.com")
    monkeypatch.setattr(config_mod.settings, "public_app_url", "http://localhost:3000")
    yield transport
    set_email_transport(None)


def test_checkout_sends_order_created_once(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    db_session: Session,
    memory_mail: MemoryTransport,
) -> None:
    product = _seed_sellable(client, admin_user, sku="MAIL-CREATE")
    _login(client, customer_user)
    client.post(
        "/api/v1/cart/items",
        json={"product_id": product["id"], "quantity": 1},
    )
    order = client.post("/api/v1/checkout", json=_checkout_body()).json()
    assert len(memory_mail.sent) == 1
    assert "Pedido recibido" in memory_mail.sent[0].subject
    assert order["order_number"] in memory_mail.sent[0].text_body

    # Manual re-notify is deduped.
    NotificationService(db_session, transport=memory_mail).notify_order_event(
        db_session.get(Order, UUID(order["order_id"])),  # type: ignore[arg-type]
        EVENT_ORDER_CREATED,
    )
    assert len(memory_mail.sent) == 1


def test_payment_confirm_sends_paid_email(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    db_session: Session,
    memory_mail: MemoryTransport,
) -> None:
    paid = _pay_manual(client, customer_user, admin_user, sku="MAIL-PAID")
    subjects = [m.subject for m in memory_mail.sent]
    assert any("Pago confirmado" in s for s in subjects)

    rows = list(
        db_session.scalars(
            select(NotificationDispatch).where(
                NotificationDispatch.order_id == UUID(paid["order_id"]),
                NotificationDispatch.event_key == EVENT_ORDER_PAID,
            )
        ).all()
    )
    assert len(rows) == 1
    assert rows[0].status == "accepted"


def test_shipped_transition_sends_email(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    memory_mail: MemoryTransport,
) -> None:
    paid = _pay_manual(client, customer_user, admin_user, sku="MAIL-SHIP")
    _login(client, admin_user)
    client.patch(
        f"/api/v1/admin/orders/{paid['order_id']}/status",
        json={"status": "PROCESSING"},
    )
    before = len(memory_mail.sent)
    ship = client.patch(
        f"/api/v1/admin/orders/{paid['order_id']}/status",
        json={"status": "SHIPPED"},
    )
    assert ship.status_code == 200
    assert len(memory_mail.sent) == before + 1
    last = memory_mail.sent[-1]
    assert "enviado" in last.subject.lower() or "enviado" in last.text_body.lower()


def test_smtp_failure_does_not_block_payment(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transport = MemoryTransport()
    transport.fail_next = True
    # Fail on paid email specifically: allow created, fail paid.
    set_email_transport(transport)
    monkeypatch.setattr(config_mod.settings, "email_enabled", True)
    monkeypatch.setattr(config_mod.settings, "smtp_host", "smtp.test.local")
    monkeypatch.setattr(config_mod.settings, "smtp_from", "noreply@example.com")

    data = _checkout_order(client, customer_user, admin_user, sku="MAIL-FAIL", price="12.00")
    # created succeeded; force next send (paid) to fail
    transport.fail_next = True
    order_id = data["order"]["order_id"]
    _login(client, customer_user)
    pay = client.post(f"/api/v1/orders/{order_id}/payment", json={}).json()
    _login(client, admin_user)
    confirmed = client.post(
        f"/api/v1/admin/payments/{pay['id']}/confirm",
        params={"success": True},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "SUCCEEDED"

    db_session.expire_all()
    order = db_session.get(Order, UUID(order_id))
    assert order is not None
    assert order.status == "PAID"

    failed = list(
        db_session.scalars(
            select(NotificationDispatch).where(
                NotificationDispatch.order_id == UUID(order_id),
                NotificationDispatch.event_key == EVENT_ORDER_PAID,
            )
        ).all()
    )
    assert len(failed) == 1
    assert failed[0].status == "failed"
    set_email_transport(None)


def test_email_disabled_skips_without_error(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transport = MemoryTransport()
    set_email_transport(transport)
    monkeypatch.setattr(config_mod.settings, "email_enabled", False)
    monkeypatch.setattr(config_mod.settings, "smtp_host", "smtp.test.local")
    monkeypatch.setattr(config_mod.settings, "smtp_from", "noreply@example.com")

    product = _seed_sellable(client, admin_user, sku="MAIL-OFF")
    _login(client, customer_user)
    client.post(
        "/api/v1/cart/items",
        json={"product_id": product["id"], "quantity": 1},
    )
    order = client.post("/api/v1/checkout", json=_checkout_body()).json()
    assert len(transport.sent) == 0

    row = db_session.scalar(
        select(NotificationDispatch).where(
            NotificationDispatch.order_id == UUID(order["order_id"]),
            NotificationDispatch.event_key == EVENT_ORDER_CREATED,
        )
    )
    assert row is not None
    assert row.status == "skipped"
    assert row.detail == "email_disabled"
    set_email_transport(None)


def test_duplicate_paid_event_does_not_resend(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    db_session: Session,
    memory_mail: MemoryTransport,
) -> None:
    paid = _pay_manual(client, customer_user, admin_user, sku="MAIL-DUP")
    paid_count = sum(1 for m in memory_mail.sent if "Pago confirmado" in m.subject)
    assert paid_count == 1
    order = db_session.get(Order, UUID(paid["order_id"]))
    assert order is not None
    NotificationService(db_session, transport=memory_mail).notify_order_event(
        order, EVENT_ORDER_PAID
    )
    paid_count2 = sum(1 for m in memory_mail.sent if "Pago confirmado" in m.subject)
    assert paid_count2 == 1


def test_shipped_idempotent_does_not_duplicate_email(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    memory_mail: MemoryTransport,
) -> None:
    paid = _pay_manual(client, customer_user, admin_user, sku="MAIL-SHIP2")
    _login(client, admin_user)
    client.patch(
        f"/api/v1/admin/orders/{paid['order_id']}/status",
        json={"status": "PROCESSING"},
    )
    client.patch(
        f"/api/v1/admin/orders/{paid['order_id']}/status",
        json={"status": "SHIPPED"},
    )
    shipped_count = sum(
        1 for m in memory_mail.sent if "enviado" in m.subject.lower()
    )
    before = len(memory_mail.sent)
    client.patch(
        f"/api/v1/admin/orders/{paid['order_id']}/status",
        json={"status": "SHIPPED"},
    )
    assert len(memory_mail.sent) == before
    assert shipped_count >= 1
