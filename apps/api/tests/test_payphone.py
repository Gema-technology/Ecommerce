"""PayPhone (Ecuador) provider — link creation, webhook, sync."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.orders.models import Order, OrderStatus
from app.modules.payments.models import Payment, PaymentStatus
from app.modules.payments.providers.base import OrderAmountBreakdown
from app.modules.payments.providers.payphone import (
    PayPhonePaymentProvider,
    build_link_amounts,
    client_transaction_id_for,
    money_to_cents,
)
from app.modules.payments.providers.payphone_client import PayPhoneApiError
from app.modules.roles.models import User
from tests.test_orders_checkout import _login
from tests.test_payments import _checkout_order


class _FakePayPhoneClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, Any] | None]] = []
        self.link_response: Any = "https://payp.page.link/test-gema"
        self.sale_response: Any = {
            "statusCode": 3,
            "transactionId": 991122,
            "clientTransactionId": "",
            "Amount": None,
            "amount": None,
        }
        self.raise_on: str | None = None

    def request(
        self,
        method: str,
        path: str,
        *,
        token: str,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        _ = token
        self.calls.append((method, path, json_body))
        if self.raise_on == path:
            raise PayPhoneApiError(502, "boom")
        if method.upper() == "POST" and path == "/api/Links":
            return self.link_response
        if method.upper() == "GET" and path.startswith("/api/Sale/client/"):
            return self.sale_response
        raise AssertionError(f"Unexpected PayPhone call {method} {path}")


def test_money_to_cents_and_client_tx_length() -> None:
    assert money_to_cents(Decimal("12.68")) == 1268
    assert money_to_cents("1.50") == 150
    pid = uuid4()
    assert len(client_transaction_id_for(pid)) == 15


def test_build_link_amounts_untaxed_total() -> None:
    amounts = build_link_amounts(
        OrderAmountBreakdown(
            total=Decimal("25.50"),
            subtotal=Decimal("20.50"),
            tax_total=Decimal("0"),
            shipping_total=Decimal("5.00"),
            discount_total=Decimal("0"),
        )
    )
    assert amounts["amount"] == 2550
    assert amounts["amountWithoutTax"] == 2550
    assert amounts["tax"] == 0


def test_build_link_amounts_with_iva() -> None:
    amounts = build_link_amounts(
        OrderAmountBreakdown(
            total=Decimal("120.00"),
            subtotal=Decimal("100.00"),
            tax_total=Decimal("15.00"),
            shipping_total=Decimal("5.00"),
            discount_total=Decimal("0"),
        )
    )
    assert amounts["amount"] == 12000
    assert amounts["amountWithTax"] == 10000
    assert amounts["tax"] == 1500
    assert amounts["amountWithoutTax"] == 500


def test_create_payment_redirects_to_payphone_link(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core import config as config_mod
    from app.modules.payments import providers as providers_mod
    from app.modules.payments.providers import payphone as payphone_mod

    fake = _FakePayPhoneClient()
    monkeypatch.setattr(config_mod.settings, "payment_default_provider", "payphone")
    monkeypatch.setattr(config_mod.settings, "payphone_token", "test-token")
    monkeypatch.setattr(config_mod.settings, "payphone_store_id", "store-1")
    monkeypatch.setattr(
        providers_mod,
        "PayPhonePaymentProvider",
        lambda: PayPhonePaymentProvider(client=fake),
    )
    monkeypatch.setattr(
        payphone_mod,
        "PayPhonePaymentProvider",
        lambda client=None: PayPhonePaymentProvider(client=fake),
    )

    # Re-bind get_provider to use fake
    def _get_provider(name: str | None = None):
        chosen = (name or config_mod.settings.payment_default_provider).lower()
        if chosen == "payphone":
            return PayPhonePaymentProvider(client=fake)
        from app.modules.payments.providers.manual import ManualPaymentProvider

        return ManualPaymentProvider()

    monkeypatch.setattr(providers_mod, "get_provider", _get_provider)
    from app.modules.payments import service as payment_service_mod

    monkeypatch.setattr(payment_service_mod, "get_provider", _get_provider)

    data = _checkout_order(client, customer_user, admin_user, sku="PP-LINK", price="19.99")
    _login(client, customer_user)
    response = client.post(f"/api/v1/orders/{data['order']['order_id']}/payment", json={})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["provider"] == "payphone"
    assert body["status"] == PaymentStatus.PROCESSING.value
    assert body["client_action"]["type"] == "redirect"
    assert body["client_action"]["url"] == "https://payp.page.link/test-gema"
    assert fake.calls and fake.calls[0][0] == "POST"
    assert fake.calls[0][2]["amount"] == 2499  # 19.99 + 5.00 shipping default


def test_payphone_webhook_approves_and_consumes(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core import config as config_mod
    from app.modules.payments import providers as providers_mod
    from app.modules.payments import service as payment_service_mod

    fake = _FakePayPhoneClient()

    def _get_provider(name: str | None = None):
        chosen = (name or "payphone").lower()
        if chosen == "payphone":
            return PayPhonePaymentProvider(client=fake)
        from app.modules.payments.providers.manual import ManualPaymentProvider

        return ManualPaymentProvider()

    monkeypatch.setattr(config_mod.settings, "payment_default_provider", "payphone")
    monkeypatch.setattr(config_mod.settings, "payphone_token", "test-token")
    monkeypatch.setattr(config_mod.settings, "payphone_store_id", "store-1")
    monkeypatch.setattr(config_mod.settings, "payphone_webhook_secret", "")
    monkeypatch.setattr(providers_mod, "get_provider", _get_provider)
    monkeypatch.setattr(payment_service_mod, "get_provider", _get_provider)

    data = _checkout_order(
        client, customer_user, admin_user, sku="PP-WH", price="10.00", stock=3
    )
    order_id = UUID(data["order"]["order_id"])
    _login(client, customer_user)
    pay = client.post(f"/api/v1/orders/{order_id}/payment", json={}).json()
    client_tx = pay["provider_payment_id"]
    amount_cents = money_to_cents(Decimal(str(pay["amount"])))

    webhook = client.post(
        "/api/v1/payments/webhooks/payphone/NotificacionPago",
        json={
            "Amount": amount_cents,
            "ClientTransactionId": client_tx,
            "StatusCode": 3,
            "TransactionStatus": "Approved",
            "StoreId": "store-1",
            "TransactionId": 555001,
            "AuthorizationCode": "W555001",
        },
    )
    assert webhook.status_code == 200
    assert webhook.json() == {"Response": True, "ErrorCode": "000"}

    db_session.expire_all()
    payment = db_session.get(Payment, UUID(pay["id"]))
    assert payment is not None
    assert payment.status == PaymentStatus.SUCCEEDED.value
    order = db_session.get(Order, order_id)
    assert order is not None
    assert order.status == OrderStatus.PAID.value


def test_payphone_sync_confirms_from_sale_api(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core import config as config_mod
    from app.modules.payments import providers as providers_mod
    from app.modules.payments import service as payment_service_mod

    fake = _FakePayPhoneClient()

    def _get_provider(name: str | None = None):
        if (name or "payphone").lower() == "payphone":
            return PayPhonePaymentProvider(client=fake)
        from app.modules.payments.providers.manual import ManualPaymentProvider

        return ManualPaymentProvider()

    monkeypatch.setattr(config_mod.settings, "payment_default_provider", "payphone")
    monkeypatch.setattr(config_mod.settings, "payphone_token", "test-token")
    monkeypatch.setattr(config_mod.settings, "payphone_store_id", "store-1")
    monkeypatch.setattr(providers_mod, "get_provider", _get_provider)
    monkeypatch.setattr(payment_service_mod, "get_provider", _get_provider)

    data = _checkout_order(client, customer_user, admin_user, sku="PP-SYNC", price="8.00")
    _login(client, customer_user)
    pay = client.post(
        f"/api/v1/orders/{data['order']['order_id']}/payment", json={}
    ).json()
    fake.sale_response = {
        "statusCode": 3,
        "transactionId": 777,
        "clientTransactionId": pay["provider_payment_id"],
        "amount": money_to_cents(Decimal(str(pay["amount"]))),
    }

    synced = client.post(f"/api/v1/payments/{pay['id']}/sync")
    assert synced.status_code == 200, synced.text
    assert synced.json()["status"] == PaymentStatus.SUCCEEDED.value

    db_session.expire_all()
    order = db_session.get(Order, UUID(data["order"]["order_id"]))
    assert order is not None
    assert order.status == OrderStatus.PAID.value


def test_payphone_webhook_rejects_wrong_secret(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core import config as config_mod

    monkeypatch.setattr(config_mod.settings, "payphone_webhook_secret", "expected-secret")
    monkeypatch.setattr(config_mod.settings, "payphone_store_id", "store-1")
    response = client.post(
        "/api/v1/payments/webhooks/payphone",
        json={
            "Amount": 100,
            "ClientTransactionId": "abc",
            "StatusCode": 3,
            "TransactionId": 1,
            "StoreId": "store-1",
        },
    )
    assert response.status_code == 401


def test_payphone_webhook_accepts_query_token(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PayPhone Notificacion Externa may pass the shared secret as ?token=."""
    _patch_payphone(monkeypatch, webhook_secret="whsec-query")
    data = _checkout_order(client, customer_user, admin_user, sku="PP-QTOK", price="15.00")
    order_id = UUID(data["order"]["order_id"])
    _login(client, customer_user)
    pay = client.post(f"/api/v1/orders/{order_id}/payment", json={}).json()
    amount_cents = money_to_cents(Decimal(str(pay["amount"])))

    webhook = client.post(
        "/api/v1/payments/webhooks/payphone/NotificacionPago",
        params={"token": "whsec-query"},
        json={
            "Amount": amount_cents,
            "ClientTransactionId": pay["provider_payment_id"],
            "StatusCode": 3,
            "StoreId": "store-1",
            "TransactionId": 9011,
            "AuthorizationCode": "Q9011",
        },
    )
    assert webhook.status_code == 200
    assert webhook.json() == {"Response": True, "ErrorCode": "000"}
    db_session.expire_all()
    assert db_session.get(Payment, UUID(pay["id"])).status == PaymentStatus.SUCCEEDED.value
    assert db_session.get(Order, order_id).status == OrderStatus.PAID.value


