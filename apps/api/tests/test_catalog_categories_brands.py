from fastapi.testclient import TestClient

from app.modules.roles.models import User


def _login(client: TestClient, user: User) -> None:
    client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "secure-password"},
    )


def test_create_category_hierarchy(client: TestClient, admin_user: User) -> None:
    _login(client, admin_user)
    parent = client.post(
        "/api/v1/admin/categories",
        json={"name": "Computación"},
    )
    assert parent.status_code == 201
    parent_id = parent.json()["id"]

    child = client.post(
        "/api/v1/admin/categories",
        json={"name": "Componentes", "parent_id": parent_id},
    )
    assert child.status_code == 201
    assert child.json()["parent_id"] == parent_id
    assert child.json()["slug"] == "componentes"

    listed = client.get("/api/v1/categories")
    assert listed.status_code == 200
    assert len(listed.json()) >= 2


def test_category_cycle_rejected(client: TestClient, admin_user: User) -> None:
    _login(client, admin_user)
    parent = client.post("/api/v1/admin/categories", json={"name": "Root Cat"}).json()
    child = client.post(
        "/api/v1/admin/categories",
        json={"name": "Child Cat", "parent_id": parent["id"]},
    ).json()
    response = client.patch(
        f"/api/v1/admin/categories/{parent['id']}",
        json={"parent_id": child["id"]},
    )
    assert response.status_code == 400
    assert "Circular" in response.json()["detail"]


def test_category_missing_parent(client: TestClient, admin_user: User) -> None:
    _login(client, admin_user)
    response = client.post(
        "/api/v1/admin/categories",
        json={"name": "Orphan", "parent_id": "00000000-0000-0000-0000-000000000099"},
    )
    assert response.status_code == 400


def test_customer_cannot_modify_category(client: TestClient, customer_user: User) -> None:
    _login(client, customer_user)
    response = client.post("/api/v1/admin/categories", json={"name": "Hack"})
    assert response.status_code == 403


def test_brand_crud_and_duplicate_slug(client: TestClient, admin_user: User) -> None:
    _login(client, admin_user)
    tech = client.post("/api/v1/admin/categories", json={"name": "Tech Crud"}).json()
    created = client.post(
        "/api/v1/admin/brands",
        json={
            "name": "ASUS",
            "website_url": "https://asus.com",
            "logo_url": "https://cdn.example.com/asus.png",
            "category_ids": [tech["id"]],
        },
    )
    assert created.status_code == 201
    assert created.json()["slug"] == "asus"
    assert created.json()["logo_url"] == "https://cdn.example.com/asus.png"
    assert created.json()["category_ids"] == [tech["id"]]

    updated = client.patch(
        f"/api/v1/admin/brands/{created.json()['id']}",
        json={"description": "Gaming brand"},
    )
    assert updated.status_code == 200
    assert updated.json()["description"] == "Gaming brand"
    assert updated.json()["category_ids"] == [tech["id"]]

    # Same name generates unique slug
    second = client.post("/api/v1/admin/brands", json={"name": "ASUS"})
    assert second.status_code == 201
    assert second.json()["slug"] == "asus-2"
    assert second.json()["category_ids"] == []


def test_category_image_url(client: TestClient, admin_user: User) -> None:
    _login(client, admin_user)
    created = client.post(
        "/api/v1/admin/categories",
        json={
            "name": "Filamentos",
            "image_url": "https://cdn.example.com/filamentos.jpg",
        },
    )
    assert created.status_code == 201
    assert created.json()["image_url"] == "https://cdn.example.com/filamentos.jpg"

    updated = client.patch(
        f"/api/v1/admin/categories/{created.json()['id']}",
        json={"image_url": "https://cdn.example.com/filamentos-v2.jpg"},
    )
    assert updated.status_code == 200
    assert updated.json()["image_url"] == "https://cdn.example.com/filamentos-v2.jpg"

    bad = client.post(
        "/api/v1/admin/categories",
        json={"name": "Bad Image", "image_url": "not-a-url"},
    )
    assert bad.status_code == 422


def test_customer_cannot_modify_brand(client: TestClient, customer_user: User) -> None:
    _login(client, customer_user)
    response = client.post("/api/v1/admin/brands", json={"name": "Nope"})
    assert response.status_code == 403


