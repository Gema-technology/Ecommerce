"""Customers vs employees isolation, invite flow, SUPER_ADMIN guards."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from app.modules.roles.models import User
from tests.conftest import login_as


def test_customers_list_excludes_employees(
    client: TestClient,
    customer_user: User,
    admin_user: User,
) -> None:
    login_as(client, admin_user)
    response = client.get("/api/v1/admin/customers")
    assert response.status_code == 200
    ids = {row["id"] for row in response.json()["items"]}
    assert str(customer_user.id) in ids
    assert str(admin_user.id) not in ids


def test_employees_list_excludes_customers(
    client: TestClient,
    customer_user: User,
    admin_user: User,
) -> None:
    login_as(client, admin_user)
    response = client.get("/api/v1/admin/employees")
    assert response.status_code == 200
    user_ids = {row["user_id"] for row in response.json()["items"]}
    assert str(admin_user.id) in user_ids
    assert str(customer_user.id) not in user_ids


def test_admin_cannot_invite_employee(
    client: TestClient,
    admin_user: User,
) -> None:
    login_as(client, admin_user)
    response = client.post(
        "/api/v1/admin/employees/invite",
        json={
            "email": "newstaff@example.com",
            "first_name": "New",
            "last_name": "Staff",
            "role": "ADMIN",
        },
    )
    assert response.status_code == 403


def test_invite_accept_and_login(
    client: TestClient,
    super_admin_user: User,
) -> None:
    login_as(client, super_admin_user)
    invite = client.post(
        "/api/v1/admin/employees/invite",
        json={
            "email": "ops@example.com",
            "first_name": "Ops",
            "last_name": "GEMA",
            "role": "ADMIN",
            "job_title": "Operaciones",
        },
    )
    assert invite.status_code == 201, invite.text
    body = invite.json()
    assert body["status"] == "invited"
    assert body["invite_url"]
    token = parse_qs(urlparse(body["invite_url"]).query)["token"][0]

    client.cookies.clear()
    accepted = client.post(
        "/api/v1/auth/accept-invite",
        json={"token": token, "password": "StaffPass123!"},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "active"

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "ops@example.com", "password": "StaffPass123!"},
    )
    assert login.status_code == 200
    assert "ADMIN" in login.json()["roles"]


def test_promote_customer_to_employee(
    client: TestClient,
    customer_user: User,
    super_admin_user: User,
) -> None:
    login_as(client, super_admin_user)
    invite = client.post(
        "/api/v1/admin/employees/invite",
        json={
            "email": customer_user.email,
            "first_name": "Promoted",
            "last_name": "Staff",
            "role": "ADMIN",
        },
    )
    assert invite.status_code == 201, invite.text

    customers = client.get("/api/v1/admin/customers")
    assert customers.status_code == 200
    assert str(customer_user.id) not in {r["id"] for r in customers.json()["items"]}

    employees = client.get("/api/v1/admin/employees")
    assert str(customer_user.id) in {r["user_id"] for r in employees.json()["items"]}


def test_cannot_demote_last_super_admin(
    client: TestClient,
    super_admin_user: User,
) -> None:
    login_as(client, super_admin_user)
    listed = client.get("/api/v1/admin/employees")
    emp = next(
        r for r in listed.json()["items"] if r["user_id"] == str(super_admin_user.id)
    )
    response = client.patch(
        f"/api/v1/admin/employees/{emp['id']}/role",
        json={"role": "ADMIN"},
    )
    assert response.status_code == 400
    assert "last SUPER_ADMIN" in response.json()["detail"]


def test_cannot_deactivate_last_super_admin(
    client: TestClient,
    super_admin_user: User,
) -> None:
    login_as(client, super_admin_user)
    listed = client.get("/api/v1/admin/employees")
    emp = next(
        r for r in listed.json()["items"] if r["user_id"] == str(super_admin_user.id)
    )
    response = client.patch(
        f"/api/v1/admin/employees/{emp['id']}/active",
        json={"is_active": False},
    )
    assert response.status_code == 400
    assert "last SUPER_ADMIN" in response.json()["detail"]


def test_customer_active_toggle(
    client: TestClient,
    customer_user: User,
    admin_user: User,
) -> None:
    login_as(client, admin_user)
    response = client.patch(
        f"/api/v1/admin/customers/{customer_user.id}/active",
        json={"is_active": False},
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_register_still_customer_only(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "shopper@example.com",
            "password": "secure-password",
            "first_name": "Shop",
            "last_name": "Per",
        },
    )
    assert response.status_code == 201
    assert response.json()["roles"] == ["CUSTOMER"]


def test_resend_invite_and_reset_password(
    client: TestClient,
    super_admin_user: User,
    admin_user: User,
) -> None:
    login_as(client, super_admin_user)
    invite = client.post(
        "/api/v1/admin/employees/invite",
        json={
            "email": "temp@example.com",
            "first_name": "Temp",
            "last_name": "Staff",
            "role": "ADMIN",
        },
    )
    assert invite.status_code == 201
    emp_id = invite.json()["id"]
    old_token = parse_qs(urlparse(invite.json()["invite_url"]).query)["token"][0]

    resent = client.post(f"/api/v1/admin/employees/{emp_id}/resend-invite")
    assert resent.status_code == 200, resent.text
    new_token = parse_qs(urlparse(resent.json()["invite_url"]).query)["token"][0]
    assert new_token != old_token

    # Old token no longer works
    client.cookies.clear()
    stale = client.post(
        "/api/v1/auth/accept-invite",
        json={"token": old_token, "password": "StaffPass123!"},
    )
    assert stale.status_code == 400

    accepted = client.post(
        "/api/v1/auth/accept-invite",
        json={"token": new_token, "password": "StaffPass123!"},
    )
    assert accepted.status_code == 200

    # Reset password for an already-active employee (admin_user fixture)
    login_as(client, super_admin_user)
    listed = client.get("/api/v1/admin/employees")
    active_emp = next(
        r for r in listed.json()["items"] if r["user_id"] == str(admin_user.id)
    )
    reset = client.post(f"/api/v1/admin/employees/{active_emp['id']}/reset-password")
    assert reset.status_code == 200, reset.text
    assert reset.json()["status"] == "invited"
    reset_token = parse_qs(urlparse(reset.json()["invite_url"]).query)["token"][0]

    # Old password no longer works
    client.cookies.clear()
    denied = client.post(
        "/api/v1/auth/login",
        json={"email": admin_user.email, "password": "secure-password"},
    )
    assert denied.status_code == 401

    set_pw = client.post(
        "/api/v1/auth/accept-invite",
        json={"token": reset_token, "password": "NewStaffPass1!"},
    )
    assert set_pw.status_code == 200
    ok = client.post(
        "/api/v1/auth/login",
        json={"email": admin_user.email, "password": "NewStaffPass1!"},
    )
    assert ok.status_code == 200


def test_admin_cannot_reset_password(client: TestClient, admin_user: User) -> None:
    login_as(client, admin_user)
    listed = client.get("/api/v1/admin/employees")
    emp_id = listed.json()["items"][0]["id"]
    assert client.post(f"/api/v1/admin/employees/{emp_id}/reset-password").status_code == 403
    assert client.post(f"/api/v1/admin/employees/{emp_id}/resend-invite").status_code == 403


def test_invite_base_url_skips_paused_placeholder_host() -> None:
    from starlette.requests import Request

    from app.core.config import settings
    from app.modules.employees.service import _invite_base_url

    previous = settings.public_app_url
    settings.public_app_url = "https://placeholder.vercel.app"
    try:
        request = Request(
            {
                "type": "http",
                "http_version": "1.1",
                "method": "POST",
                "scheme": "https",
                "path": "/api/v1/admin/employees/invite",
                "raw_path": b"/api/v1/admin/employees/invite",
                "query_string": b"",
                "headers": [(b"origin", b"https://ecommerce-nu-flax-51.vercel.app")],
                "client": ("127.0.0.1", 123),
                "server": ("test", 443),
            }
        )
        assert _invite_base_url(request) == "https://ecommerce-nu-flax-51.vercel.app"
    finally:
        settings.public_app_url = previous


def test_invite_returns_link_and_sends_email_when_enabled(
    client: TestClient,
    super_admin_user: User,
    monkeypatch,
) -> None:
    from app.core.config import settings
    from app.modules.notifications.service import set_email_transport
    from app.modules.notifications.smtp import MemoryTransport

    transport = MemoryTransport()
    set_email_transport(transport)
    monkeypatch.setattr(settings, "email_enabled", True)
    try:
        login_as(client, super_admin_user)
        invite = client.post(
            "/api/v1/admin/employees/invite",
            json={
                "email": "correo.equipo@example.com",
                "first_name": "Ana",
                "last_name": "Equipo",
                "role": "ADMIN",
            },
        )
        assert invite.status_code == 201, invite.text
        body = invite.json()
        assert body["invite_url"]
        assert body["email_sent"] is True
        assert len(transport.sent) == 1
        assert transport.sent[0].to_address == "correo.equipo@example.com"
        assert body["invite_url"] in transport.sent[0].text_body
    finally:
        set_email_transport(None)
