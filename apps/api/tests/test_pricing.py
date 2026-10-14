from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient

from app.modules.pricing.service import calculate_margin
from app.modules.roles.models import User


def _login(client: TestClient, user: User) -> None:
    client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "secure-password"},
    )


def _seed_product(client: TestClient, sku: str = "LAP-1") -> dict:
    category = client.post(
        "/api/v1/admin/categories", json={"name": f"Cat-{sku}"}
    ).json()
    brand = client.post(
        "/api/v1/admin/brands",
        json={"name": f"Brand-{sku}", "category_ids": [category["id"]]},
    ).json()
    return client.post(
        "/api/v1/admin/products",
        json={
            "sku": sku,
            "name": f"Product {sku}",
            "brand_id": brand["id"],
            "category_id": category["id"],
        },
    ).json()


def test_create_price_types(client: TestClient, admin_user: User) -> None:
    _login(client, admin_user)
    product = _seed_product(client)
    pid = product["id"]

    for price_type, amount in [
        ("RETAIL", "350.00"),
        ("WHOLESALE", "300.00"),
        ("PROMOTIONAL", "320.00"),
    ]:
        response = client.post(
            f"/api/v1/admin/products/{pid}/prices",
            json={
                "price_type": price_type,
                "amount": amount,
                "currency": "USD",
                "starts_at": datetime.now(UTC).isoformat(),
            },
        )
        assert response.status_code == 201, response.text
        assert response.json()["price_type"] == price_type
        assert Decimal(response.json()["amount"]) == Decimal(amount)


def test_negative_amount_rejected(client: TestClient, admin_user: User) -> None:
    _login(client, admin_user)
    product = _seed_product(client, sku="NEG-1")
    response = client.post(
        f"/api/v1/admin/products/{product['id']}/prices",
        json={"amount": "-1", "price_type": "RETAIL"},
    )
    assert response.status_code == 422


def test_overlap_rejected(client: TestClient, admin_user: User) -> None:
    _login(client, admin_user)
    product = _seed_product(client, sku="OVL-1")
    pid = product["id"]
    start = datetime.now(UTC) - timedelta(days=1)
    assert (
        client.post(
            f"/api/v1/admin/products/{pid}/prices",
            json={
                "price_type": "RETAIL",
                "amount": "350",
                "starts_at": start.isoformat(),
                "ends_at": (start + timedelta(days=30)).isoformat(),
            },
        ).status_code
        == 201
    )
    overlap = client.post(
        f"/api/v1/admin/products/{pid}/prices",
        json={
            "price_type": "RETAIL",
            "amount": "340",
            "starts_at": (start + timedelta(days=10)).isoformat(),
            "ends_at": (start + timedelta(days=40)).isoformat(),
        },
    )
    assert overlap.status_code == 409


def test_current_price_validity(client: TestClient, admin_user: User) -> None:
    _login(client, admin_user)
    product = _seed_product(client, sku="CUR-1")
    pid = product["id"]
    now = datetime.now(UTC)

    # expired
    client.post(
        f"/api/v1/admin/products/{pid}/prices",
        json={
            "price_type": "RETAIL",
            "amount": "100",
            "starts_at": (now - timedelta(days=20)).isoformat(),
            "ends_at": (now - timedelta(days=10)).isoformat(),
        },
    )
    # future
    client.post(
        f"/api/v1/admin/products/{pid}/prices",
        json={
            "price_type": "RETAIL",
            "amount": "200",
            "starts_at": (now + timedelta(days=5)).isoformat(),
        },
    )
    # current
    client.post(
        f"/api/v1/admin/products/{pid}/prices",
        json={
            "price_type": "RETAIL",
            "amount": "150",
            "starts_at": (now - timedelta(days=2)).isoformat(),
            "ends_at": (now + timedelta(days=2)).isoformat(),
        },
    )

    current = client.get(f"/api/v1/admin/products/{pid}/prices/current")
    assert current.status_code == 200
    assert Decimal(current.json()["amount"]) == Decimal("150.0000")

    public = client.get(f"/api/v1/products/{product['slug']}")
    assert public.status_code == 200
    assert public.json()["price"]["amount"] == "150.0000"
    assert public.json()["price"]["price_type"] == "RETAIL"


def test_no_current_price_null(client: TestClient, admin_user: User) -> None:
    _login(client, admin_user)
    product = _seed_product(client, sku="NOP-1")
    current = client.get(f"/api/v1/admin/products/{product['id']}/prices/current")
    assert current.status_code == 200
    assert current.json() is None
    public = client.get(f"/api/v1/products/{product['slug']}")
    assert public.json()["price"] is None