def test_production_requires_payphone_credentials() -> None:
    from pydantic import ValidationError

    from app.core.config import Settings

    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            postgres_password="prod-db-secret-not-default",
            internal_job_secret="prod-internal-secret-not-default",
            payment_webhook_secret="prod-webhook-secret-not-default",
            payment_default_provider="payphone",
            payphone_token="",
            payphone_store_id="",
            session_backend="redis",
            auth_rate_limit_backend="redis",
            allow_manual_payment_confirm=False,
        )


def test_production_requires_payphone_webhook_secret() -> None:
    from pydantic import ValidationError

    from app.core.config import Settings

    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            postgres_password="prod-db-secret-not-default",
            internal_job_secret="prod-internal-secret-not-default",
            payment_webhook_secret="prod-webhook-secret-not-default",
            payment_default_provider="payphone",
            payphone_token="prod-token",
            payphone_store_id="prod-store",
            payphone_webhook_secret="",
            session_backend="redis",
            auth_rate_limit_backend="redis",
            allow_manual_payment_confirm=False,
        )


def test_staging_requires_payphone_webhook_secret() -> None:
    from pydantic import ValidationError

    from app.core.config import Settings

    with pytest.raises(ValidationError):
        Settings(
            app_env="staging",
            postgres_password="stage-db-secret-not-default",
            internal_job_secret="stage-internal-secret-not-default",
            payment_webhook_secret="stage-webhook-secret-not-default",
            payment_default_provider="payphone",
            payphone_token="stage-token",
            payphone_store_id="stage-store",
            payphone_webhook_secret="",
            session_backend="redis",
            auth_rate_limit_backend="redis",
            public_app_url="https://staging.example.com",
            cors_origins="https://staging.example.com",
        )


