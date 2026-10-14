from fastapi.testclient import TestClient

from app.modules.roles.models import User


def _login(client: TestClient, user: User) -> None:
    client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "secure-password"},
    )


def _seed_product(client: TestClient, sku: str = "GPU-4060") -> str:
    category = client.post(
        "/api/v1/admin/categories", json={"name": f"Cat-{sku}"}
    ).json()
    brand = client.post(
        "/api/v1/admin/brands",
        json={"name": f"Brand-{sku}", "category_ids": [category["id"]]},
    ).json()
    product = client.post(
        "/api/v1/admin/products",
        json={
            "sku": sku,
            "name": f"Product {sku}",
            "brand_id": brand["id"],
            "category_id": category["id"],
        },
    ).json()
    return product["id"]


def test_create_inventory_and_duplicate(client: TestClient, admin_user: User) -> None:
    _login(client, admin_user)
    product_id = _seed_product(client)
    created = client.post(
        "/api/v1/admin/inventory",
        json={"product_id": product_id, "reorder_point": 3, "reorder_quantity": 10},
    )
    assert created.status_code == 201
    data = created.json()
    assert data["quantity"] == 0
    assert data["available_quantity"] == 0
    assert data["reorder_point"] == 3

    dup = client.post("/api/v1/admin/inventory", json={"product_id": product_id})
    assert dup.status_code == 409


