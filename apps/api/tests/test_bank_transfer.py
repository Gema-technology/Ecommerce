"""Offline bank transfer flow — instructions, mark transferred, admin confirm."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.orders.models import Order, OrderStatus
from app.modules.payments.models import Payment, PaymentStatus
from app.modules.roles.models import User
from tests.conftest import admin_confirm_payment, login_as
from tests.test_orders_checkout import _login
from tests.test_payments import _checkout_order


@pytest.fixture()
def bank_env(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core import config as config_mod

    monkeypatch.setattr(config_mod.settings, "bank_name", "Banco Pichincha")
    monkeypatch.setattr(config_mod.settings, "bank_account_type", "Ahorros")
    monkeypatch.setattr(config_mod.settings, "bank_account_number", "2201234567")
    monkeypatch.setattr(config_mod.settings, "bank_account_holder", "GEMA Technology")
    monkeypatch.setattr(config_mod.settings, "bank_account_id", "1790000000001")
    monkeypatch.setattr(
        config_mod.settings,
        "bank_transfer_instructions",
        "Usa el número de orden como referencia.",
    )


def test_bank_transfer_requires_configuration(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core import config as config_mod

    monkeypatch.setattr(config_mod.settings, "bank_name", "")
    monkeypatch.setattr(config_mod.settings, "bank_account_number", "")
    monkeypatch.setattr(config_mod.settings, "bank_account_holder", "")

    data = _checkout_order(client, customer_user, admin_user, sku="BT-CFG", price="10.00")
    _login(client, customer_user)
    response = client.post(
        f"/api/v1/orders/{data['order']['order_id']}/payment",
        json={"method": "BANK_TRANSFER"},
    )
    assert response.status_code == 503
    assert "Bank transfer is not configured" in response.json()["detail"]


def test_bank_transfer_create_shows_instructions(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    bank_env: None,
) -> None:
    data = _checkout_order(client, customer_user, admin_user, sku="BT-OK", price="15.00")
    _login(client, customer_user)
    response = client.post(
        f"/api/v1/orders/{data['order']['order_id']}/payment",
        json={"method": "BANK_TRANSFER"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["provider"] == "bank_transfer"
    assert body["method"] == "BANK_TRANSFER"
    assert body["status"] == PaymentStatus.PROCESSING.value
    action = body["client_action"]
    assert action["type"] == "bank_transfer_instructions"
    assert action["bank"]["bank_name"] == "Banco Pichincha"
    assert action["bank"]["account_number"] == "2201234567"
    assert action["reference"] == data["order"]["order_number"]
    assert Decimal(str(body["amount"])) == Decimal(str(data["order"]["total"]))


def test_bank_transfer_mark_and_admin_confirm(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    db_session: Session,
    bank_env: None,
) -> None:
    data = _checkout_order(client, customer_user, admin_user, sku="BT-CFM", price="12.00")
    order_id = UUID(data["order"]["order_id"])
    _login(client, customer_user)
    pay = client.post(
        f"/api/v1/orders/{order_id}/payment",
        json={"method": "BANK_TRANSFER"},
    ).json()

    marked = client.post(f"/api/v1/payments/{pay['id']}/mark-transferred")
    assert marked.status_code == 200, marked.text
    assert marked.json()["client_action"]["customer_marked_transferred"] is True

    confirm = admin_confirm_payment(
        client, admin_user, pay["id"], restore_user=customer_user
    )
    assert confirm.status_code == 200, confirm.text
    assert confirm.json()["status"] == PaymentStatus.SUCCEEDED.value

    db_session.expire_all()
    order = db_session.get(Order, order_id)
    assert order is not None
    assert order.status == OrderStatus.PAID.value
    payment = db_session.get(Payment, UUID(pay["id"]))
    assert payment is not None
    assert payment.status == PaymentStatus.SUCCEEDED.value


def test_bank_transfer_admin_confirm_allowed_in_production(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    bank_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core import config as config_mod

    data = _checkout_order(client, customer_user, admin_user, sku="BT-PROD", price="9.00")
    _login(client, customer_user)
    pay = client.post(
        f"/api/v1/orders/{data['order']['order_id']}/payment",
        json={"method": "BANK_TRANSFER"},
    ).json()

    # Simulate production offline-confirm policy without Secure cookies (TestClient is HTTP).
    monkeypatch.setattr(config_mod.settings, "app_env", "production")
    monkeypatch.setattr(config_mod.settings, "allow_manual_payment_confirm", False)
    monkeypatch.setattr(config_mod.settings, "session_cookie_secure", False)

    confirm = admin_confirm_payment(client, admin_user, pay["id"])
    assert confirm.status_code == 200, confirm.text
    assert confirm.json()["status"] == PaymentStatus.SUCCEEDED.value


def test_card_still_uses_default_provider(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    bank_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """BANK_TRANSFER is offline; CARD keeps PAYMENT_DEFAULT_PROVIDER (manual in tests)."""
    from app.core import config as config_mod

    monkeypatch.setattr(config_mod.settings, "payment_default_provider", "manual")
    data = _checkout_order(client, customer_user, admin_user, sku="BT-CARD", price="11.00")
    _login(client, customer_user)
    response = client.post(
        f"/api/v1/orders/{data['order']['order_id']}/payment",
        json={"method": "CARD"},
    )
    assert response.status_code == 200
    assert response.json()["provider"] == "manual"