def _patch_payphone(
    monkeypatch: pytest.MonkeyPatch,
    *,
    fake: _FakePayPhoneClient | None = None,
    webhook_secret: str = "",
) -> _FakePayPhoneClient:
    from app.core import config as config_mod
    from app.modules.payments import providers as providers_mod
    from app.modules.payments import service as payment_service_mod

    client_fake = fake or _FakePayPhoneClient()

    def _get_provider(name: str | None = None):
        if (name or "payphone").lower() == "payphone":
            return PayPhonePaymentProvider(client=client_fake)
        from app.modules.payments.providers.manual import ManualPaymentProvider

        return ManualPaymentProvider()

    monkeypatch.setattr(config_mod.settings, "payment_default_provider", "payphone")
    monkeypatch.setattr(config_mod.settings, "payphone_token", "test-token")
    monkeypatch.setattr(config_mod.settings, "payphone_store_id", "store-1")
    monkeypatch.setattr(config_mod.settings, "payphone_webhook_secret", webhook_secret)
    monkeypatch.setattr(config_mod.settings, "app_env", "development")
    monkeypatch.setattr(providers_mod, "get_provider", _get_provider)
    monkeypatch.setattr(payment_service_mod, "get_provider", _get_provider)
    return client_fake


def test_payphone_webhook_empty_body_does_not_mark_paid(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_payphone(monkeypatch)
    data = _checkout_order(client, customer_user, admin_user, sku="PP-EMPTY", price="9.00")
    order_id = UUID(data["order"]["order_id"])
    _login(client, customer_user)
    pay = client.post(f"/api/v1/orders/{order_id}/payment", json={}).json()

    webhook = client.post(
        "/api/v1/payments/webhooks/payphone",
        content=b"",
        headers={"Content-Type": "application/json"},
    )
    # PayPhone contract: always HTTP 200 envelope; must not confirm payment.
    assert webhook.status_code == 200
    assert webhook.json()["Response"] is False

    db_session.expire_all()
    payment = db_session.get(Payment, UUID(pay["id"]))
    assert payment is not None
    assert payment.status == PaymentStatus.PROCESSING.value
    order = db_session.get(Order, order_id)
    assert order is not None
    assert order.status == OrderStatus.PENDING_PAYMENT.value


def test_payphone_webhook_missing_secret_fails_closed_in_staging(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core import config as config_mod

    monkeypatch.setattr(config_mod.settings, "app_env", "staging")
    monkeypatch.setattr(config_mod.settings, "payphone_webhook_secret", "")
    monkeypatch.setattr(config_mod.settings, "payphone_store_id", "store-1")
    response = client.post(
        "/api/v1/payments/webhooks/payphone",
        json={
            "Amount": 100,
            "ClientTransactionId": "abc",
            "StatusCode": 3,
            "TransactionId": 1,
            "StoreId": "store-1",
        },
    )
    assert response.status_code == 503


def test_payphone_webhook_malformed_payload_does_not_pay(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_payphone(monkeypatch)
    data = _checkout_order(client, customer_user, admin_user, sku="PP-BAD", price="7.00")
    order_id = UUID(data["order"]["order_id"])
    _login(client, customer_user)
    pay = client.post(f"/api/v1/orders/{order_id}/payment", json={}).json()

    webhook = client.post("/api/v1/payments/webhooks/payphone", json={"hello": "world"})
    assert webhook.status_code == 200
    assert webhook.json()["Response"] is False

    db_session.expire_all()
    assert db_session.get(Payment, UUID(pay["id"])).status == PaymentStatus.PROCESSING.value
    assert db_session.get(Order, order_id).status == OrderStatus.PENDING_PAYMENT.value


def test_payphone_webhook_wrong_amount_does_not_pay(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_payphone(monkeypatch)
    data = _checkout_order(client, customer_user, admin_user, sku="PP-AMT", price="11.00")
    order_id = UUID(data["order"]["order_id"])
    _login(client, customer_user)
    pay = client.post(f"/api/v1/orders/{order_id}/payment", json={}).json()

    webhook = client.post(
        "/api/v1/payments/webhooks/payphone",
        json={
            "Amount": 1,
            "ClientTransactionId": pay["provider_payment_id"],
            "StatusCode": 3,
            "StoreId": "store-1",
            "TransactionId": 9001,
        },
    )
    assert webhook.status_code == 200
    assert webhook.json()["Response"] is False

    db_session.expire_all()
    assert db_session.get(Payment, UUID(pay["id"])).status == PaymentStatus.PROCESSING.value
    assert db_session.get(Order, order_id).status == OrderStatus.PENDING_PAYMENT.value


def test_payphone_webhook_unknown_client_tx_does_not_pay(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_payphone(monkeypatch)
    webhook = client.post(
        "/api/v1/payments/webhooks/payphone",
        json={
            "Amount": 1500,
            "ClientTransactionId": "deadbeefdeadbee",
            "StatusCode": 3,
            "StoreId": "store-1",
            "TransactionId": 9002,
        },
    )
    assert webhook.status_code == 200
    assert webhook.json()["Response"] is False


def test_payphone_webhook_duplicate_is_idempotent(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_payphone(monkeypatch)
    data = _checkout_order(client, customer_user, admin_user, sku="PP-DUP", price="12.00")
    order_id = UUID(data["order"]["order_id"])
    _login(client, customer_user)
    pay = client.post(f"/api/v1/orders/{order_id}/payment", json={}).json()
    amount_cents = money_to_cents(Decimal(str(pay["amount"])))
    body = {
        "Amount": amount_cents,
        "ClientTransactionId": pay["provider_payment_id"],
        "StatusCode": 3,
        "StoreId": "store-1",
        "TransactionId": 9003,
        "AuthorizationCode": "D9003",
    }
    first = client.post("/api/v1/payments/webhooks/payphone", json=body)
    second = client.post("/api/v1/payments/webhooks/payphone", json=body)
    assert first.status_code == 200 and first.json()["Response"] is True
    assert second.status_code == 200 and second.json()["Response"] is True

    db_session.expire_all()
    payment = db_session.get(Payment, UUID(pay["id"]))
    assert payment is not None
    assert payment.status == PaymentStatus.SUCCEEDED.value
    assert db_session.get(Order, order_id).status == OrderStatus.PAID.value


def test_payphone_webhook_pending_does_not_pay(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_payphone(monkeypatch)
    data = _checkout_order(client, customer_user, admin_user, sku="PP-PEND", price="6.00")
    order_id = UUID(data["order"]["order_id"])
    _login(client, customer_user)
    pay = client.post(f"/api/v1/orders/{order_id}/payment", json={}).json()
    amount_cents = money_to_cents(Decimal(str(pay["amount"])))

    webhook = client.post(
        "/api/v1/payments/webhooks/payphone",
        json={
            "Amount": amount_cents,
            "ClientTransactionId": pay["provider_payment_id"],
            "StatusCode": 1,
            "StoreId": "store-1",
            "TransactionId": 9004,
        },
    )
    assert webhook.status_code == 200
    assert webhook.json()["Response"] is True  # accepted notify, outcome ignored

    db_session.expire_all()
    assert db_session.get(Payment, UUID(pay["id"])).status == PaymentStatus.PROCESSING.value
    assert db_session.get(Order, order_id).status == OrderStatus.PENDING_PAYMENT.value


def test_payphone_webhook_failed_releases_reservation(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_payphone(monkeypatch)
    data = _checkout_order(
        client, customer_user, admin_user, sku="PP-FAIL", price="5.00", stock=2
    )
    order_id = UUID(data["order"]["order_id"])
    _login(client, customer_user)
    pay = client.post(f"/api/v1/orders/{order_id}/payment", json={}).json()
    amount_cents = money_to_cents(Decimal(str(pay["amount"])))

    webhook = client.post(
        "/api/v1/payments/webhooks/payphone",
        json={
            "Amount": amount_cents,
            "ClientTransactionId": pay["provider_payment_id"],
            "StatusCode": 2,
            "StoreId": "store-1",
            "TransactionId": 9005,
        },
    )
    assert webhook.status_code == 200
    assert webhook.json()["Response"] is True

    db_session.expire_all()
    assert db_session.get(Payment, UUID(pay["id"])).status == PaymentStatus.FAILED.value
    assert db_session.get(Order, order_id).status == OrderStatus.PENDING_PAYMENT.value


def test_payphone_webhook_valid_with_secret_header(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_payphone(monkeypatch, webhook_secret="whsec-test")
    data = _checkout_order(client, customer_user, admin_user, sku="PP-OK", price="13.00")
    order_id = UUID(data["order"]["order_id"])
    _login(client, customer_user)
    pay = client.post(f"/api/v1/orders/{order_id}/payment", json={}).json()
    amount_cents = money_to_cents(Decimal(str(pay["amount"])))

    webhook = client.post(
        "/api/v1/payments/webhooks/payphone",
        headers={"X-GEMA-Payment-Secret": "whsec-test"},
        json={
            "Amount": amount_cents,
            "ClientTransactionId": pay["provider_payment_id"],
            "StatusCode": 3,
            "StoreId": "store-1",
            "TransactionId": 9006,
            "AuthorizationCode": "A9006",
        },
    )
    assert webhook.status_code == 200
    assert webhook.json() == {"Response": True, "ErrorCode": "000"}

    db_session.expire_all()
    assert db_session.get(Payment, UUID(pay["id"])).status == PaymentStatus.SUCCEEDED.value
    assert db_session.get(Order, order_id).status == OrderStatus.PAID.value


def test_payphone_abandoned_expire_then_late_webhook_does_not_pay(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TTL job releases stock / cancels PENDING; late PayPhone approve must not PAID."""
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import func, select

    from app.modules.inventory.models import InventoryReservation, ReservationStatus
    from app.modules.inventory.service import InventoryService

    _patch_payphone(monkeypatch)
    data = _checkout_order(
        client, customer_user, admin_user, sku="PP-ABANDON", price="14.00", stock=3
    )
    order_id = UUID(data["order"]["order_id"])
    _login(client, customer_user)
    pay = client.post(f"/api/v1/orders/{order_id}/payment", json={}).json()
    amount_cents = money_to_cents(Decimal(str(pay["amount"])))

    # Simulate TTL elapsed while payment stays PROCESSING.
    rows = list(
        db_session.scalars(
            select(InventoryReservation).where(InventoryReservation.order_id == order_id)
        ).all()
    )
    for row in rows:
        row.expires_at = datetime.now(UTC) - timedelta(minutes=5)
    db_session.commit()

    result = InventoryService(db_session).expire_due_reservations(commit=True)
    assert result["expired_reservations"] >= 1
    db_session.expire_all()
    order = db_session.get(Order, order_id)
    assert order is not None
    assert order.status == OrderStatus.CANCELLED.value
    reserved = db_session.scalar(
        select(func.count())
        .select_from(InventoryReservation)
        .where(
            InventoryReservation.order_id == order_id,
            InventoryReservation.status == ReservationStatus.ACTIVE.value,
        )
    )
    assert reserved == 0

    webhook = client.post(
        "/api/v1/payments/webhooks/payphone",
        json={
            "Amount": amount_cents,
            "ClientTransactionId": pay["provider_payment_id"],
            "StatusCode": 3,
            "StoreId": "store-1",
            "TransactionId": 9010,
        },
    )
    assert webhook.status_code == 200
    assert webhook.json()["Response"] is False

    db_session.expire_all()
    payment = db_session.get(Payment, UUID(pay["id"]))
    assert payment is not None
    assert payment.status != PaymentStatus.SUCCEEDED.value
    assert db_session.get(Order, order_id).status == OrderStatus.CANCELLED.value


def test_payphone_webhook_missing_amount_on_approved_does_not_pay(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_payphone(monkeypatch)
    data = _checkout_order(client, customer_user, admin_user, sku="PP-NOAMT", price="4.00")
    order_id = UUID(data["order"]["order_id"])
    _login(client, customer_user)
    pay = client.post(f"/api/v1/orders/{order_id}/payment", json={}).json()

    webhook = client.post(
        "/api/v1/payments/webhooks/payphone",
        json={
            "ClientTransactionId": pay["provider_payment_id"],
            "StatusCode": 3,
            "StoreId": "store-1",
            "TransactionId": 9007,
        },
    )
    assert webhook.status_code == 200
    assert webhook.json()["Response"] is False
    db_session.expire_all()
    assert db_session.get(Payment, UUID(pay["id"])).status == PaymentStatus.PROCESSING.value
    assert db_session.get(Order, order_id).status == OrderStatus.PENDING_PAYMENT.value
