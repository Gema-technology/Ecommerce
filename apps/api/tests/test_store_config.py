"""Admin store configuration singleton."""

from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient

from app.modules.commerce.shipping import calculate_shipping
from app.modules.orders.schemas import ShippingAddress
from app.modules.payments.providers.bank_transfer import (
    bank_account_configured,
    bank_details_dict,
)
from app.modules.roles.models import User
from app.modules.store_config.schemas import StoreConfigRead
from app.modules.store_config.service import StoreConfigService
from sqlalchemy.orm import Session
from tests.conftest import login_as


def _payload(**overrides: object) -> dict:
    base = {
        "business_name": "GEMA Technology",
        "business_ruc": "1799999999001",
        "business_phone": "0987654321",
        "business_address": "Ibarra",
        "business_email": "info@gema.example",
        "bank_name": "Banco Pichincha",
        "bank_account_type": "Ahorros",
        "bank_account_number": "2209088875",
        "bank_account_holder": "GEMA Technology",
        "bank_account_id": "0401727623",
        "bank_transfer_instructions": "Usar número de orden",
        "shipping_enabled": True,
        "shipping_flat_rate": "7.50",
        "shipping_free_threshold": "150.00",
        "shipping_province_rates": {"Galápagos": "20.00"},
    }
    base.update(overrides)
    return base


def test_customer_cannot_access_store_config(
    client: TestClient, customer_user: User
) -> None:
    login_as(client, customer_user)
    assert client.get("/api/v1/admin/store-config").status_code == 403


def test_get_seeds_from_settings_and_put_persists(
    client: TestClient,
    admin_user: User,
) -> None:
    login_as(client, admin_user)
    first = client.get("/api/v1/admin/store-config")
    assert first.status_code == 200, first.text
    body = first.json()
    assert "business_name" in body
    assert "bank_name" in body
    assert "shipping_enabled" in body

    updated = client.put("/api/v1/admin/store-config", json=_payload())
    assert updated.status_code == 200, updated.text
    data = updated.json()
    assert data["bank_account_number"] == "2209088875"
    assert data["shipping_flat_rate"] in ("7.5000", "7.5", 7.5, "7.50")
    assert "Galápagos" in data["shipping_province_rates"]

    again = client.get("/api/v1/admin/store-config")
    assert again.status_code == 200
    assert again.json()["bank_account_holder"] == "GEMA Technology"


def test_shipping_and_bank_use_db_config(
    client: TestClient,
    admin_user: User,
    db_session: Session,
) -> None:
    login_as(client, admin_user)
    assert client.put("/api/v1/admin/store-config", json=_payload()).status_code == 200

    cfg = StoreConfigService(db_session).get_read()
    assert bank_account_configured(cfg) is True
    bank = bank_details_dict(cfg)
    assert bank["bank_name"] == "Banco Pichincha"
    assert bank["account_number"] == "2209088875"

    amount, method = calculate_shipping(
        subtotal=Decimal("50.00"),
        discount_total=Decimal("0"),
        shipping_address=None,
        store_config=cfg,
    )
    assert method == "standard"
    assert amount == Decimal("7.5000")

    amount_free, method_free = calculate_shipping(
        subtotal=Decimal("160.00"),
        discount_total=Decimal("0"),
        shipping_address=None,
        store_config=cfg,
    )
    assert method_free == "free"
    assert amount_free == Decimal("0.0000")

    amount_prov, method_prov = calculate_shipping(
        subtotal=Decimal("50.00"),
        discount_total=Decimal("0"),
        shipping_address=ShippingAddress(
            recipient_name="Test",
            phone="0987654321",
            address_line="Calle Principal 1",
            city="Puerto Ayora",
            province="Galápagos",
            postal_code="200101",
            country="Ecuador",
        ),
        store_config=cfg,
    )
    assert method_prov == "province_flat"
    assert amount_prov == Decimal("20.0000")


def test_from_settings_fallback_without_db() -> None:
    cfg = StoreConfigRead.from_settings()
    assert cfg.business_name
    assert isinstance(cfg.shipping_enabled, bool)
