from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.modules.orders.models import Order, OrderStatus
from app.modules.sri.access_key import build_access_key, format_document_number
from app.modules.sri.client import SriSoapClient
from app.modules.sri.models import (
    BuyerIdType,
    FiscalDocStatus,
    FiscalDocType,
    FiscalDocument,
    SriConfig,
    TaxRegime,
)
from app.modules.sri.pdf import generate_fiscal_pdf
from app.modules.sri.repository import FiscalDocumentRepository, SriConfigRepository
from app.modules.sri.schemas import (
    CertVerifyResponse,
    EmitFiscalDocumentRequest,
    FiscalDocumentListResponse,
    FiscalDocumentRead,
    SriConfigRead,
    SriConfigUpdate,
)
from app.modules.sri.signing import sign_comprobante_xml, verify_cert_loadable
from app.modules.sri.timeutil import ecuador_emission_date
from app.modules.sri.xml_factura import FacturaLine, FacturaPayload, build_factura_xml
from app.modules.store_config.service import StoreConfigService

def _postal_code(address: dict | None) -> str | None:
    if not isinstance(address, dict):
        return None
    code = address.get("postal_code")
    if code is None:
        return None
    cleaned = str(code).strip()
    return cleaned or None


def _address_without_postal(address: dict) -> str | None:
    parts = [
        address.get("address_line"),
        address.get("city"),
        address.get("province"),
    ]
    text = ", ".join(str(part).strip() for part in parts if part and str(part).strip())
    return text or None


def _drop_postal_code(address: str | None, postal_code: str | None) -> str | None:
    if not address:
        return address
    code = (postal_code or "").strip()
    if not code:
        return address
    parts = [part.strip() for part in address.split(",") if part.strip() and part.strip() != code]
    return ", ".join(parts) or None


EMITTABLE_STATUSES = {
    OrderStatus.PAID.value,
    OrderStatus.PROCESSING.value,
    OrderStatus.SHIPPED.value,
    OrderStatus.DELIVERED.value,
}

CONSUMIDOR_FINAL_ID = "9999999999999"
CF_MAX_TOTAL = Decimal("50.00")

REGIME_LEGENDS = {
    TaxRegime.RIMPE_NEGOCIO_POPULAR.value: "CONTRIBUYENTE RÉGIMEN RIMPE — NEGOCIO POPULAR",
    TaxRegime.RIMPE_EMPRENDEDOR.value: "CONTRIBUYENTE RÉGIMEN RIMPE — EMPRENDEDOR",
    TaxRegime.GENERAL.value: "RÉGIMEN GENERAL",
}


def _money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal("0.0001"))