def test_list_brands_filtered_by_category(client: TestClient, admin_user: User) -> None:
    _login(client, admin_user)
    ropa = client.post("/api/v1/admin/categories", json={"name": "Ropa"}).json()
    tech = client.post("/api/v1/admin/categories", json={"name": "Tecnología"}).json()
    nike = client.post(
        "/api/v1/admin/brands",
        json={"name": "Nike", "category_ids": [ropa["id"]]},
    ).json()
    samsung = client.post(
        "/api/v1/admin/brands",
        json={"name": "Samsung", "category_ids": [tech["id"]]},
    ).json()

    assert (
        client.post(
            "/api/v1/admin/products",
            json={
                "sku": "NIKE-ROPA-1",
                "name": "Nike Shirt",
                "brand_id": nike["id"],
                "category_id": ropa["id"],
            },
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/api/v1/admin/products",
            json={
                "sku": "SAMSUNG-TECH-1",
                "name": "Samsung Phone",
                "brand_id": samsung["id"],
                "category_id": tech["id"],
            },
        ).status_code
        == 201
    )

    all_brands = client.get("/api/v1/brands")
    assert all_brands.status_code == 200
    all_slugs = {b["slug"] for b in all_brands.json()}
    assert "nike" in all_slugs
    assert "samsung" in all_slugs

    ropa_brands = client.get("/api/v1/brands", params={"category": "ropa"})
    assert ropa_brands.status_code == 200
    ropa_slugs = {b["slug"] for b in ropa_brands.json()}
    assert ropa_slugs == {"nike"}

    tech_brands = client.get("/api/v1/brands", params={"category": "tecnologia"})
    assert tech_brands.status_code == 200
    tech_slugs = {b["slug"] for b in tech_brands.json()}
    assert tech_slugs == {"samsung"}

    admin_tech = client.get("/api/v1/admin/brands", params={"category": "tecnologia"})
    assert admin_tech.status_code == 200
    assert {b["slug"] for b in admin_tech.json()["items"]} == {"samsung"}


def test_brand_category_affinity_inheritance_and_rejection(
    client: TestClient, admin_user: User
) -> None:
    """Brand linked to parent is valid on children; rejected on unrelated trees."""
    _login(client, admin_user)
    tech = client.post("/api/v1/admin/categories", json={"name": "Tecnología"}).json()
    phones = client.post(
        "/api/v1/admin/categories",
        json={"name": "Celulares", "parent_id": tech["id"]},
    ).json()
    ropa = client.post("/api/v1/admin/categories", json={"name": "Ropa"}).json()
    pants = client.post(
        "/api/v1/admin/categories",
        json={"name": "Pantalones", "parent_id": ropa["id"]},
    ).json()
    samsung = client.post(
        "/api/v1/admin/brands",
        json={"name": "Samsung", "category_ids": [tech["id"]]},
    ).json()

    ok = client.post(
        "/api/v1/admin/products",
        json={
            "sku": "SAM-PHONE-1",
            "name": "Galaxy S",
            "brand_id": samsung["id"],
            "category_id": phones["id"],
        },
    )
    assert ok.status_code == 201

    rejected = client.post(
        "/api/v1/admin/products",
        json={
            "sku": "SAM-PANTS-1",
            "name": "Samsung Pants",
            "brand_id": samsung["id"],
            "category_id": pants["id"],
        },
    )
    assert rejected.status_code == 400
    assert "not allowed" in rejected.json()["detail"].lower()

    tech_brands = client.get("/api/v1/brands", params={"category": "tecnologia"})
    assert {b["slug"] for b in tech_brands.json()} == {"samsung"}
    phone_brands = client.get("/api/v1/brands", params={"category": "celulares"})
    assert {b["slug"] for b in phone_brands.json()} == {"samsung"}
    pants_brands = client.get("/api/v1/brands", params={"category": "pantalones"})
    assert pants_brands.json() == []


def test_category_subtree_includes_nested_products_and_brands(
    client: TestClient, admin_user: User
) -> None:
    """Parent category filter includes children / grandchildren / great-grandchildren."""
    _login(client, admin_user)
    root = client.post("/api/v1/admin/categories", json={"name": "Impresión 3D"}).json()
    child = client.post(
        "/api/v1/admin/categories",
        json={"name": "Filamentos", "parent_id": root["id"]},
    ).json()
    grandchild = client.post(
        "/api/v1/admin/categories",
        json={"name": "PLA", "parent_id": child["id"]},
    ).json()
    great = client.post(
        "/api/v1/admin/categories",
        json={"name": "PLA Premium", "parent_id": grandchild["id"]},
    ).json()
    laptops = client.post("/api/v1/admin/categories", json={"name": "Laptops"}).json()
    brand = client.post(
        "/api/v1/admin/brands",
        json={"name": "eSun", "category_ids": [root["id"]]},
    ).json()
    other_brand = client.post(
        "/api/v1/admin/brands",
        json={"name": "Dell", "category_ids": [laptops["id"]]},
    ).json()

    assert (
        client.post(
            "/api/v1/admin/products",
            json={
                "sku": "PLA-PREM-1",
                "name": "PLA Premium Black",
                "brand_id": brand["id"],
                "category_id": great["id"],
            },
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/api/v1/admin/products",
            json={
                "sku": "DELL-LAP-1",
                "name": "Dell XPS",
                "brand_id": other_brand["id"],
                "category_id": laptops["id"],
            },
        ).status_code
        == 201
    )

    products = client.get("/api/v1/products", params={"category": "impresion-3d"})
    assert products.status_code == 200
    assert products.json()["total"] == 1
    assert products.json()["items"][0]["slug"] == "pla-premium-black"

    brands = client.get("/api/v1/brands", params={"category": "impresion-3d"})
    assert brands.status_code == 200
    assert {b["slug"] for b in brands.json()} == {"esun"}
