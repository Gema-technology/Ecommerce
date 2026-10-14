from decimal import Decimal

from fastapi.testclient import TestClient

from app.modules.roles.models import User


def _login(client: TestClient, user: User) -> None:
    client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "secure-password"},
    )


def _seed_product(client: TestClient) -> str:
    category = client.post("/api/v1/admin/categories", json={"name": "GPUs"}).json()
    brand = client.post(
        "/api/v1/admin/brands",
        json={"name": "ASUS", "category_ids": [category["id"]]},
    ).json()
    product = client.post(
        "/api/v1/admin/products",
        json={
            "sku": "GPU-4060",
            "name": "RTX 4060",
            "brand_id": brand["id"],
            "category_id": category["id"],
        },
    ).json()
    return product["id"]


def _supplier_payload(**overrides: object) -> dict:
    data = {
        "business_name": "Distribuidora Tech SA",
        "commercial_name": "TechDist",
        "tax_id": "1790012345001",
        "tax_id_type": "RUC",
        "email": "ventas@techdist.example.com",
        "website_url": "https://techdist.example.com",
        "city": "Quito",
        "province": "Pichincha",
        "country": "Ecuador",
        "contact_name": "Ana Pérez",
    }
    data.update(overrides)
    return data


def test_create_and_list_supplier(client: TestClient, admin_user: User) -> None:
    _login(client, admin_user)
    response = client.post("/api/v1/admin/suppliers", json=_supplier_payload())
    assert response.status_code == 201
    data = response.json()
    assert data["business_name"] == "Distribuidora Tech SA"
    assert data["tax_id"] == "1790012345001"
    assert data["tax_id_type"] == "RUC"

    listed = client.get("/api/v1/admin/suppliers")
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1


def test_update_supplier(client: TestClient, admin_user: User) -> None:
    _login(client, admin_user)
    created = client.post("/api/v1/admin/suppliers", json=_supplier_payload()).json()
    response = client.patch(
        f"/api/v1/admin/suppliers/{created['id']}",
        json={"commercial_name": "Tech Dist Ecuador", "phone": "+593999999999"},
    )
    assert response.status_code == 200
    assert response.json()["commercial_name"] == "Tech Dist Ecuador"
    assert response.json()["phone"] == "+593999999999"


def test_duplicate_tax_id(client: TestClient, admin_user: User) -> None:
    _login(client, admin_user)
    assert client.post("/api/v1/admin/suppliers", json=_supplier_payload()).status_code == 201
    response = client.post(
        "/api/v1/admin/suppliers",
        json=_supplier_payload(business_name="Otro"),
    )
    assert response.status_code == 409


def test_invalid_email_and_website(client: TestClient, admin_user: User) -> None:
    _login(client, admin_user)
    bad_email = client.post(
        "/api/v1/admin/suppliers",
        json=_supplier_payload(email="not-an-email", tax_id="111"),
    )
    assert bad_email.status_code == 422

    bad_web = client.post(
        "/api/v1/admin/suppliers",
        json=_supplier_payload(website_url="notaurl", tax_id="222"),
    )
    assert bad_web.status_code == 422


def test_soft_delete_supplier(client: TestClient, admin_user: User) -> None:
    _login(client, admin_user)
    created = client.post("/api/v1/admin/suppliers", json=_supplier_payload()).json()
    response = client.delete(f"/api/v1/admin/suppliers/{created['id']}")
    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_customer_cannot_manage_suppliers(
    client: TestClient, customer_user: User
) -> None:
    _login(client, customer_user)
    response = client.post("/api/v1/admin/suppliers", json=_supplier_payload())
    assert response.status_code == 403


