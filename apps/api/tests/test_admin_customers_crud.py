from fastapi.testclient import TestClient

from app.modules.roles.models import User
from tests.conftest import login_as

BILLING = {
    "phone": "0998887766",
    "tax_id_type": "CEDULA",
    "tax_id": "1710034065",
    "address_line": "Av. Amazonas N34-123",
    "city": "Quito",
    "province": "Pichincha",
}


def test_admin_customer_crud(client: TestClient, admin_user: User) -> None:
    login_as(client, admin_user)

    created = client.post(
        "/api/v1/admin/customers",
        json={
            "email": "mostrador@example.com",
            "password": "secure-password",
            "first_name": "Ana",
            "last_name": "Vega",
            "phone": "0998887766",
            "tax_id_type": "RUC",
            "tax_id": "1790012345001",
            "address_line": "Av. Amazonas N34-123",
            "city": "Quito",
            "province": "Pichincha",
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["email"] == "mostrador@example.com"
    assert body["first_name"] == "Ana"
    assert body["phone"] == "0998887766"
    assert body["tax_id_type"] == "RUC"
    assert body["tax_id"] == "1790012345001"
    assert body["city"] == "Quito"
    assert body["address_line"] == "Av. Amazonas N34-123"
    assert "CUSTOMER" in body["roles"]
    customer_id = body["id"]

    fetched = client.get(f"/api/v1/admin/customers/{customer_id}")
    assert fetched.status_code == 200
    assert fetched.json()["last_name"] == "Vega"

    updated = client.patch(
        f"/api/v1/admin/customers/{customer_id}",
        json={"last_name": "Vera", "phone": "0990001122"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["last_name"] == "Vera"
    assert updated.json()["phone"] == "0990001122"

    duplicate = client.post(
        "/api/v1/admin/customers",
        json={
            "email": "mostrador@example.com",
            "password": "secure-password",
            "first_name": "Otra",
            "last_name": "Persona",
            **BILLING,
        },
    )
    assert duplicate.status_code == 409

    deleted = client.delete(f"/api/v1/admin/customers/{customer_id}")
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/admin/customers/{customer_id}").status_code == 404


def test_admin_creates_customer_without_password(
    client: TestClient,
    admin_user: User,
) -> None:
    login_as(client, admin_user)
    created = client.post(
        "/api/v1/admin/customers",
        json={
            "email": "sin-clave@example.com",
            "first_name": "Luis",
            "last_name": "Perez",
            **BILLING,
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["email"] == "sin-clave@example.com"

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "sin-clave@example.com", "password": "secure-password"},
    )
    assert login.status_code == 401


def test_admin_cannot_delete_employee_as_customer(
    client: TestClient,
    admin_user: User,
) -> None:
    login_as(client, admin_user)
    denied = client.delete(f"/api/v1/admin/customers/{admin_user.id}")
    assert denied.status_code == 400