def test_price_history_preserved(client: TestClient, admin_user: User) -> None:
    _login(client, admin_user)
    product = _seed_product(client, sku="HIS-1")
    pid = product["id"]
    now = datetime.now(UTC)

    first = client.post(
        f"/api/v1/admin/products/{pid}/prices",
        json={
            "price_type": "RETAIL",
            "amount": "350",
            "starts_at": (now - timedelta(days=30)).isoformat(),
            "ends_at": (now - timedelta(days=15)).isoformat(),
        },
    ).json()
    second = client.post(
        f"/api/v1/admin/products/{pid}/prices",
        json={
            "price_type": "RETAIL",
            "amount": "330",
            "starts_at": (now - timedelta(days=14)).isoformat(),
            "ends_at": (now - timedelta(days=1)).isoformat(),
        },
    ).json()
    third = client.post(
        f"/api/v1/admin/products/{pid}/prices",
        json={
            "price_type": "RETAIL",
            "amount": "340",
            "starts_at": now.isoformat(),
        },
    ).json()

    history = client.get(f"/api/v1/admin/products/{pid}/prices/history").json()
    assert len(history) == 3
    amounts = {h["id"]: h["amount"] for h in history}
    assert amounts[first["id"]] == "350.0000"
    assert amounts[second["id"]] == "330.0000"
    assert amounts[third["id"]] == "340.0000"


def test_cannot_edit_started_price_amount(client: TestClient, admin_user: User) -> None:
    _login(client, admin_user)
    product = _seed_product(client, sku="EDT-1")
    pid = product["id"]
    created = client.post(
        f"/api/v1/admin/products/{pid}/prices",
        json={
            "price_type": "RETAIL",
            "amount": "100",
            "starts_at": (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
        },
    ).json()
    response = client.patch(
        f"/api/v1/admin/products/{pid}/prices/{created['id']}",
        json={"amount": "90"},
    )
    assert response.status_code == 409


def test_margin_calculations() -> None:
    result = calculate_margin(Decimal("100"), Decimal("70"))
    assert result.margin_amount == Decimal("30")
    assert result.margin_percentage == Decimal("30")

    negative = calculate_margin(Decimal("50"), Decimal("80"))
    assert negative.margin_amount == Decimal("-30")

    zero_sale = calculate_margin(Decimal("0"), Decimal("10"))
    assert zero_sale.margin_amount == Decimal("-10")
    assert zero_sale.margin_percentage is None

    zero_margin = calculate_margin(Decimal("40"), Decimal("40"))
    assert zero_margin.margin_amount == Decimal("0")
    assert zero_margin.margin_percentage == Decimal("0")


def test_customer_cannot_manage_prices(
    client: TestClient, customer_user: User, admin_user: User
) -> None:
    _login(client, admin_user)
    product = _seed_product(client, sku="AUTH-P")
    client.post("/api/v1/auth/logout")
    _login(client, customer_user)
    assert (
        client.post(
            f"/api/v1/admin/products/{product['id']}/prices",
            json={"amount": "10", "price_type": "RETAIL"},
        ).status_code
        == 403
    )


def test_super_admin_can_create_price(
    client: TestClient, super_admin_user: User
) -> None:
    _login(client, super_admin_user)
    product = _seed_product(client, sku="SA-P")
    response = client.post(
        f"/api/v1/admin/products/{product['id']}/prices",
        json={"amount": "99.99", "price_type": "RETAIL"},
    )
    assert response.status_code == 201


def test_product_price_filters(client: TestClient, admin_user: User) -> None:
    _login(client, admin_user)
    cheap = _seed_product(client, sku="FIL-C")
    mid = _seed_product(client, sku="FIL-M")
    expensive = _seed_product(client, sku="FIL-E")
    none_price = _seed_product(client, sku="FIL-N")

    for product, amount in [
        (cheap, "100"),
        (mid, "500"),
        (expensive, "1500"),
    ]:
        client.post(
            f"/api/v1/admin/products/{product['id']}/prices",
            json={"amount": amount, "price_type": "RETAIL"},
        )

    ranged = client.get("/api/v1/products?min_price=200&max_price=1000").json()
    ids = {item["id"] for item in ranged["items"]}
    assert mid["id"] in ids
    assert cheap["id"] not in ids
    assert expensive["id"] not in ids
    assert none_price["id"] not in ids

    with_brand = client.get(
        f"/api/v1/products?brand={mid['brand']['slug']}&min_price=100"
    ).json()
    assert any(item["id"] == mid["id"] for item in with_brand["items"])


def test_deactivate_price(client: TestClient, admin_user: User) -> None:
    _login(client, admin_user)
    product = _seed_product(client, sku="DEA-1")
    created = client.post(
        f"/api/v1/admin/products/{product['id']}/prices",
        json={"amount": "50", "price_type": "RETAIL"},
    ).json()
    deleted = client.delete(
        f"/api/v1/admin/products/{product['id']}/prices/{created['id']}"
    )
    assert deleted.status_code == 200
    assert deleted.json()["is_active"] is False
    assert client.get(f"/api/v1/products/{product['slug']}").json()["price"] is None
