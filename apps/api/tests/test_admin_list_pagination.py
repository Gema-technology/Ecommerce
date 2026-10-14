"""Admin list endpoints: pagination envelope and basic filters."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.modules.roles.models import User
from tests.conftest import login_as
from tests.test_payments import _checkout_order
from tests.test_suppliers import _supplier_payload


def test_suppliers_list_paginated(client: TestClient, admin_user: User) -> None:
    login_as(client, admin_user)
    for i in range(3):
        payload = _supplier_payload(
            business_name=f"Proveedor {i}",
            tax_id=f"179001234500{i}",
        )
        assert client.post("/api/v1/admin/suppliers", json=payload).status_code == 201

    page1 = client.get("/api/v1/admin/suppliers", params={"page": 1, "page_size": 2})
    assert page1.status_code == 200
    body = page1.json()
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert body["total"] >= 3
    assert body["total_pages"] >= 2
    assert len(body["items"]) == 2

    filtered = client.get(
        "/api/v1/admin/suppliers", params={"search": "Proveedor 1"}
    )
    assert filtered.status_code == 200
    assert filtered.json()["total"] >= 1
    assert any("Proveedor 1" in s["business_name"] for s in filtered.json()["items"])


def test_customers_list_paginated(
    client: TestClient, admin_user: User, customer_user: User
) -> None:
    login_as(client, admin_user)
    response = client.get(
        "/api/v1/admin/customers",
        params={"page": 1, "page_size": 20, "q": customer_user.email},
    )
    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert body["page"] == 1
    assert any(r["id"] == str(customer_user.id) for r in body["items"])


def test_payments_list_paginated(
    client: TestClient, customer_user: User, admin_user: User
) -> None:
    data = _checkout_order(client, customer_user, admin_user, sku="PAY-PAGE")
    login_as(client, customer_user)
    payment = client.post(
        f"/api/v1/orders/{data['order']['order_id']}/payment", json={}
    ).json()

    login_as(client, admin_user)
    response = client.get(
        "/api/v1/admin/payments",
        params={"page": 1, "page_size": 10, "q": data["order"]["order_number"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    assert any(p["id"] == payment["id"] for p in body["items"])


def test_orders_list_status_filter(
    client: TestClient, customer_user: User, admin_user: User
) -> None:
    _checkout_order(client, customer_user, admin_user, sku="ORD-STATUS")
    login_as(client, admin_user)
    response = client.get(
        "/api/v1/admin/orders",
        params={"status": "PENDING_PAYMENT", "page": 1, "page_size": 20},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    assert all(o["status"] == "PENDING_PAYMENT" for o in body["items"])
