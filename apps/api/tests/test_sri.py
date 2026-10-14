"""SRI access key, XML, nota de venta, and factura (mocked SOAP) tests."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import BestAvailableEncryption, pkcs12
from cryptography.x509.oid import NameOID
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.catalog.models import Brand, Category, Product
from app.modules.orders.models import Order, OrderItem, OrderStatus
from app.modules.pricing.models import PriceCurrency
from app.modules.roles.schemas import ROLE_ADMIN, ROLE_CUSTOMER
from app.modules.sri.access_key import (
    build_access_key,
    format_document_number,
    modulo11_check_digit,
)
from app.modules.sri.client import AutorizacionResult, RecepcionResult, SriSoapClient
from app.modules.sri.models import FiscalDocStatus, FiscalDocType
from app.modules.sri.schemas import EmitFiscalDocumentRequest, SriConfigUpdate
from app.modules.sri.service import SriService
from app.modules.sri.signing import sign_comprobante_xml, verify_cert_loadable
from app.modules.sri.xml_factura import FacturaLine, FacturaPayload, build_factura_xml
from app.modules.store_config.models import StoreConfig
from tests.conftest import create_user_with_role, login_as


def test_modulo11_and_access_key_length():
    body = "121020260117999999990011001001000000001123456781"
    digit = modulo11_check_digit(body)
    assert digit.isdigit() and len(digit) == 1
    key = build_access_key(
        emission_date=date(2026, 10, 12),
        doc_type_code="01",
        ruc="1799999999001",
        ambiente="1",
        establecimiento="001",
        punto_emision="001",
        sequential=1,
        numeric_code="12345678",
    )
    assert len(key) == 49
    assert key.isdigit()
    assert key.endswith(digit)
    assert format_document_number("1", "2", 3) == "001-002-000000003"


def test_ecuador_emission_date_uses_guayaquil_not_utc_date():
    """Near UTC midnight, Ecuador (UTC-5) can be the previous civil day — SRI uses EC date."""
    from app.modules.sri.timeutil import ecuador_emission_date

    # 2026-10-13 03:30 UTC == 2026-10-12 22:30 America/Guayaquil
    utc_morning = datetime(2026, 10, 13, 3, 30, tzinfo=UTC)
    assert ecuador_emission_date(reference=utc_morning) == date(2026, 10, 12)

    # Midday Ecuador
    local_midday = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)
    assert ecuador_emission_date(reference=local_midday) == date(2026, 10, 13)


def test_access_key_date_segment_matches_ecuador_emission():
    from app.modules.sri.timeutil import ecuador_emission_date

    ref = datetime(2026, 10, 13, 3, 30, tzinfo=UTC)
    emission = ecuador_emission_date(reference=ref)
    key = build_access_key(
        emission_date=emission,
        doc_type_code="01",
        ruc="1799999999001",
        ambiente="1",
        establecimiento="001",
        punto_emision="001",
        sequential=1,
        numeric_code="12345678",
    )
    assert key.startswith("12102026")  # 12/10/2026 Ecuador, not 13


def test_build_factura_xml_contains_clave():
    payload = FacturaPayload(
        ambiente="1",
        tipo_emision="1",
        razon_social="GEMA Technology",
        nombre_comercial="GEMA",
        ruc="1799999999001",
        clave_acceso="1" * 49,
        codigo_establecimiento="001",
        codigo_punto_emision="001",
        secuencial="000000001",
        dir_matriz="Quito",
        dir_establecimiento="Quito",
        obligado_contabilidad="NO",
        contribuyente_especial=None,
        fecha_emision=date(2026, 10, 12),
        buyer_id_type="CEDULA",
        buyer_id_number="1710034065",
        buyer_name="Cliente Demo",
        buyer_address="Ibarra",
        total_sin_impuestos=Decimal("100.00"),
        total_descuento=Decimal("0"),
        propina=Decimal("0"),
        importe_total=Decimal("115.00"),
        moneda="DOLAR",
        lines=[
            FacturaLine(
                codigo="SKU1",
                descripcion="Producto",
                cantidad=Decimal("1"),
                precio_unitario=Decimal("100"),
                descuento=Decimal("0"),
                precio_total_sin_impuesto=Decimal("100"),
                iva_rate=Decimal("0.15"),
                iva_valor=Decimal("15"),
            )
        ],
        payments=[("01", Decimal("115.00"))],
        info_adicional=[("Email", "a@b.com")],
        rimpe_legend="CONTRIBUYENTE RÉGIMEN RIMPE — EMPRENDEDOR",
    )
    xml = build_factura_xml(payload)
    assert "<factura" in xml
    assert "<claveAcceso>" in xml
    assert "codigoPorcentaje>4<" in xml or ">4</codigoPorcentaje>" in xml


def _make_p12(path: Path, password: str = "secret") -> None:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "EC"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "GEMA Test"),
            x509.NameAttribute(NameOID.COMMON_NAME, "GEMA Signer"),
        ]
    )
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=365))
        .sign(key, hashes.SHA256())
    )
    p12_bytes = pkcs12.serialize_key_and_certificates(
        name=b"gema",
        key=key,
        cert=cert,
        cas=None,
        encryption_algorithm=BestAvailableEncryption(password.encode("utf-8")),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(p12_bytes)


def test_sign_xml_with_p12(tmp_path: Path):
    cert_path = tmp_path / "test.p12"
    _make_p12(cert_path, "secret")
    info = verify_cert_loadable(cert_path, "secret")
    assert "GEMA" in info["subject"]
    xml = (
        "<?xml version='1.0' encoding='utf-8'?>"
        '<factura id="comprobante" version="1.1.0">'
        "<infoTributaria><ruc>1799999999001</ruc></infoTributaria>"
        "</factura>"
    )
    signed = sign_comprobante_xml(xml, cert_path, "secret")
    assert "Signature" in signed
    assert "SignatureValue" in signed


class _FakeSoap(SriSoapClient):
    def __init__(self) -> None:
        super().__init__(ambiente="1")

    def enviar_comprobante(self, signed_xml: str) -> RecepcionResult:
        assert signed_xml
        return RecepcionResult(estado="RECIBIDA", messages=[])

    def autorizar_comprobante(self, access_key: str) -> AutorizacionResult:
        return AutorizacionResult(
            estado="AUTORIZADO",
            numero_autorizacion=access_key,
            fecha_autorizacion="2026-10-12T12:00:00",
            comprobante_xml="<autorizado/>",
            messages=[],
        )


def _seed_paid_order(db: Session) -> Order:
    user = create_user_with_role(
        db,
        email=f"buyer-{uuid4().hex[:8]}@example.com",
        password="secure-password",
        role_name=ROLE_CUSTOMER,
    )
    brand = Brand(name=f"Brand-{uuid4().hex[:6]}", slug=f"brand-{uuid4().hex[:8]}", is_active=True)
    category = Category(
        name=f"Cat-{uuid4().hex[:6]}",
        slug=f"cat-{uuid4().hex[:8]}",
        is_active=True,
    )
    db.add_all([brand, category])
    db.flush()
    product = Product(
        name="Router Demo",
        slug=f"router-{uuid4().hex[:8]}",
        sku=f"SKU-{uuid4().hex[:6].upper()}",
        description="Demo",
        brand_id=brand.id,
        category_id=category.id,
        is_active=True,
    )
    db.add(product)
    db.flush()
    order = Order(
        user_id=user.id,
        order_number=f"GEMA-TEST-{uuid4().hex[:6].upper()}",
        status=OrderStatus.PAID.value,
        currency=PriceCurrency.USD.value,
        subtotal=Decimal("100.0000"),
        tax_total=Decimal("0"),
        shipping_total=Decimal("5.0000"),
        discount_total=Decimal("0"),
        total=Decimal("105.0000"),
        customer_email=user.email,
        customer_name="Cliente Demo",
        customer_phone="0999999999",
        buyer_id_type="CEDULA",
        buyer_id_number="1710034065",
        shipping_address={
            "recipient_name": "Cliente Demo",
            "phone": "0999999999",
            "address_line": "Calle 1",
            "city": "Ibarra",
            "province": "Imbabura",
            "country": "Ecuador",
        },
    )
    db.add(order)
    db.flush()
    db.add(
        OrderItem(
            order_id=order.id,
            product_id=product.id,
            product_name_snapshot=product.name,
            sku_snapshot=product.sku,
            unit_price=Decimal("100.0000"),
            quantity=1,
            line_total=Decimal("100.0000"),
            line_discount=Decimal("0"),
        )
    )
    store = db.get(StoreConfig, 1)
    if store is None:
        store = StoreConfig(id=1)
        db.add(store)
    store.business_name = "GEMA Technology"
    store.business_ruc = "1799999999001"
    store.business_address = "Ibarra"
    db.commit()
    db.refresh(order)
    return order


def test_sri_config_admin_api(client: TestClient, db_session: Session):
    admin = create_user_with_role(
        db_session,
        email="sri-admin@example.com",
        password="secure-password",
        role_name=ROLE_ADMIN,
    )
    login_as(client, admin)
    res = client.get("/api/v1/admin/sri/config")
    assert res.status_code == 200
    body = res.json()
    assert body["ambiente"] == "1"
    assert body["establecimiento"] == "001"

    upd = client.put(
        "/api/v1/admin/sri/config",
        json={
            "tax_regime": "RIMPE_NEGOCIO_POPULAR",
            "ambiente": "1",
            "establecimiento": "002",
            "punto_emision": "003",
            "dir_matriz": "Matriz Av. 1",
            "dir_establecimiento": "Sucursal 2",
            "obligado_contabilidad": "NO",
            "contribuyente_especial": "",
        },
    )
    assert upd.status_code == 200
    assert upd.json()["establecimiento"] == "002"
    assert upd.json()["tax_regime"] == "RIMPE_NEGOCIO_POPULAR"


def test_emit_nota_venta(
    client: TestClient, db_session: Session, tmp_path: Path, monkeypatch
):
    monkeypatch.setattr(settings, "sri_pdf_dir", str(tmp_path / "pdfs"))
    monkeypatch.setattr(settings, "sri_cert_dir", str(tmp_path / "certs"))
    admin = create_user_with_role(
        db_session,
        email="nota-admin@example.com",
        password="secure-password",
        role_name=ROLE_ADMIN,
    )
    order = _seed_paid_order(db_session)
    login_as(client, admin)

    client.put(
        "/api/v1/admin/sri/config",
        json={
            "tax_regime": "RIMPE_NEGOCIO_POPULAR",
            "ambiente": "1",
            "establecimiento": "001",
            "punto_emision": "001",
            "dir_matriz": "Matriz",
            "dir_establecimiento": "Estab",
            "obligado_contabilidad": "NO",
            "contribuyente_especial": "",
        },
    )

    res = client.post(
        f"/api/v1/admin/orders/{order.id}/fiscal-documents",
        json={"doc_type": "NOTA_VENTA"},
    )
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["doc_type"] == FiscalDocType.NOTA_VENTA.value
    assert data["status"] == FiscalDocStatus.ISSUED.value
    assert data["document_number"] == "001-001-000000001"
    assert data["has_pdf"] is True
    assert Decimal(data["tax_total"]) == Decimal("0")

    pdf = client.get(f"/api/v1/admin/fiscal-documents/{data['id']}/pdf")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"].startswith("application/pdf")
    assert pdf.content[:4] == b"%PDF"

    # Second download regenerates from the current template (still valid PDF).
    pdf2 = client.get(f"/api/v1/admin/fiscal-documents/{data['id']}/pdf")
    assert pdf2.status_code == 200
    assert pdf2.content[:4] == b"%PDF"


def test_fiscal_pdf_html_has_header_and_footer_structure():
    from app.modules.sri.models import FiscalDocument
    from app.modules.sri.pdf import render_nota_venta_html, render_ride_html
    from app.modules.store_config.schemas import StoreConfigRead

    store = StoreConfigRead(
        business_name="GEMA Technology",
        business_ruc="1799999999001",
        business_phone="062600000",
        business_address="Ibarra, Ecuador",
        business_email="ventas@gema.ec",
        bank_name="",
        bank_account_type="Ahorros",
        bank_account_number="",
        bank_account_holder="",
        bank_account_id="",
        bank_transfer_instructions="",
        shipping_enabled=True,
        shipping_flat_rate=Decimal("5"),
        shipping_free_threshold=None,
        shipping_province_rates={},
        updated_at=None,
    )
    doc = FiscalDocument(
        order_id=uuid4(),
        doc_type=FiscalDocType.NOTA_VENTA.value,
        status=FiscalDocStatus.ISSUED.value,
        establishment="001",
        emission_point="001",
        sequential=2,
        document_number="001-001-000000002",
        buyer_id_type="CONSUMIDOR_FINAL",
        buyer_id_number="9999999999999",
        buyer_name="Cliente Demo",
        buyer_email="cliente@example.com",
        buyer_address="Calle 1",
        currency="USD",
        subtotal=Decimal("3.99"),
        tax_total=Decimal("0"),
        discount_total=Decimal("0"),
        shipping_total=Decimal("5"),
        total=Decimal("8.99"),
        tax_rate=Decimal("0"),
        line_items=[
            {
                "quantity": 1,
                "description": "Manos Libres",
                "sku": "AKG",
                "unit_price": "3.99",
                "discount": "0",
                "line_total": "3.99",
            }
        ],
        created_at=datetime(2026, 10, 12, 18, 34, 29, tzinfo=UTC),
    )

    html = render_nota_venta_html(
        doc, store_config=store, regime="RIMPE_NEGOCIO_POPULAR"
    )
    assert 'class="document-header"' in html
    assert 'class="document-footer"' in html
    assert 'class="logo"' in html
    assert 'class="client-name"' in html
    assert 'class="client-grid"' in html
    assert "data:image/" in html
    assert "NOTA DE VENTA" in html
    assert "001-001-000000002" in html
    assert "Consumidor final" in html
    assert "GEMA Technology" in html
    assert "no requiere autorización electrónica" in html

    doc.doc_type = FiscalDocType.FACTURA.value
    ride = render_ride_html(doc, store_config=store, regime="GENERAL")
    assert 'class="document-header"' in ride
    assert "FACTURA ELECTRÓNICA" in ride
    assert "RIDE" in ride


def test_fiscal_pdf_reportlab_fallback(monkeypatch):
    from app.modules.sri import pdf as pdf_mod
    from app.modules.sri.models import FiscalDocument
    from app.modules.store_config.schemas import StoreConfigRead

    monkeypatch.setattr(
        pdf_mod,
        "_generate_pdf_weasyprint",
        lambda _html: (_ for _ in ()).throw(RuntimeError("no weasy")),
    )
    store = StoreConfigRead(
        business_name="GEMA Technology",
        business_ruc="1799999999001",
        business_phone="062600000",
        business_address="Ibarra",
        business_email="ventas@gema.ec",
        bank_name="",
        bank_account_type="Ahorros",
        bank_account_number="",
        bank_account_holder="",
        bank_account_id="",
        bank_transfer_instructions="",
        shipping_enabled=True,
        shipping_flat_rate=Decimal("5"),
        shipping_free_threshold=None,
        shipping_province_rates={},
        updated_at=None,
    )
    doc = FiscalDocument(
        order_id=uuid4(),
        doc_type=FiscalDocType.NOTA_VENTA.value,
        status=FiscalDocStatus.ISSUED.value,
        establishment="001",
        emission_point="001",
        sequential=1,
        document_number="001-001-000000001",
        buyer_id_type="CEDULA",
        buyer_id_number="1710034065",
        buyer_name="Cliente Demo",
        currency="USD",
        subtotal=Decimal("100"),
        tax_total=Decimal("0"),
        discount_total=Decimal("0"),
        shipping_total=Decimal("5"),
        total=Decimal("105"),
        tax_rate=Decimal("0"),
        line_items=[
            {
                "quantity": 1,
                "description": "Router Demo",
                "sku": "SKU-1",
                "unit_price": "100",
                "discount": "0",
                "line_total": "100",
            }
        ],
        created_at=datetime(2026, 10, 12, 12, 0, 0, tzinfo=UTC),
    )
    data = pdf_mod.generate_fiscal_pdf(
        doc, store_config=store, regime="RIMPE_EMPRENDEDOR"
    )
    assert data[:4] == b"%PDF"


def test_emit_factura_with_mocked_sri(
    client: TestClient, db_session: Session, tmp_path: Path, monkeypatch
):
    cert_path = tmp_path / "certs" / "emitter.p12"
    _make_p12(cert_path, "secret")
    monkeypatch.setattr(settings, "sri_cert_dir", str(tmp_path / "certs"))
    monkeypatch.setattr(settings, "sri_pdf_dir", str(tmp_path / "pdfs"))
    monkeypatch.setattr(settings, "sri_cert_password", "secret")

    _seed_paid_order(db_session)  # ensure store config
    order = _seed_paid_order(db_session)

    service = SriService(db_session, soap_client=_FakeSoap())
    service.update_config(
        SriConfigUpdate(
            tax_regime="RIMPE_EMPRENDEDOR",
            ambiente="1",
            establecimiento="001",
            punto_emision="001",
            dir_matriz="Matriz Quito",
            dir_establecimiento="Estab Quito",
            obligado_contabilidad="NO",
            contribuyente_especial="",
        )
    )
    cfg = service.config_repo.get_or_create()
    cfg.cert_filename = "emitter.p12"
    cfg.cert_stored = True
    db_session.commit()

    doc = service.emit_for_order(
        order.id,
        EmitFiscalDocumentRequest(doc_type="FACTURA", send_to_sri=True),
    )
    assert doc.doc_type == "FACTURA"
    assert doc.status == FiscalDocStatus.AUTHORIZED.value
    assert doc.access_key and len(doc.access_key) == 49
    assert doc.authorization_number
    assert doc.has_xml is True


def test_emit_factura_utc_edge_uses_ecuador_civil_date(
    db_session: Session, tmp_path: Path, monkeypatch
):
    """Regression for SRI error 65: UTC midnight edge must not stamp a future EC date."""
    from app.modules.sri import service as sri_service_mod

    cert_path = tmp_path / "certs" / "emitter.p12"
    _make_p12(cert_path, "secret")
    monkeypatch.setattr(settings, "sri_cert_dir", str(tmp_path / "certs"))
    monkeypatch.setattr(settings, "sri_pdf_dir", str(tmp_path / "pdfs"))
    monkeypatch.setattr(settings, "sri_cert_password", "secret")
    # Same instant as rejected live doc GEMA-20261013-000004 (~04:52 UTC).
    monkeypatch.setattr(
        sri_service_mod,
        "ecuador_emission_date",
        lambda reference=None: date(2026, 10, 12),
    )

    order = _seed_paid_order(db_session)
    service = SriService(db_session, soap_client=_FakeSoap())
    service.update_config(
        SriConfigUpdate(
            tax_regime="RIMPE_EMPRENDEDOR",
            ambiente="1",
            establecimiento="001",
            punto_emision="001",
            dir_matriz="Matriz Quito",
            dir_establecimiento="Estab Quito",
            obligado_contabilidad="NO",
            contribuyente_especial="",
        )
    )
    cfg = service.config_repo.get_or_create()
    cfg.cert_filename = "emitter.p12"
    cfg.cert_stored = True
    db_session.commit()

    doc = service.emit_for_order(
        order.id,
        EmitFiscalDocumentRequest(doc_type="FACTURA", send_to_sri=False),
    )
    assert doc.access_key.startswith("12102026")
    from app.modules.sri.models import FiscalDocument

    stored = db_session.get(FiscalDocument, doc.id)
    assert stored is not None
    assert "<fechaEmision>12/10/2026</fechaEmision>" in (stored.xml_unsigned or "")


def test_retry_authorization_blocks_sri_error_65_without_rewriting_xml(
    db_session: Session, tmp_path: Path, monkeypatch
):
    from fastapi import HTTPException

    from app.modules.sri.models import FiscalDocument

    cert_path = tmp_path / "certs" / "emitter.p12"
    _make_p12(cert_path, "secret")
    monkeypatch.setattr(settings, "sri_cert_dir", str(tmp_path / "certs"))
    monkeypatch.setattr(settings, "sri_pdf_dir", str(tmp_path / "pdfs"))
    monkeypatch.setattr(settings, "sri_cert_password", "secret")

    order = _seed_paid_order(db_session)
    service = SriService(db_session, soap_client=_FakeSoap())
    service.update_config(
        SriConfigUpdate(
            tax_regime="RIMPE_EMPRENDEDOR",
            ambiente="1",
            establecimiento="001",
            punto_emision="001",
            dir_matriz="Matriz Quito",
            dir_establecimiento="Estab Quito",
            obligado_contabilidad="NO",
            contribuyente_especial="",
        )
    )
    cfg = service.config_repo.get_or_create()
    cfg.cert_filename = "emitter.p12"
    cfg.cert_stored = True
    db_session.commit()

    doc_read = service.emit_for_order(
        order.id,
        EmitFiscalDocumentRequest(doc_type="FACTURA", send_to_sri=False),
    )
    stored = db_session.get(FiscalDocument, doc_read.id)
    assert stored is not None
    original_xml = stored.xml_signed
    stored.status = FiscalDocStatus.SENT.value
    stored.sri_messages = (
        "ERROR — 65 — FECHA EMISIÓN EXTEMPORANEA — La fecha de emisión "
        "está fuera del rango de tolerancia"
    )
    db_session.commit()

    with pytest.raises(HTTPException) as exc:
        service.retry_authorization(doc_read.id)
    assert exc.value.status_code == 409
    assert "error 65" in exc.value.detail.lower()
    db_session.refresh(stored)
    assert stored.xml_signed == original_xml