def test_create_supplier_product(client: TestClient, admin_user: User) -> None:
    _login(client, admin_user)
    product_id = _seed_product(client)
    supplier = client.post("/api/v1/admin/suppliers", json=_supplier_payload()).json()

    response = client.post(
        f"/api/v1/admin/suppliers/{supplier['id']}/products",
        json={
            "product_id": product_id,
            "supplier_sku": "rtx4060-a",
            "cost": "280.00",
            "currency": "USD",
            "availability": "IN_STOCK",
            "lead_time_days": 2,
            "minimum_order_quantity": 1,
            "supplier_url": "https://techdist.example.com/rtx4060",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["supplier_sku"] == "RTX4060-A"
    assert Decimal(data["cost"]) == Decimal("280.0000")
    assert data["availability"] == "IN_STOCK"
    assert data["last_checked_at"] is not None


def test_supplier_product_missing_entities(client: TestClient, admin_user: User) -> None:
    _login(client, admin_user)
    product_id = _seed_product(client)
    missing_supplier = client.post(
        "/api/v1/admin/suppliers/00000000-0000-0000-0000-000000000099/products",
        json={"product_id": product_id, "cost": "10.00"},
    )
    assert missing_supplier.status_code == 404

    supplier = client.post("/api/v1/admin/suppliers", json=_supplier_payload()).json()
    missing_product = client.post(
        f"/api/v1/admin/suppliers/{supplier['id']}/products",
        json={"product_id": "00000000-0000-0000-0000-000000000088", "cost": "10.00"},
    )
    assert missing_product.status_code == 404


def test_inactive_supplier_or_product_blocked(client: TestClient, admin_user: User) -> None:
    _login(client, admin_user)
    product_id = _seed_product(client)
    supplier = client.post("/api/v1/admin/suppliers", json=_supplier_payload()).json()
    client.delete(f"/api/v1/admin/suppliers/{supplier['id']}")

    blocked = client.post(
        f"/api/v1/admin/suppliers/{supplier['id']}/products",
        json={"product_id": product_id, "cost": "10.00"},
    )
    assert blocked.status_code == 400

    active = client.post(
        "/api/v1/admin/suppliers",
        json=_supplier_payload(tax_id="1790099999001", business_name="Activo"),
    ).json()
    client.delete(f"/api/v1/admin/products/{product_id}")
    blocked_product = client.post(
        f"/api/v1/admin/suppliers/{active['id']}/products",
        json={"product_id": product_id, "cost": "10.00"},
    )
    assert blocked_product.status_code == 400


def test_supplier_product_validation(client: TestClient, admin_user: User) -> None:
    _login(client, admin_user)
    product_id = _seed_product(client)
    supplier = client.post("/api/v1/admin/suppliers", json=_supplier_payload()).json()
    base = f"/api/v1/admin/suppliers/{supplier['id']}/products"

    assert (
        client.post(base, json={"product_id": product_id, "cost": "-1"}).status_code == 422
    )
    assert (
        client.post(
            base, json={"product_id": product_id, "cost": "1", "lead_time_days": -1}
        ).status_code
        == 422
    )
    assert (
        client.post(
            base, json={"product_id": product_id, "cost": "1", "minimum_order_quantity": 0}
        ).status_code
        == 422
    )
    assert (
        client.post(
            base, json={"product_id": product_id, "cost": "1", "currency": "EUR"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            base, json={"product_id": product_id, "cost": "1", "availability": "LOTS"}
        ).status_code
        == 422
    )


def test_duplicate_supplier_product_relation(client: TestClient, admin_user: User) -> None:
    _login(client, admin_user)
    product_id = _seed_product(client)
    supplier = client.post("/api/v1/admin/suppliers", json=_supplier_payload()).json()
    payload = {"product_id": product_id, "cost": "100.00"}
    assert (
        client.post(f"/api/v1/admin/suppliers/{supplier['id']}/products", json=payload).status_code
        == 201
    )
    dup = client.post(f"/api/v1/admin/suppliers/{supplier['id']}/products", json=payload)
    assert dup.status_code == 409


def test_update_and_soft_delete_supplier_product(
    client: TestClient, admin_user: User
) -> None:
    _login(client, admin_user)
    product_id = _seed_product(client)
    supplier = client.post("/api/v1/admin/suppliers", json=_supplier_payload()).json()
    created = client.post(
        f"/api/v1/admin/suppliers/{supplier['id']}/products",
        json={"product_id": product_id, "cost": "100.00", "availability": "UNKNOWN"},
    ).json()

    updated = client.patch(
        f"/api/v1/admin/suppliers/{supplier['id']}/products/{created['id']}",
        json={"cost": "95.50", "availability": "LOW_STOCK", "lead_time_days": 5},
    )
    assert updated.status_code == 200
    assert Decimal(updated.json()["cost"]) == Decimal("95.5000")
    assert updated.json()["availability"] == "LOW_STOCK"
    assert updated.json()["last_checked_at"] is not None

    deleted = client.delete(
        f"/api/v1/admin/suppliers/{supplier['id']}/products/{created['id']}"
    )
    assert deleted.status_code == 200
    assert deleted.json()["is_active"] is False


def test_product_suppliers_multiple_costs(client: TestClient, admin_user: User) -> None:
    _login(client, admin_user)
    product_id = _seed_product(client)
    s1 = client.post("/api/v1/admin/suppliers", json=_supplier_payload()).json()
    s2 = client.post(
        "/api/v1/admin/suppliers",
        json=_supplier_payload(tax_id="1790088888001", business_name="Segundo Proveedor"),
    ).json()

    client.post(
        f"/api/v1/admin/suppliers/{s1['id']}/products",
        json={"product_id": product_id, "cost": "280.00", "supplier_sku": "A"},
    )
    client.post(
        f"/api/v1/admin/suppliers/{s2['id']}/products",
        json={"product_id": product_id, "cost": "275.50", "supplier_sku": "B"},
    )

    response = client.get(f"/api/v1/admin/products/{product_id}/suppliers")
    assert response.status_code == 200
    data = response.json()
    assert data["product"]["name"] == "RTX 4060"
    assert len(data["suppliers"]) == 2
    costs = [Decimal(item["cost"]) for item in data["suppliers"]]
    assert costs == sorted(costs)
    assert Decimal("275.5000") in costs
    assert Decimal("280.0000") in costs
