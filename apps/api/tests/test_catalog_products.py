from fastapi.testclient import TestClient

from app.modules.roles.models import User


def _login(client: TestClient, user: User) -> None:
    client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "secure-password"},
    )


def _seed_brand_category(client: TestClient) -> tuple[str, str]:
    category = client.post("/api/v1/admin/categories", json={"name": "Laptops"}).json()
    brand = client.post(
        "/api/v1/admin/brands",
        json={"name": "ASUS", "category_ids": [category["id"]]},
    ).json()
    return brand["id"], category["id"]


def test_create_product_with_images_and_specs(client: TestClient, admin_user: User) -> None:
    _login(client, admin_user)
    brand_id, category_id = _seed_brand_category(client)

    response = client.post(
        "/api/v1/admin/products",
        json={
            "sku": "lap-asus-001",
            "name": "ASUS TUF Gaming A15",
            "short_description": "Laptop gaming",
            "brand_id": brand_id,
            "category_id": category_id,
            "specifications": {"ram": "16 GB", "gpu": "RTX 4060"},
            "images": [
                {
                    "url": "https://cdn.example.com/a15-1.jpg",
                    "alt_text": "Front",
                    "sort_order": 1,
                    "is_primary": True,
                },
                {
                    "url": "https://cdn.example.com/a15-2.jpg",
                    "alt_text": "Side",
                    "sort_order": 2,
                    "is_primary": False,
                },
            ],
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["sku"] == "LAP-ASUS-001"
    assert data["slug"] == "asus-tuf-gaming-a15"
    assert data["brand"]["name"] == "ASUS"
    assert data["category"]["slug"] == "laptops"
    assert data["specifications"]["gpu"] == "RTX 4060"
    assert len(data["images"]) == 2
    assert data["images"][0]["is_primary"] is True


def test_duplicate_sku_rejected(client: TestClient, admin_user: User) -> None:
    _login(client, admin_user)
    brand_id, category_id = _seed_brand_category(client)
    payload = {
        "sku": "DUP-001",
        "name": "Product One",
        "brand_id": brand_id,
        "category_id": category_id,
    }
    assert client.post("/api/v1/admin/products", json=payload).status_code == 201
    assert client.post("/api/v1/admin/products", json=payload).status_code == 409


def test_missing_brand_or_category(client: TestClient, admin_user: User) -> None:
    _login(client, admin_user)
    brand_id, category_id = _seed_brand_category(client)
    bad_brand = client.post(
        "/api/v1/admin/products",
        json={
            "sku": "X-1",
            "name": "No Brand",
            "brand_id": "00000000-0000-0000-0000-000000000099",
            "category_id": category_id,
        },
    )
    assert bad_brand.status_code == 400

    bad_category = client.post(
        "/api/v1/admin/products",
        json={
            "sku": "X-2",
            "name": "No Category",
            "brand_id": brand_id,
            "category_id": "00000000-0000-0000-0000-000000000099",
        },
    )
    assert bad_category.status_code == 400


def test_product_filters_and_pagination(client: TestClient, admin_user: User) -> None:
    _login(client, admin_user)
    brand_id, category_id = _seed_brand_category(client)
    other_brand = client.post(
        "/api/v1/admin/brands",
        json={"name": "Lenovo", "category_ids": [category_id]},
    ).json()

    for i in range(3):
        client.post(
            "/api/v1/admin/products",
            json={
                "sku": f"ASUS-{i}",
                "name": f"ASUS Product {i}",
                "brand_id": brand_id,
                "category_id": category_id,
            },
        )
    client.post(
        "/api/v1/admin/products",
        json={
            "sku": "LEN-1",
            "name": "Lenovo Product",
            "brand_id": other_brand["id"],
            "category_id": category_id,
        },
    )

    filtered = client.get("/api/v1/products", params={"brand": "asus"})
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 3

    page = client.get("/api/v1/products", params={"page": 1, "page_size": 2})
    assert page.status_code == 200
    assert len(page.json()["items"]) == 2
    assert page.json()["total_pages"] >= 2


def test_product_soft_delete_hides_from_public(client: TestClient, admin_user: User) -> None:
    _login(client, admin_user)
    brand_id, category_id = _seed_brand_category(client)
    created = client.post(
        "/api/v1/admin/products",
        json={
            "sku": "DEL-1",
            "name": "To Delete",
            "brand_id": brand_id,
            "category_id": category_id,
        },
    ).json()

    deleted = client.delete(f"/api/v1/admin/products/{created['id']}")
    assert deleted.status_code == 200
    assert deleted.json()["is_active"] is False

    public = client.get(f"/api/v1/products/{created['slug']}")
    assert public.status_code == 404


def test_cannot_soft_delete_category_with_active_products(
    client: TestClient, admin_user: User
) -> None:
    _login(client, admin_user)
    brand_id, category_id = _seed_brand_category(client)
    client.post(
        "/api/v1/admin/products",
        json={
            "sku": "KEEP-1",
            "name": "Keep",
            "brand_id": brand_id,
            "category_id": category_id,
        },
    )
    response = client.delete(f"/api/v1/admin/categories/{category_id}")
    assert response.status_code == 409


def test_customer_cannot_modify_product(client: TestClient, customer_user: User) -> None:
    _login(client, customer_user)
    response = client.post(
        "/api/v1/admin/products",
        json={
            "sku": "NOPE",
            "name": "Nope",
            "brand_id": "00000000-0000-0000-0000-000000000001",
            "category_id": "00000000-0000-0000-0000-000000000001",
        },
    )
    assert response.status_code == 403


def test_update_product_images_order(client: TestClient, admin_user: User) -> None:
    _login(client, admin_user)
    brand_id, category_id = _seed_brand_category(client)
    created = client.post(
        "/api/v1/admin/products",
        json={
            "sku": "IMG-1",
            "name": "Image Product",
            "brand_id": brand_id,
            "category_id": category_id,
            "images": [
                {"url": "https://cdn.example.com/1.jpg", "sort_order": 0, "is_primary": True}
            ],
        },
    ).json()

    updated = client.patch(
        f"/api/v1/admin/products/{created['id']}",
        json={
            "images": [
                {"url": "https://cdn.example.com/a.jpg", "sort_order": 2, "is_primary": False},
                {"url": "https://cdn.example.com/b.jpg", "sort_order": 1, "is_primary": True},
            ]
        },
    )
    assert updated.status_code == 200
    images = updated.json()["images"]
    assert len(images) == 2
    assert sum(1 for i in images if i["is_primary"]) == 1