class SriService:
    def __init__(
        self,
        db: Session,
        *,
        soap_client: SriSoapClient | None = None,
    ) -> None:
        self.db = db
        self.config_repo = SriConfigRepository(db)
        self.docs = FiscalDocumentRepository(db)
        self._soap_client = soap_client

    def _cert_dir(self) -> Path:
        path = Path(settings.sri_cert_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _pdf_dir(self) -> Path:
        path = Path(settings.sri_pdf_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _cert_path(self, cfg: SriConfig) -> Path | None:
        if not cfg.cert_stored or not cfg.cert_filename:
            return None
        path = self._cert_dir() / cfg.cert_filename
        return path if path.is_file() else None

    def _to_config_read(self, row: SriConfig) -> SriConfigRead:
        return SriConfigRead(
            tax_regime=row.tax_regime,  # type: ignore[arg-type]
            ambiente=row.ambiente,  # type: ignore[arg-type]
            establecimiento=row.establecimiento,
            punto_emision=row.punto_emision,
            dir_matriz=row.dir_matriz,
            dir_establecimiento=row.dir_establecimiento,
            obligado_contabilidad=row.obligado_contabilidad,  # type: ignore[arg-type]
            contribuyente_especial=row.contribuyente_especial,
            secuencial_nota_venta=row.secuencial_nota_venta,
            secuencial_factura=row.secuencial_factura,
            cert_filename=row.cert_filename,
            cert_stored=bool(row.cert_stored),
            cert_password_configured=bool((settings.sri_cert_password or "").strip()),
            updated_at=row.updated_at,
        )

    def _to_doc_read(self, doc: FiscalDocument) -> FiscalDocumentRead:
        return FiscalDocumentRead(
            id=doc.id,
            order_id=doc.order_id,
            doc_type=doc.doc_type,
            status=doc.status,
            establishment=doc.establishment,
            emission_point=doc.emission_point,
            sequential=doc.sequential,
            document_number=doc.document_number,
            access_key=doc.access_key,
            buyer_id_type=doc.buyer_id_type,
            buyer_id_number=doc.buyer_id_number,
            buyer_name=doc.buyer_name,
            buyer_email=doc.buyer_email,
            buyer_address=doc.buyer_address,
            currency=doc.currency,
            subtotal=doc.subtotal,
            tax_total=doc.tax_total,
            discount_total=doc.discount_total,
            shipping_total=doc.shipping_total,
            total=doc.total,
            tax_rate=doc.tax_rate,
            authorization_number=doc.authorization_number,
            authorized_at=doc.authorized_at,
            sri_messages=doc.sri_messages,
            has_pdf=bool(doc.pdf_path),
            has_xml=bool(doc.xml_signed or doc.xml_unsigned),
            line_items=doc.line_items,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
        )

    def get_config(self) -> SriConfigRead:
        existed = self.config_repo.get() is not None
        row = self.config_repo.get_or_create()
        if not existed:
            self.db.commit()
            self.db.refresh(row)
        return self._to_config_read(row)

    def update_config(self, payload: SriConfigUpdate) -> SriConfigRead:
        row = self.config_repo.get_or_create()
        row.tax_regime = payload.tax_regime
        row.ambiente = payload.ambiente
        row.establecimiento = payload.establecimiento
        row.punto_emision = payload.punto_emision
        row.dir_matriz = payload.dir_matriz
        row.dir_establecimiento = payload.dir_establecimiento
        row.obligado_contabilidad = payload.obligado_contabilidad
        row.contribuyente_especial = payload.contribuyente_especial
        self.db.commit()
        self.db.refresh(row)
        return self._to_config_read(row)

    async def upload_certificate(self, file: UploadFile) -> SriConfigRead:
        if not file.filename or not file.filename.lower().endswith((".p12", ".pfx")):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Certificate must be a .p12 or .pfx file",
            )
        data = await file.read()
        if not data:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")
        if len(data) > 2_000_000:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File too large")

        safe_name = "emitter.p12"
        dest = self._cert_dir() / safe_name
        dest.write_bytes(data)

        password = (settings.sri_cert_password or "").strip()
        if password:
            try:
                verify_cert_loadable(dest, password)
            except Exception as exc:
                dest.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Could not open certificate with SRI_CERT_PASSWORD: {exc}",
                ) from exc

        row = self.config_repo.get_or_create()
        row.cert_filename = safe_name
        row.cert_stored = True
        self.db.commit()
        self.db.refresh(row)
        return self._to_config_read(row)

    def verify_certificate(self) -> CertVerifyResponse:
        row = self.config_repo.get_or_create()
        path = self._cert_path(row)
        password = (settings.sri_cert_password or "").strip()
        if path is None:
            return CertVerifyResponse(ok=False, message="No certificate uploaded")
        if not password:
            return CertVerifyResponse(
                ok=False,
                message="Set SRI_CERT_PASSWORD in the environment",
            )
        try:
            info = verify_cert_loadable(path, password)
            return CertVerifyResponse(ok=True, **info)
        except Exception as exc:
            return CertVerifyResponse(ok=False, message=str(exc))

    def list_documents(self, *, page: int = 1, page_size: int = 20) -> FiscalDocumentListResponse:
        items, total = self.docs.list_all(page=page, page_size=page_size)
        return FiscalDocumentListResponse(
            items=[self._to_doc_read(d) for d in items],
            page=page,
            page_size=page_size,
            total=total,
            total_pages=self.docs.total_pages(total, page_size),
        )

    def get_document(self, doc_id: UUID) -> FiscalDocumentRead:
        doc = self.docs.get(doc_id)
        if doc is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
        return self._to_doc_read(doc)

    def list_for_order(self, order_id: UUID) -> list[FiscalDocumentRead]:
        return [self._to_doc_read(d) for d in self.docs.list_for_order(order_id)]

    def _resolve_buyer(
        self, order: Order, payload: EmitFiscalDocumentRequest
    ) -> tuple[str, str, str, str | None, str | None]:
        id_type = payload.buyer_id_type or order.buyer_id_type or BuyerIdType.CONSUMIDOR_FINAL.value
        id_number = payload.buyer_id_number or order.buyer_id_number or ""
        name = payload.buyer_name or order.customer_name or "Consumidor Final"
        email = payload.buyer_email or order.customer_email
        address = payload.buyer_address
        if not address and order.shipping_address:
            address = _address_without_postal(order.shipping_address)
        address = _drop_postal_code(address, _postal_code(order.shipping_address))

        if id_type == BuyerIdType.CONSUMIDOR_FINAL.value:
            id_number = CONSUMIDOR_FINAL_ID
            if not name.strip():
                name = "Consumidor Final"
        elif not id_number:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="buyer_id_number is required for this identification type",
            )

        return id_type, id_number, name.strip(), email, address

    def _line_items(self, order: Order) -> list[dict]:
        return [
            {
                "sku": item.sku_snapshot,
                "description": item.product_name_snapshot,
                "quantity": item.quantity,
                "unit_price": str(item.unit_price),
                "discount": str(item.line_discount or 0),
                "line_total": str(item.line_total),
            }
            for item in order.items
        ]

    def _persist_pdf(self, doc: FiscalDocument, cfg: SriConfig) -> None:
        order = self.db.get(Order, doc.order_id)
        if order is not None:
            doc.buyer_address = _drop_postal_code(
                doc.buyer_address, _postal_code(order.shipping_address)
            )
        store = StoreConfigService(self.db).get_read()
        pdf_bytes = generate_fiscal_pdf(doc, store_config=store, regime=cfg.tax_regime)
        filename = f"{doc.doc_type.lower()}_{doc.document_number.replace('-', '_')}.pdf"
        path = self._pdf_dir() / filename
        path.write_bytes(pdf_bytes)
        doc.pdf_path = str(path)

    def emit_for_order(
        self, order_id: UUID, payload: EmitFiscalDocumentRequest
    ) -> FiscalDocumentRead:
        order = self.db.scalar(
            select(Order)
            .where(Order.id == order_id)
            .options(selectinload(Order.items))
        )
        if order is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
        if order.status not in EMITTABLE_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Order must be paid (or later) to emit a fiscal document",
            )

        existing = self.docs.active_for_order(order_id)
        if existing is not None and existing.status not in {
            FiscalDocStatus.REJECTED.value,
            FiscalDocStatus.CANCELLED.value,
        }:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Order already has fiscal document {existing.document_number}",
            )

        buyer = self._resolve_buyer(order, payload)
        id_type, id_number, name, email, address = buyer

        if payload.doc_type == FiscalDocType.FACTURA.value and not address:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La factura requiere la dirección del comprador",
            )

        if (
            id_type == BuyerIdType.CONSUMIDOR_FINAL.value
            and payload.doc_type == FiscalDocType.FACTURA.value
            and _money(order.total) > CF_MAX_TOTAL
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Consumidor final invoices cannot exceed $50.00; use cédula/RUC",
            )

        # Persist buyer on order when provided
        if payload.buyer_id_type:
            order.buyer_id_type = payload.buyer_id_type
        if payload.buyer_id_number:
            order.buyer_id_number = payload.buyer_id_number
        elif id_type == BuyerIdType.CONSUMIDOR_FINAL.value:
            order.buyer_id_type = id_type
            order.buyer_id_number = id_number

        if payload.doc_type == FiscalDocType.NOTA_VENTA.value:
            doc = self._emit_nota_venta(order, id_type, id_number, name, email, address)
        else:
            doc = self._emit_factura(
                order,
                id_type,
                id_number,
                name,
                email,
                address,
                send_to_sri=payload.send_to_sri,
            )

        self.db.commit()
        self.db.refresh(doc)
        return self._to_doc_read(doc)

    def _emit_nota_venta(
        self,
        order: Order,
        id_type: str,
        id_number: str,
        name: str,
        email: str | None,
        address: str | None,
    ) -> FiscalDocument:
        cfg = self.config_repo.get_for_update()
        cfg.secuencial_nota_venta = int(cfg.secuencial_nota_venta or 0) + 1
        sequential = cfg.secuencial_nota_venta
        doc_number = format_document_number(
            cfg.establecimiento, cfg.punto_emision, sequential
        )

        # Notas de venta: without IVA (RIMPE NP style); totals from order merchandise+shipping
        merchandise = _money(order.subtotal - order.discount_total)
        total = _money(merchandise + order.shipping_total)

        doc = FiscalDocument(
            order_id=order.id,
            doc_type=FiscalDocType.NOTA_VENTA.value,
            status=FiscalDocStatus.ISSUED.value,
            establishment=cfg.establecimiento,
            emission_point=cfg.punto_emision,
            sequential=sequential,
            document_number=doc_number,
            buyer_id_type=id_type,
            buyer_id_number=id_number,
            buyer_name=name,
            buyer_email=email,
            buyer_address=address,
            currency=order.currency,
            subtotal=merchandise,
            tax_total=Decimal("0"),
            discount_total=order.discount_total,
            shipping_total=order.shipping_total,
            total=total,
            tax_rate=Decimal("0"),
            line_items=self._line_items(order),
        )
        self.docs.add(doc)
        self._persist_pdf(doc, cfg)
        return doc

    def _emit_factura(
        self,
        order: Order,
        id_type: str,
        id_number: str,
        name: str,
        email: str | None,
        address: str | None,
        *,
        send_to_sri: bool,
    ) -> FiscalDocument:
        store = StoreConfigService(self.db).get_read()
        ruc = "".join(c for c in (store.business_ruc or "") if c.isdigit())
        if len(ruc) != 13:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Configure a valid 13-digit business RUC in store settings",
            )

        cfg = self.config_repo.get_for_update()
        if not cfg.dir_matriz.strip() or not cfg.dir_establecimiento.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Configure dir_matriz and dir_establecimiento in SRI settings",
            )

        cert_path = self._cert_path(cfg)
        password = (settings.sri_cert_password or "").strip()
        if cert_path is None or not password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Upload a .p12 certificate and set SRI_CERT_PASSWORD "
                    "before emitting invoices"
                ),
            )

        cfg.secuencial_factura = int(cfg.secuencial_factura or 0) + 1
        sequential = cfg.secuencial_factura
        doc_number = format_document_number(
            cfg.establecimiento, cfg.punto_emision, sequential
        )
        # SRI fechaEmision / claveAcceso use Ecuador civil date, not UTC midnight edge.
        emission_date = ecuador_emission_date()
        access_key = build_access_key(
            emission_date=emission_date,
            doc_type_code="01",
            ruc=ruc,
            ambiente=cfg.ambiente,
            establecimiento=cfg.establecimiento,
            punto_emision=cfg.punto_emision,
            sequential=sequential,
        )

        # Sprint A3 opción A: factura totals follow the paid order snapshot.
        # Do not rewrite historical order.total / tax_total here.
        merchandise = _money(order.subtotal - order.discount_total)
        shipping = _money(order.shipping_total or 0)
        # XML base sin impuestos = merchandise + shipping (IVA only on merchandise in v1).
        taxable_base = _money(merchandise + shipping)

        if cfg.tax_regime == TaxRegime.RIMPE_NEGOCIO_POPULAR.value:
            # Negocio Popular no percibe IVA. El comprobante sale con tarifa 0
            # aunque la tienda tenga COMMERCE_TAX_ENABLED.
            tax_rate = Decimal("0.0000")
            tax_total = Decimal("0.0000")
            total = taxable_base
        elif settings.commerce_tax_enabled:
            tax_rate = _money(Decimal(str(settings.commerce_tax_rate)))
            tax_total = _money(order.tax_total)
            total = _money(order.total)
            expected_tax = _money(merchandise * tax_rate)
            if abs(tax_total - expected_tax) > Decimal("0.01"):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Order tax_total is inconsistent with COMMERCE_TAX_RATE "
                        "merchandise base; refuse to emit divergent factura"
                    ),
                )
            if abs(total - _money(taxable_base + tax_total)) > Decimal("0.01"):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Order total is inconsistent with subtotal/shipping/tax; "
                        "refuse to emit divergent factura"
                    ),
                )
        else:
            if settings.is_production or settings.is_staging:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "Cannot emit FACTURA while COMMERCE_TAX_ENABLED=false in "
                        "staging/production (opción A requires checkout IVA). "
                        "Enable COMMERCE_TAX_ENABLED=true or use development only."
                    ),
                )
            # Development/lab: align with order (no silent IVA inflate).
            tax_rate = Decimal("0.0000")
            tax_total = _money(order.tax_total)
            total = _money(order.total)

        lines: list[FacturaLine] = []
        for item in order.items:
            line_base = _money(item.line_total)
            iva = _money(line_base * tax_rate) if tax_rate > 0 else Decimal("0.0000")
            lines.append(
                FacturaLine(
                    codigo=item.sku_snapshot[:25],
                    descripcion=item.product_name_snapshot,
                    cantidad=Decimal(item.quantity),
                    precio_unitario=item.unit_price,
                    descuento=_money(item.line_discount or 0),
                    precio_total_sin_impuesto=line_base,
                    iva_rate=tax_rate,
                    iva_valor=iva,
                )
            )
        if shipping > 0:
            lines.append(
                FacturaLine(
                    codigo="ENVIO",
                    descripcion="Envío / transporte",
                    cantidad=Decimal("1"),
                    precio_unitario=shipping,
                    descuento=Decimal("0"),
                    precio_total_sin_impuesto=shipping,
                    # Shipping not in checkout taxable base (v1).
                    iva_rate=tax_rate if tax_rate > 0 else Decimal("0"),
                    iva_valor=Decimal("0.0000"),
                )
            )

        extras: list[tuple[str, str]] = []
        if email:
            extras.append(("Email", email))
        extras.append(("Orden", order.order_number))

        payload_xml = FacturaPayload(
            ambiente=cfg.ambiente,
            tipo_emision="1",
            razon_social=store.business_name,
            nombre_comercial=store.business_name,
            ruc=ruc,
            clave_acceso=access_key,
            codigo_establecimiento=cfg.establecimiento,
            codigo_punto_emision=cfg.punto_emision,
            secuencial=f"{sequential:09d}",
            dir_matriz=cfg.dir_matriz,
            dir_establecimiento=cfg.dir_establecimiento,
            obligado_contabilidad=cfg.obligado_contabilidad,
            contribuyente_especial=cfg.contribuyente_especial or None,
            fecha_emision=emission_date,
            buyer_id_type=id_type,
            buyer_id_number=id_number,
            buyer_name=name,
            buyer_address=address,
            total_sin_impuestos=taxable_base,
            total_descuento=order.discount_total,
            propina=Decimal("0"),
            importe_total=total,
            moneda="DOLAR",
            lines=lines,
            payments=[("01", total)],  # sin utilización del sistema financiero
            info_adicional=extras,
            rimpe_legend=REGIME_LEGENDS.get(cfg.tax_regime),
        )
        xml_unsigned = build_factura_xml(payload_xml)
        xml_signed = sign_comprobante_xml(xml_unsigned, cert_path, password)

        doc = FiscalDocument(
            order_id=order.id,
            doc_type=FiscalDocType.FACTURA.value,
            status=FiscalDocStatus.SIGNED.value,
            establishment=cfg.establecimiento,
            emission_point=cfg.punto_emision,
            sequential=sequential,
            document_number=doc_number,
            access_key=access_key,
            buyer_id_type=id_type,
            buyer_id_number=id_number,
            buyer_name=name,
            buyer_email=email,
            buyer_address=address,
            currency=order.currency,
            subtotal=merchandise,
            tax_total=tax_total,
            discount_total=order.discount_total,
            shipping_total=order.shipping_total,
            total=total,
            tax_rate=tax_rate,
            xml_unsigned=xml_unsigned,
            xml_signed=xml_signed,
            line_items=self._line_items(order),
        )
        self.docs.add(doc)
        self._persist_pdf(doc, cfg)

        if send_to_sri:
            self._send_and_authorize(doc, cfg)

        return doc

    def _get_soap(self, ambiente: str) -> SriSoapClient:
        if self._soap_client is not None:
            return self._soap_client
        return SriSoapClient(ambiente=ambiente)

    def _send_and_authorize(self, doc: FiscalDocument, cfg: SriConfig) -> None:
        assert doc.xml_signed and doc.access_key
        client = self._get_soap(cfg.ambiente)
        try:
            recepcion = client.enviar_comprobante(doc.xml_signed)
        except Exception as exc:
            doc.status = FiscalDocStatus.REJECTED.value
            doc.sri_messages = f"Recepción error: {exc}"
            return

        doc.sri_messages = "; ".join(recepcion.messages) or recepcion.estado
        if recepcion.estado.upper() not in {"RECIBIDA", "DEVUELTA"}:
            doc.status = FiscalDocStatus.REJECTED.value
            return

        # DEVUELTA often means already received or validation issues — still try auth
        doc.status = FiscalDocStatus.SENT.value
        try:
            auth = client.autorizar_comprobante(doc.access_key)
        except Exception as exc:
            doc.sri_messages = (doc.sri_messages or "") + f" | Autorización error: {exc}"
            return

        msg = "; ".join(auth.messages)
        if msg:
            doc.sri_messages = ((doc.sri_messages or "") + " | " + msg).strip(" |")

        estado = (auth.estado or "").upper()
        if estado == "AUTORIZADO":
            doc.status = FiscalDocStatus.AUTHORIZED.value
            doc.authorization_number = auth.numero_autorizacion or doc.access_key
            doc.authorized_at = datetime.now(UTC)
            if auth.comprobante_xml:
                doc.xml_signed = auth.comprobante_xml
            self._persist_pdf(doc, cfg)
        elif estado in {"NO AUTORIZADO", "RECHAZADO"}:
            doc.status = FiscalDocStatus.REJECTED.value
        # else leave as SENT for retry

    def retry_authorization(self, doc_id: UUID) -> FiscalDocumentRead:
        doc = self.docs.get(doc_id)
        if doc is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
        if doc.doc_type != FiscalDocType.FACTURA.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only facturas can be authorized with SRI",
            )
        if doc.status == FiscalDocStatus.AUTHORIZED.value:
            return self._to_doc_read(doc)
        if not doc.xml_signed or not doc.access_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Document has no signed XML / access key",
            )

        # Error 65 embeds an incorrect fechaEmision in the signed XML / access key.
        # Re-sending the same bytes cannot fix it; emit a new FACTURA instead.
        msgs = (doc.sri_messages or "").upper()
        if "65" in msgs and ("FECHA" in msgs or "EMISION" in msgs or "EMISIÓN" in msgs):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "SRI error 65 (fecha de emisión extemporánea) is baked into this "
                    "document's signed XML. Do not retry the same comprobante; emit a "
                    "new FACTURA so fechaEmision/claveAcceso use America/Guayaquil."
                ),
            )

        cfg = self.config_repo.get_or_create()
        if doc.status in {FiscalDocStatus.SIGNED.value, FiscalDocStatus.REJECTED.value}:
            # Re-send then authorize
            self._send_and_authorize(doc, cfg)
        else:
            client = self._get_soap(cfg.ambiente)
            try:
                auth = client.autorizar_comprobante(doc.access_key)
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"SRI authorization failed: {exc}",
                ) from exc
            msg = "; ".join(auth.messages)
            if msg:
                doc.sri_messages = msg
            if (auth.estado or "").upper() == "AUTORIZADO":
                doc.status = FiscalDocStatus.AUTHORIZED.value
                doc.authorization_number = auth.numero_autorizacion or doc.access_key
                doc.authorized_at = datetime.now(UTC)
                if auth.comprobante_xml:
                    doc.xml_signed = auth.comprobante_xml
                self._persist_pdf(doc, cfg)
            elif (auth.estado or "").upper() in {"NO AUTORIZADO", "RECHAZADO"}:
                doc.status = FiscalDocStatus.REJECTED.value
            else:
                doc.status = FiscalDocStatus.SENT.value

        self.db.commit()
        self.db.refresh(doc)
        return self._to_doc_read(doc)

    def get_pdf_bytes(self, doc_id: UUID) -> tuple[bytes, str]:
        doc = self.docs.get(doc_id)
        if doc is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
        # Always regenerate so template/layout updates apply to existing docs.
        cfg = self.config_repo.get_or_create()
        self._persist_pdf(doc, cfg)
        self.db.commit()
        assert doc.pdf_path
        return Path(doc.pdf_path).read_bytes(), f"{doc.document_number}.pdf"

    def get_xml_text(self, doc_id: UUID) -> tuple[str, str]:
        doc = self.docs.get(doc_id)
        if doc is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
        xml = doc.xml_signed or doc.xml_unsigned
        if not xml:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No XML for this document",
            )
        name = f"{doc.access_key or doc.document_number}.xml"
        return xml, name
