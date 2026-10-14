"""Security hardening regression tests (Phase 0)."""

from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.rate_limit import reset_auth_rate_limiter_for_tests
from app.modules.roles.models import User
from tests.conftest import admin_confirm_payment, login_as
from tests.test_orders_checkout import _login
from tests.test_payments import _checkout_order


def test_customer_cannot_confirm_payment_manually(
    client: TestClient,
    customer_user: User,
    admin_user: User,
) -> None:
    data = _checkout_order(client, customer_user, admin_user, sku="SEC-NOCONF")
    _login(client, customer_user)
    payment = client.post(
        f"/api/v1/orders/{data['order']['order_id']}/payment", json={}
    ).json()

    legacy = client.post(f"/api/v1/payments/{payment['id']}/confirm?success=true")
    assert legacy.status_code == 404

    forbidden = client.post(
        f"/api/v1/admin/payments/{payment['id']}/confirm?success=true"
    )
    assert forbidden.status_code == 403

    assert admin_confirm_payment(client, admin_user, payment["id"]).status_code == 200


def test_customer_cannot_access_internal_expire_job(
    client: TestClient,
    customer_user: User,
) -> None:
    _login(client, customer_user)
    response = client.post("/api/v1/internal/reservations/expire")
    assert response.status_code == 401


def test_internal_expire_job_requires_valid_secret(
    client: TestClient,
) -> None:
    client.cookies.clear()
    bad = client.post(
        "/api/v1/internal/reservations/expire",
        headers={"X-GEMA-Internal-Secret": "wrong"},
    )
    assert bad.status_code == 401

    ok = client.post(
        "/api/v1/internal/reservations/expire",
        headers={"X-GEMA-Internal-Secret": settings.internal_job_secret},
    )
    assert ok.status_code == 200


def test_customer_cannot_access_admin_products(
    client: TestClient,
    customer_user: User,
) -> None:
    _login(client, customer_user)
    assert client.get("/api/v1/admin/products").status_code == 403
    assert client.post("/api/v1/admin/categories", json={}).status_code == 403


def test_login_rate_limit(
    client: TestClient,
    customer_user: User,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "auth_rate_limit", 3)
    monkeypatch.setattr(settings, "auth_rate_limit_window_seconds", 60)
    reset_auth_rate_limiter_for_tests()

    for _ in range(3):
        response = client.post(
            "/api/v1/auth/login",
            json={"email": customer_user.email, "password": "wrong-password"},
        )
        assert response.status_code == 401

    blocked = client.post(
        "/api/v1/auth/login",
        json={"email": customer_user.email, "password": "wrong-password"},
    )
    assert blocked.status_code == 429


def test_auth_error_does_not_leak_password(
    client: TestClient,
    customer_user: User,
) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": customer_user.email, "password": "secure-password"},
    )
    body = response.json()
    assert "secure-password" not in str(body)
    assert "password_hash" not in str(body)


def test_order_ownership_returns_not_found(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    db_session,
) -> None:
    from tests.conftest import create_user_with_role
    from app.modules.roles.schemas import ROLE_CUSTOMER

    other = create_user_with_role(
        db_session,
        email="other-sec@example.com",
        password="secure-password",
        role_name=ROLE_CUSTOMER,
    )
    data = _checkout_order(client, customer_user, admin_user, sku="SEC-OWN")
    login_as(client, other)
    assert client.get(f"/api/v1/orders/{data['order']['order_id']}").status_code == 404
