from fastapi.testclient import TestClient

from app.modules.roles.models import User


def test_customer_cannot_access_admin_customers(
    client: TestClient, customer_user: User
) -> None:
    client.post(
        "/api/v1/auth/login",
        json={"email": customer_user.email, "password": "secure-password"},
    )
    response = client.get("/api/v1/admin/customers")
    assert response.status_code == 403


def test_customer_cannot_access_admin_employees(
    client: TestClient, customer_user: User
) -> None:
    client.post(
        "/api/v1/auth/login",
        json={"email": customer_user.email, "password": "secure-password"},
    )
    response = client.get("/api/v1/admin/employees")
    assert response.status_code == 403


def test_admin_can_access_admin_customers(client: TestClient, admin_user: User) -> None:
    client.post(
        "/api/v1/auth/login",
        json={"email": admin_user.email, "password": "secure-password"},
    )
    response = client.get("/api/v1/admin/customers")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert all(u["email"] != admin_user.email for u in response.json())


def test_admin_can_access_admin_employees(client: TestClient, admin_user: User) -> None:
    client.post(
        "/api/v1/auth/login",
        json={"email": admin_user.email, "password": "secure-password"},
    )
    response = client.get("/api/v1/admin/employees")
    assert response.status_code == 200
    assert any(e["email"] == admin_user.email for e in response.json())


def test_super_admin_can_access_admin_employees(
    client: TestClient, super_admin_user: User
) -> None:
    client.post(
        "/api/v1/auth/login",
        json={"email": super_admin_user.email, "password": "secure-password"},
    )
    response = client.get("/api/v1/admin/employees")
    assert response.status_code == 200


def test_get_profile(client: TestClient, customer_user: User) -> None:
    client.post(
        "/api/v1/auth/login",
        json={"email": customer_user.email, "password": "secure-password"},
    )
    response = client.get("/api/v1/users/me")
    assert response.status_code == 200
    assert response.json()["email"] == customer_user.email


def test_update_profile_allowed_fields(client: TestClient, customer_user: User) -> None:
    client.post(
        "/api/v1/auth/login",
        json={"email": customer_user.email, "password": "secure-password"},
    )
    response = client.patch(
        "/api/v1/users/me",
        json={"first_name": "Updated", "last_name": "Name", "phone": "0987654321"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["first_name"] == "Updated"
    assert data["last_name"] == "Name"
    assert data["phone"] == "0987654321"
    assert data["roles"] == ["CUSTOMER"]


def test_update_profile_cannot_change_roles(client: TestClient, customer_user: User) -> None:
    client.post(
        "/api/v1/auth/login",
        json={"email": customer_user.email, "password": "secure-password"},
    )
    response = client.patch(
        "/api/v1/users/me",
        json={"roles": ["ADMIN"], "is_active": False, "email_verified": True},
    )
    # Extra fields ignored by Pydantic model → request succeeds without applying them
    assert response.status_code == 200
    data = response.json()
    assert data["roles"] == ["CUSTOMER"]
    assert data["is_active"] is True
    assert data["email_verified"] is False
