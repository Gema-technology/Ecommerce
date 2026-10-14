from decimal import Decimal

from fastapi.testclient import TestClient

from app.modules.quotes.pricing import compute_quote_totals, compute_tier_prices, cost_real, price_from_margin
from app.modules.roles.models import User


def _login(client: TestClient, user: User) -> None:
    client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "secure-password"},
    )


def test_pricing_formulas() -> None:
    real = cost_real(Decimal("100"), Decimal("10"))
    assert real == Decimal("110.0000")
    prices = compute_tier_prices(
        Decimal("100"),
        Decimal("10"),
        min_margin=Decimal("0.12"),
        rec_margin=Decimal("0.20"),
        high_margin=Decimal("0.25"),
    )
    assert prices["price_min"] == price_from_margin(real, Decimal("0.12"))
    assert prices["price_rec"] == price_from_margin(real, Decimal("0.20"))
    assert prices["price_high"] == price_from_margin(real, Decimal("0.25"))


def test_quote_totals() -> None:
    subtotal, iva, total = compute_quote_totals(
        [(2, Decimal("125.00")), (1, Decimal("50.00"))],
        Decimal("0.15"),
    )
    assert subtotal == Decimal("300.0000")
    assert iva == Decimal("45.0000")
    assert total == Decimal("345.0000")


def test_pricing_config_defaults(client: TestClient, admin_user: User) -> None:
    _login(client, admin_user)
    response = client.get("/api/v1/admin/pricing-config")
    assert response.status_code == 200
    data = response.json()
    assert Decimal(data["min_margin"]) == Decimal("0.12")
    assert Decimal(data["rec_margin"]) == Decimal("0.20")
    assert Decimal(data["high_margin"]) == Decimal("0.25")
    assert Decimal(data["default_iva"]) == Decimal("0.15")


def test_catalog_product_computed_prices(client: TestClient, admin_user: User) -> None:
    _login(client, admin_user)
    client.put(
        "/api/v1/admin/pricing-config",
        json={"min_margin": "0.10", "rec_margin": "0.20", "high_margin": "0.30"},
    )
    created = client.post(
        "/api/v1/admin/catalog/products",
        json={"name": "Laptop Pro", "category": "Laptops", "cost_price": "800", "other_costs": "50"},
    )
    assert created.status_code == 201
    data = created.json()
    assert data["cost_real"] == "850.0000"
    assert data["price_min"] == "944.4444"
    assert data["price_rec"] == "1062.5000"
    assert data["price_high"] == "1214.2857"


def test_create_quote_recalculates_totals(client: TestClient, admin_user: User) -> None:
    _login(client, admin_user)
    product = client.post(
        "/api/v1/admin/catalog/products",
        json={"name": "Monitor", "cost_price": "200", "other_costs": "0"},
    ).json()
    response = client.post(
        "/api/v1/admin/quotes",
        json={
            "client_name": "Juan Pérez",
            "client_email": "juan@example.com",
            "iva_pct": "0.15",
            "items": [
                {"product_id": product["id"], "tier": "rec", "quantity": 2},
                {"product_id": product["id"], "tier": "min", "quantity": 1},
            ],
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["number"] == "PRO-0001"
    assert Decimal(data["subtotal"]) > 0
    assert Decimal(data["total"]) == Decimal(data["subtotal"]) + Decimal(data["iva_amount"])
    assert len(data["items"]) == 2


def test_quote_number_is_sequential(client: TestClient, admin_user: User) -> None:
    _login(client, admin_user)
    product = client.post(
        "/api/v1/admin/catalog/products",
        json={"name": "Cable", "cost_price": "5"},
    ).json()
    payload = {
        "client_name": "Cliente",
        "items": [{"product_id": product["id"], "tier": "rec", "quantity": 1}],
    }
    n1 = client.post("/api/v1/admin/quotes", json=payload).json()["number"]
    n2 = client.post("/api/v1/admin/quotes", json=payload).json()["number"]
    assert n1 == "PRO-0001"
    assert n2 == "PRO-0002"


def test_product_price_change_does_not_alter_quote(client: TestClient, admin_user: User) -> None:
    _login(client, admin_user)
    product = client.post(
        "/api/v1/admin/catalog/products",
        json={"name": "Teclado", "cost_price": "50"},
    ).json()
    quote = client.post(
        "/api/v1/admin/quotes",
        json={
            "client_name": "Ana",
            "items": [{"product_id": product["id"], "tier": "rec", "quantity": 1}],
        },
    ).json()
    original_unit = quote["items"][0]["unit_price"]
    client.put(
        f"/api/v1/admin/catalog/products/{product['id']}",
        json={"cost_price": "500"},
    )
    fetched = client.get(f"/api/v1/admin/quotes/{quote['id']}").json()
    assert fetched["items"][0]["unit_price"] == original_unit
    assert fetched["items"][0]["product_name"] == "Teclado"


def test_customer_cannot_access_quotes(client: TestClient, customer_user: User) -> None:
    _login(client, customer_user)
    assert client.get("/api/v1/admin/quotes").status_code == 403


def test_quote_pdf_endpoint(client: TestClient, admin_user: User) -> None:
    _login(client, admin_user)
    product = client.post(
        "/api/v1/admin/catalog/products",
        json={"name": "Mouse", "cost_price": "20"},
    ).json()
    quote = client.post(
        "/api/v1/admin/quotes",
        json={
            "client_name": "PDF Client",
            "items": [{"product_id": product["id"], "tier": "rec", "quantity": 1}],
        },
    ).json()
    response = client.get(f"/api/v1/admin/quotes/{quote['id']}/pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content[:4] == b"%PDF"


def test_quote_pdf_html_has_header_logo_and_footer(
    client: TestClient, admin_user: User, db_session
) -> None:
    from uuid import UUID

    from app.modules.quotes.models import Quote
    from app.modules.quotes.pdf import render_quote_html

    _login(client, admin_user)
    product = client.post(
        "/api/v1/admin/catalog/products",
        json={"name": "Mouse Pro", "cost_price": "20"},
    ).json()
    created = client.post(
        "/api/v1/admin/quotes",
        json={
            "client_name": "HTML Client",
            "items": [{"product_id": product["id"], "tier": "rec", "quantity": 1}],
        },
    ).json()
    quote = db_session.get(Quote, UUID(created["id"]))
    assert quote is not None
    html = render_quote_html(quote)
    assert 'class="document-header' in html
    assert 'class="logo"' in html
    assert 'class="client-name"' in html
    assert 'class="client-grid"' in html
    assert "data:image/" in html
    assert "document-footer" in html
    assert "PROFORMA" in html.upper() or "Proforma" in html


def test_quote_pdf_reportlab_fallback(
    monkeypatch, client: TestClient, admin_user: User, db_session
):
    from uuid import UUID

    from app.modules.quotes import pdf as pdf_mod
    from app.modules.quotes.models import Quote

    monkeypatch.setattr(
        pdf_mod,
        "_generate_pdf_weasyprint",
        lambda _html: (_ for _ in ()).throw(RuntimeError("no weasy")),
    )
    _login(client, admin_user)
    product = client.post(
        "/api/v1/admin/catalog/products",
        json={"name": "Teclado Pro", "cost_price": "30"},
    ).json()
    created = client.post(
        "/api/v1/admin/quotes",
        json={
            "client_name": "RL Client",
            "items": [{"product_id": product["id"], "tier": "rec", "quantity": 2}],
        },
    ).json()
    quote = db_session.get(Quote, UUID(created["id"]))
    assert quote is not None
    data = pdf_mod.generate_quote_pdf(quote)
    assert data[:4] == b"%PDF"
