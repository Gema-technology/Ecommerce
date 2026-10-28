"""Sprint A3 — opción A: checkout IVA alineado con factura SRI (sin rewrite histórico)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core import config as config_mod
from app.core.config import Settings
from app.modules.catalog.models import Brand, Category, Product
from app.modules.commerce.tax import calculate_tax
from app.modules.commerce.totals import compute_order_totals
from app.modules.orders.models import Order, OrderItem, OrderStatus
from app.modules.orders.schemas import ShippingAddress
from app.modules.pricing.models import PriceCurrency
from app.modules.roles.schemas import ROLE_CUSTOMER
from app.modules.sri.schemas import EmitFiscalDocumentRequest, SriConfigUpdate
from app.modules.sri.service import SriService
from app.modules.store_config.models import StoreConfig
from tests.conftest import create_user_with_role
from tests.test_sri import _FakeSoap, _make_p12


def _addr() -> ShippingAddress:
    return ShippingAddress(
        recipient_name="Cliente",
        phone="0991234567",
        address_line="Calle 1",
        city="Ibarra",
        province="Imbabura",
        country="Ecuador",
    )


def _seed_paid_order(
    db_session: Session,
    *,
    subtotal: Decimal,
    tax_total: Decimal,
    shipping_total: Decimal,
    total: Decimal,
) -> Order:
    if db_session.get(StoreConfig, 1) is None:
        db_session.add(
            StoreConfig(
                id=1,
                business_name="GEMA Demo",
                business_ruc="1799999999001",
                business_email="demo@example.com",
            )
        )
    user = create_user_with_role(
        db_session,
        email=f"tax-{uuid4().hex[:8]}@example.com",
        password="secure-password",
        role_name=ROLE_CUSTOMER,
    )
    brand = Brand(name="B", slug=f"b-{uuid4().hex[:8]}", is_active=True)
    category = Category(name="C", slug=f"c-{uuid4().hex[:8]}", is_active=True)
    db_session.add_all([brand, category])
    db_session.flush()
    product = Product(
        name="Laptop",
        slug=f"p-{uuid4().hex[:8]}",
        sku=f"SKU-{uuid4().hex[:6].upper()}",
        brand_id=brand.id,
        category_id=category.id,
        is_active=True,
    )
    db_session.add(product)
    db_session.flush()
    order = Order(
        user_id=user.id,
        order_number=f"GEMA-TAX-{uuid4().hex[:6].upper()}",
        status=OrderStatus.PAID.value,
        currency=PriceCurrency.USD.value,
        subtotal=subtotal,
        tax_total=tax_total,
        shipping_total=shipping_total,
        discount_total=Decimal("0"),
        total=total,
        customer_email=user.email,
        customer_name="Cliente",
        buyer_id_type="CEDULA",
        buyer_id_number="1710034065",
    )
    db_session.add(order)
    db_session.flush()
    db_session.add(
        OrderItem(
            order_id=order.id,
            product_id=product.id,
            product_name_snapshot=product.name,
            sku_snapshot=product.sku,
            unit_price=subtotal,
            quantity=1,
            line_total=subtotal,
            line_discount=Decimal("0"),
        )
    )
    db_session.commit()
    return order


def _prepare_sri(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> SriService:
    cert_path = tmp_path / "certs" / "emitter.p12"
    _make_p12(cert_path, "secret")
    monkeypatch.setattr(config_mod.settings, "sri_cert_dir", str(tmp_path / "certs"))
    monkeypatch.setattr(config_mod.settings, "sri_pdf_dir", str(tmp_path / "pdfs"))
    monkeypatch.setattr(config_mod.settings, "sri_cert_password", "secret")

    service = SriService(db_session, soap_client=_FakeSoap())
    service.update_config(
        SriConfigUpdate(
            tax_regime="RIMPE_EMPRENDEDOR",
            ambiente="1",
            establecimiento="001",
            punto_emision="001",
            dir_matriz="Matriz",
            dir_establecimiento="Estab",
            obligado_contabilidad="NO",
            contribuyente_especial="",
        )
    )
    cfg = service.config_repo.get_or_create()
    cfg.cert_filename = "emitter.p12"
    cfg.cert_stored = True
    db_session.commit()
    return service


def test_checkout_tax_disabled_keeps_order_total_without_iva(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config_mod.settings, "commerce_tax_enabled", False)
    monkeypatch.setattr(config_mod.settings, "commerce_tax_rate", Decimal("0.15"))
    monkeypatch.setattr(config_mod.settings, "shipping_enabled", False)

    assert calculate_tax(taxable_subtotal=Decimal("999.0000")) == Decimal("0.0000")
    totals = compute_order_totals(
        subtotal=Decimal("999.0000"),
        discount_total=Decimal("0"),
        shipping_address=_addr(),
        store_config=None,
    )
    assert totals.tax_total == Decimal("0.0000")
    assert totals.total == Decimal("999.0000")


def test_checkout_tax_enabled_adds_flat_iva(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config_mod.settings, "commerce_tax_enabled", True)
    monkeypatch.setattr(config_mod.settings, "commerce_tax_rate", Decimal("0.15"))
    monkeypatch.setattr(config_mod.settings, "shipping_enabled", False)

    tax = calculate_tax(taxable_subtotal=Decimal("999.0000"))
    assert tax == Decimal("149.8500")
    totals = compute_order_totals(
        subtotal=Decimal("999.0000"),
        discount_total=Decimal("0"),
        shipping_address=_addr(),
        store_config=None,
    )
    assert totals.tax_total == Decimal("149.8500")
    assert totals.total == Decimal("1148.8500")


def test_rimpe_negocio_popular_does_not_charge_iva(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config_mod.settings, "commerce_tax_enabled", True)
    monkeypatch.setattr(config_mod.settings, "commerce_tax_rate", Decimal("0.15"))
    monkeypatch.setattr(config_mod.settings, "shipping_enabled", False)

    tax = calculate_tax(
        taxable_subtotal=Decimal("100.0000"),
        tax_regime="RIMPE_NEGOCIO_POPULAR",
    )
    assert tax == Decimal("0.0000")
    totals = compute_order_totals(
        subtotal=Decimal("100.0000"),
        discount_total=Decimal("0"),
        shipping_address=_addr(),
        store_config=None,
        tax_regime="RIMPE_NEGOCIO_POPULAR",
    )
    assert totals.tax_total == Decimal("0.0000")
    assert totals.total == Decimal("100.0000")


def test_rimpe_negocio_popular_factura_has_zero_iva(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config_mod.settings, "commerce_tax_enabled", True)
    monkeypatch.setattr(config_mod.settings, "commerce_tax_rate", Decimal("0.15"))
    monkeypatch.setattr(config_mod.settings, "app_env", "staging")

    order = _seed_paid_order(
        db_session,
        subtotal=Decimal("40.0000"),
        tax_total=Decimal("6.0000"),
        shipping_total=Decimal("0"),
        total=Decimal("46.0000"),
    )
    service = _prepare_sri(db_session, tmp_path, monkeypatch)
    service.update_config(
        SriConfigUpdate(
            tax_regime="RIMPE_NEGOCIO_POPULAR",
            ambiente="1",
            establecimiento="001",
            punto_emision="001",
            dir_matriz="Matriz",
            dir_establecimiento="Estab",
            obligado_contabilidad="NO",
            contribuyente_especial="",
        )
    )
    doc = service.emit_for_order(
        order.id,
        EmitFiscalDocumentRequest(
            doc_type="FACTURA",
            send_to_sri=False,
            buyer_address="Av. Amazonas, Quito, Pichincha",
        ),
    )
    assert Decimal(doc.tax_rate) == Decimal("0")
    assert Decimal(doc.tax_total) == Decimal("0")
    assert Decimal(doc.total) == Decimal("40.0000")


def test_option_a_checkout_total_matches_factura_total(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Opción A: order $1148.85 (999 + IVA 149.85) → factura total idéntico."""
    monkeypatch.setattr(config_mod.settings, "commerce_tax_enabled", True)
    monkeypatch.setattr(config_mod.settings, "commerce_tax_rate", Decimal("0.15"))
    monkeypatch.setattr(config_mod.settings, "app_env", "development")

    order = _seed_paid_order(
        db_session,
        subtotal=Decimal("999.0000"),
        tax_total=Decimal("149.8500"),
        shipping_total=Decimal("0"),
        total=Decimal("1148.8500"),
    )
    service = _prepare_sri(db_session, tmp_path, monkeypatch)
    doc = service.emit_for_order(
        order.id,
        EmitFiscalDocumentRequest(
            doc_type="FACTURA",
            send_to_sri=False,
            buyer_address="Av. Amazonas, Quito, Pichincha",
        ),
    )
    assert doc.tax_total == order.tax_total == Decimal("149.8500")
    assert doc.total == order.total == Decimal("1148.8500")
    assert doc.subtotal == Decimal("999.0000")