def test_purchase_increments_and_creates_movement(
    client: TestClient, admin_user: User
) -> None:
    _login(client, admin_user)
    product_id = _seed_product(client)
    client.post("/api/v1/admin/inventory", json={"product_id": product_id})

    response = client.post(
        f"/api/v1/admin/inventory/{product_id}/purchase",
        json={"quantity": 10, "notes": "PO-1"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["inventory"]["quantity"] == 10
    assert body["inventory"]["available_quantity"] == 10
    assert body["movement"]["type"] == "PURCHASE"
    assert body["movement"]["quantity"] == 10
    assert body["movement"]["signed_quantity"] == 10
    assert body["movement"]["created_by"] == str(admin_user.id)

    history = client.get(f"/api/v1/admin/inventory/{product_id}/movements")
    assert history.status_code == 200
    assert history.json()["total"] == 1


def test_sale_validations(client: TestClient, admin_user: User) -> None:
    _login(client, admin_user)
    product_id = _seed_product(client)
    client.post(
        f"/api/v1/admin/inventory/{product_id}/purchase", json={"quantity": 5}
    )

    bad = client.post(
        f"/api/v1/admin/inventory/{product_id}/sale", json={"quantity": 6}
    )
    assert bad.status_code == 409
    inv = client.get(f"/api/v1/admin/inventory/{product_id}").json()
    assert inv["quantity"] == 5

    ok = client.post(
        f"/api/v1/admin/inventory/{product_id}/sale", json={"quantity": 2}
    )
    assert ok.status_code == 200
    assert ok.json()["inventory"]["quantity"] == 3
    assert ok.json()["inventory"]["available_quantity"] == 3


def test_reservation_and_release(client: TestClient, admin_user: User) -> None:
    _login(client, admin_user)
    product_id = _seed_product(client)
    client.post(
        f"/api/v1/admin/inventory/{product_id}/purchase", json={"quantity": 5}
    )

    reserved = client.post(
        f"/api/v1/admin/inventory/{product_id}/reserve", json={"quantity": 2}
    )
    assert reserved.status_code == 200
    assert reserved.json()["inventory"]["reserved_quantity"] == 2
    assert reserved.json()["inventory"]["available_quantity"] == 3

    over = client.post(
        f"/api/v1/admin/inventory/{product_id}/reserve", json={"quantity": 4}
    )
    assert over.status_code == 409

    released = client.post(
        f"/api/v1/admin/inventory/{product_id}/release", json={"quantity": 1}
    )
    assert released.status_code == 200
    assert released.json()["inventory"]["reserved_quantity"] == 1

    over_release = client.post(
        f"/api/v1/admin/inventory/{product_id}/release", json={"quantity": 5}
    )
    assert over_release.status_code == 409


def test_reservation_concurrency_serialized(client: TestClient, admin_user: User) -> None:
    """With row lock, only one of two competing reserves for last unit succeeds."""
    _login(client, admin_user)
    product_id = _seed_product(client, sku="CONC-1")
    client.post(
        f"/api/v1/admin/inventory/{product_id}/purchase", json={"quantity": 1}
    )

    # Sequential simulation of race: first takes available, second must fail
    first = client.post(
        f"/api/v1/admin/inventory/{product_id}/reserve", json={"quantity": 1}
    )
    second = client.post(
        f"/api/v1/admin/inventory/{product_id}/reserve", json={"quantity": 1}
    )
    assert first.status_code == 200
    assert second.status_code == 409
    inv = client.get(f"/api/v1/admin/inventory/{product_id}").json()
    assert inv["reserved_quantity"] == 1
    assert inv["available_quantity"] == 0


def test_adjustment_up_and_down(client: TestClient, admin_user: User) -> None:
    _login(client, admin_user)
    product_id = _seed_product(client)
    client.post(
        f"/api/v1/admin/inventory/{product_id}/purchase", json={"quantity": 10}
    )

    up = client.post(
        f"/api/v1/admin/inventory/{product_id}/adjust", json={"delta": 5}
    )
    assert up.status_code == 200
    assert up.json()["inventory"]["quantity"] == 15
    assert up.json()["movement"]["signed_quantity"] == 5

    down = client.post(
        f"/api/v1/admin/inventory/{product_id}/adjust", json={"delta": -4}
    )
    assert down.status_code == 200
    assert down.json()["inventory"]["quantity"] == 11
    assert down.json()["movement"]["signed_quantity"] == -4

    neg = client.post(
        f"/api/v1/admin/inventory/{product_id}/adjust", json={"delta": -100}
    )
    assert neg.status_code == 409


def test_return_and_damage(client: TestClient, admin_user: User) -> None:
    _login(client, admin_user)
    product_id = _seed_product(client)
    client.post(
        f"/api/v1/admin/inventory/{product_id}/purchase", json={"quantity": 8}
    )

    returned = client.post(
        f"/api/v1/admin/inventory/{product_id}/return", json={"quantity": 2}
    )
    assert returned.status_code == 200
    assert returned.json()["inventory"]["quantity"] == 10

    damaged = client.post(
        f"/api/v1/admin/inventory/{product_id}/damage", json={"quantity": 3}
    )
    assert damaged.status_code == 200
    assert damaged.json()["inventory"]["quantity"] == 7

    over = client.post(
        f"/api/v1/admin/inventory/{product_id}/damage", json={"quantity": 100}
    )
    assert over.status_code == 409


def test_low_stock(client: TestClient, admin_user: User) -> None:
    _login(client, admin_user)
    low_id = _seed_product(client, sku="LOW-1")
    high_id = _seed_product(client, sku="HIGH-1")

    client.post(
        "/api/v1/admin/inventory",
        json={"product_id": low_id, "reorder_point": 5, "reorder_quantity": 20},
    )
    client.post(
        f"/api/v1/admin/inventory/{low_id}/purchase", json={"quantity": 4}
    )

    client.post(
        "/api/v1/admin/inventory",
        json={"product_id": high_id, "reorder_point": 2, "reorder_quantity": 10},
    )
    client.post(
        f"/api/v1/admin/inventory/{high_id}/purchase", json={"quantity": 10}
    )

    response = client.get("/api/v1/admin/inventory/low-stock")
    assert response.status_code == 200
    ids = {item["product_id"] for item in response.json()}
    assert low_id in ids
    assert high_id not in ids


def test_customer_forbidden(
    client: TestClient, customer_user: User, admin_user: User
) -> None:
    _login(client, admin_user)
    product_id = _seed_product(client)
    client.post(
        f"/api/v1/admin/inventory/{product_id}/purchase", json={"quantity": 1}
    )

    client.post("/api/v1/auth/logout")
    _login(client, customer_user)
    assert (
        client.post(
            f"/api/v1/admin/inventory/{product_id}/purchase", json={"quantity": 1}
        ).status_code
        == 403
    )
    assert client.get("/api/v1/admin/inventory").status_code == 403


def test_super_admin_can_operate(
    client: TestClient, super_admin_user: User
) -> None:
    _login(client, super_admin_user)
    product_id = _seed_product(client, sku="SA-1")
    response = client.post(
        f"/api/v1/admin/inventory/{product_id}/purchase", json={"quantity": 3}
    )
    assert response.status_code == 200


def test_failed_sale_does_not_mutate_stock(
    client: TestClient, admin_user: User
) -> None:
    _login(client, admin_user)
    product_id = _seed_product(client, sku="RB-1")
    client.post(
        f"/api/v1/admin/inventory/{product_id}/purchase", json={"quantity": 2}
    )
    assert (
        client.post(
            f"/api/v1/admin/inventory/{product_id}/sale", json={"quantity": 9}
        ).status_code
        == 409
    )
    inv = client.get(f"/api/v1/admin/inventory/{product_id}").json()
    assert inv["quantity"] == 2
    assert client.get(f"/api/v1/admin/inventory/{product_id}/movements").json()["total"] == 1


def test_invalid_movement_quantity(client: TestClient, admin_user: User) -> None:
    _login(client, admin_user)
    product_id = _seed_product(client, sku="INV-Q")
    assert (
        client.post(
            f"/api/v1/admin/inventory/{product_id}/purchase", json={"quantity": 0}
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/api/v1/admin/inventory/{product_id}/purchase", json={"quantity": -1}
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/api/v1/admin/inventory/{product_id}/adjust", json={"delta": 0}
        ).status_code
        == 422
    )
