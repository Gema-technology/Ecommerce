from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.roles.models import User
from app.modules.roles.schemas import ROLE_CUSTOMER
from tests.conftest import create_user_with_role


def test_register_success(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "New.User@Example.com",
            "password": "secure-password",
            "first_name": "John",
            "last_name": "Doe",
            "phone": "0999999999",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "new.user@example.com"
    assert data["first_name"] == "John"
    assert data["roles"] == [ROLE_CUSTOMER]
    assert "password_hash" not in data
    assert "password" not in data
    assert client.cookies.get("gema_session")


def test_register_duplicate_email(client: TestClient, customer_user: User) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": customer_user.email,
            "password": "secure-password",
            "first_name": "Other",
            "last_name": "User",
        },
    )
    assert response.status_code == 409


def test_register_invalid_password(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "weak@example.com",
            "password": "short",
            "first_name": "Weak",
            "last_name": "Pass",
        },
    )
    assert response.status_code == 422


def test_register_assigns_customer_role(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "rolecheck@example.com",
            "password": "secure-password",
            "first_name": "Role",
            "last_name": "Check",
        },
    )
    assert response.status_code == 201
    assert response.json()["roles"] == [ROLE_CUSTOMER]


def test_login_success(client: TestClient, customer_user: User) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": customer_user.email, "password": "secure-password"},
    )
    assert response.status_code == 200
    assert response.json()["email"] == customer_user.email
    assert client.cookies.get("gema_session")


def test_login_wrong_password(client: TestClient, customer_user: User) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": customer_user.email, "password": "wrong-password"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_login_unknown_user(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "secure-password"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_login_disabled_user(client: TestClient, db_session: Session) -> None:
    create_user_with_role(
        db_session,
        email="disabled@example.com",
        password="secure-password",
        role_name=ROLE_CUSTOMER,
        is_active=False,
    )
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "disabled@example.com", "password": "secure-password"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_me_authenticated(client: TestClient, customer_user: User) -> None:
    login = client.post(
        "/api/v1/auth/login",
        json={"email": customer_user.email, "password": "secure-password"},
    )
    assert login.status_code == 200
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == customer_user.email
    assert "password_hash" not in data


def test_me_unauthenticated(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_logout(client: TestClient, customer_user: User) -> None:
    client.post(
        "/api/v1/auth/login",
        json={"email": customer_user.email, "password": "secure-password"},
    )
    logout = client.post("/api/v1/auth/logout")
    assert logout.status_code == 200
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 401