def test_emit_factura_blocked_in_staging_when_tax_disabled(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config_mod.settings, "commerce_tax_enabled", False)
    monkeypatch.setattr(config_mod.settings, "app_env", "staging")

    order = _seed_paid_order(
        db_session,
        subtotal=Decimal("999.0000"),
        tax_total=Decimal("0"),
        shipping_total=Decimal("0"),
        total=Decimal("999.0000"),
    )
    service = _prepare_sri(db_session, tmp_path, monkeypatch)
    with pytest.raises(HTTPException) as exc:
        service.emit_for_order(
            order.id,
            EmitFiscalDocumentRequest(
            doc_type="FACTURA",
            send_to_sri=False,
            buyer_address="Av. Amazonas, Quito, Pichincha",
        ),
        )
    assert exc.value.status_code == 400
    assert "COMMERCE_TAX_ENABLED" in str(exc.value.detail)


def test_emit_factura_matches_zero_tax_order_in_development(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dev/lab: tax off → factura follows order (no silent $999 → $1148.85 inflate)."""
    monkeypatch.setattr(config_mod.settings, "commerce_tax_enabled", False)
    monkeypatch.setattr(config_mod.settings, "commerce_tax_rate", Decimal("0.15"))
    monkeypatch.setattr(config_mod.settings, "app_env", "development")

    order = _seed_paid_order(
        db_session,
        subtotal=Decimal("999.0000"),
        tax_total=Decimal("0"),
        shipping_total=Decimal("0"),
        total=Decimal("999.0000"),
    )
    service = _prepare_sri(db_session, tmp_path, monkeypatch)
    doc = service.emit_for_order(
        order.id,
        EmitFiscalDocumentRequest(
            doc_type="FACTURA",
            send_to_sri=False,
            buyer_address="Av. Amazonas, Quito, Pichincha",
        ),
    )
    assert doc.tax_total == Decimal("0")
    assert doc.total == order.total == Decimal("999.0000")


def test_production_rejects_localhost_cors() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            postgres_password="prod-db-secret-not-default",
            internal_job_secret="prod-internal-secret-not-default",
            payment_webhook_secret="prod-webhook-secret-not-default",
            payment_default_provider="payphone",
            payphone_token="prod-payphone-token",
            payphone_store_id="prod-payphone-store",
            payphone_webhook_secret="prod-payphone-webhook-secret",
            session_backend="redis",
            auth_rate_limit_backend="redis",
            allow_manual_payment_confirm=False,
            public_app_url="https://shop.example.com",
            cors_origins="https://shop.example.com,http://localhost:3000",
        )
