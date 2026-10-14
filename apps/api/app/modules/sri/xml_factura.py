"""XML builder for factura electrónica (tipo 01) — esquema SRI vigente."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from xml.etree.ElementTree import Element, SubElement, tostring


def _money(value: Decimal | float | str | int) -> str:
    return f"{Decimal(str(value)).quantize(Decimal('0.01')):.2f}"


def _text(parent: Element, tag: str, value: str | None) -> Element:
    el = SubElement(parent, tag)
    el.text = value if value is not None else ""
    return el


BUYER_TYPE_CODES = {
    "RUC": "04",
    "CEDULA": "05",
    "PASAPORTE": "06",
    "CONSUMIDOR_FINAL": "07",
}


@dataclass
class FacturaLine:
    codigo: str
    descripcion: str
    cantidad: Decimal
    precio_unitario: Decimal
    descuento: Decimal
    precio_total_sin_impuesto: Decimal
    iva_rate: Decimal  # 0 or 0.15
    iva_valor: Decimal


@dataclass
class FacturaPayload:
    ambiente: str
    tipo_emision: str
    razon_social: str
    nombre_comercial: str
    ruc: str
    clave_acceso: str
    codigo_establecimiento: str
    codigo_punto_emision: str
    secuencial: str
    dir_matriz: str
    dir_establecimiento: str
    obligado_contabilidad: str
    contribuyente_especial: str | None
    fecha_emision: date
    buyer_id_type: str
    buyer_id_number: str
    buyer_name: str
    buyer_address: str | None
    total_sin_impuestos: Decimal
    total_descuento: Decimal
    propina: Decimal
    importe_total: Decimal
    moneda: str
    lines: list[FacturaLine]
    payments: list[tuple[str, Decimal]]  # formaPago, total
    info_adicional: list[tuple[str, str]]
    rimpe_legend: str | None = None


def build_factura_xml(payload: FacturaPayload) -> str:
    root = Element("factura", {"id": "comprobante", "version": "1.1.0"})

    info_trib = SubElement(root, "infoTributaria")
    _text(info_trib, "ambiente", payload.ambiente)
    _text(info_trib, "tipoEmision", payload.tipo_emision)
    _text(info_trib, "razonSocial", payload.razon_social[:300])
    if payload.nombre_comercial:
        _text(info_trib, "nombreComercial", payload.nombre_comercial[:300])
    _text(info_trib, "ruc", payload.ruc)
    _text(info_trib, "claveAcceso", payload.clave_acceso)
    _text(info_trib, "codDoc", "01")
    _text(info_trib, "estab", payload.codigo_establecimiento)
    _text(info_trib, "ptoEmi", payload.codigo_punto_emision)
    _text(info_trib, "secuencial", payload.secuencial)
    _text(info_trib, "dirMatriz", payload.dir_matriz[:300])

    info_fac = SubElement(root, "infoFactura")
    fecha = payload.fecha_emision
    if isinstance(fecha, datetime):
        fecha = fecha.date()
    _text(info_fac, "fechaEmision", fecha.strftime("%d/%m/%Y"))
    _text(info_fac, "dirEstablecimiento", payload.dir_establecimiento[:300])
    if payload.contribuyente_especial:
        _text(info_fac, "contribuyenteEspecial", payload.contribuyente_especial)
    _text(info_fac, "obligadoContabilidad", payload.obligado_contabilidad)
    id_code = BUYER_TYPE_CODES.get(payload.buyer_id_type, "07")
    _text(info_fac, "tipoIdentificacionComprador", id_code)
    _text(info_fac, "razonSocialComprador", payload.buyer_name[:300])
    _text(info_fac, "identificacionComprador", payload.buyer_id_number)
    if payload.buyer_address:
        _text(info_fac, "direccionComprador", payload.buyer_address[:300])
    _text(info_fac, "totalSinImpuestos", _money(payload.total_sin_impuestos))
    _text(info_fac, "totalDescuento", _money(payload.total_descuento))

    total_con_impuestos = SubElement(info_fac, "totalConImpuestos")
    # Aggregate by tax code
    base0 = Decimal("0")
    base15 = Decimal("0")
    iva15 = Decimal("0")
    for line in payload.lines:
        if line.iva_rate and line.iva_rate > 0:
            base15 += line.precio_total_sin_impuesto
            iva15 += line.iva_valor
        else:
            base0 += line.precio_total_sin_impuesto

    if base0 > 0:
        ti = SubElement(total_con_impuestos, "totalImpuesto")
        _text(ti, "codigo", "2")
        _text(ti, "codigoPorcentaje", "0")
        _text(ti, "baseImponible", _money(base0))
        _text(ti, "valor", _money(Decimal("0")))
    if base15 > 0 or iva15 > 0:
        ti = SubElement(total_con_impuestos, "totalImpuesto")
        _text(ti, "codigo", "2")
        _text(ti, "codigoPorcentaje", "4")  # IVA 15%
        _text(ti, "baseImponible", _money(base15))
        _text(ti, "valor", _money(iva15))

    _text(info_fac, "propina", _money(payload.propina))
    _text(info_fac, "importeTotal", _money(payload.importe_total))
    _text(info_fac, "moneda", payload.moneda)

    pagos = SubElement(info_fac, "pagos")
    for forma, total in payload.payments:
        pago = SubElement(pagos, "pago")
        _text(pago, "formaPago", forma)
        _text(pago, "total", _money(total))

    detalles = SubElement(root, "detalles")
    for line in payload.lines:
        det = SubElement(detalles, "detalle")
        _text(det, "codigoPrincipal", (line.codigo or "001")[:25])
        _text(det, "descripcion", line.descripcion[:300])
        _text(det, "cantidad", _money(line.cantidad))
        _text(det, "precioUnitario", _money(line.precio_unitario))
        _text(det, "descuento", _money(line.descuento))
        _text(det, "precioTotalSinImpuesto", _money(line.precio_total_sin_impuesto))
        impuestos = SubElement(det, "impuestos")
        imp = SubElement(impuestos, "impuesto")
        _text(imp, "codigo", "2")
        if line.iva_rate and line.iva_rate > 0:
            _text(imp, "codigoPorcentaje", "4")
            _text(imp, "tarifa", "15.00")
        else:
            _text(imp, "codigoPorcentaje", "0")
            _text(imp, "tarifa", "0.00")
        _text(imp, "baseImponible", _money(line.precio_total_sin_impuesto))
        _text(imp, "valor", _money(line.iva_valor))

    extras = list(payload.info_adicional)
    if payload.rimpe_legend:
        extras.append(("Regimen", payload.rimpe_legend))
    if extras:
        info_ad = SubElement(root, "infoAdicional")
        for name, value in extras:
            campo = SubElement(info_ad, "campoAdicional", {"nombre": name[:300]})
            campo.text = value[:300]

    xml_bytes = tostring(root, encoding="utf-8", xml_declaration=True)
    return xml_bytes.decode("utf-8")
