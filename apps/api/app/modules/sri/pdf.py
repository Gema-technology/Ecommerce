"""PDF generation for notas de venta and RIDE."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.brand_assets import (
    business_logo_data_uri,
    resolve_business_logo_path,
)
from app.core.config import settings
from app.core.pdf_client_card import build_client_card
from app.modules.sri.models import FiscalDocument
from app.modules.store_config.schemas import StoreConfigRead

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


def _format_money(value: Any) -> str:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f"${num:,.2f}"


_env.filters["money"] = _format_money


REGIME_LABELS = {
    "RIMPE_NEGOCIO_POPULAR": "Contribuyente Régimen RIMPE — Negocio Popular",
    "RIMPE_EMPRENDEDOR": "Contribuyente Régimen RIMPE — Emprendedor",
    "GENERAL": "Régimen General",
}

BUYER_ID_LABELS = {
    "CONSUMIDOR_FINAL": "Consumidor final",
    "CEDULA": "Cédula",
    "RUC": "RUC",
    "PASAPORTE": "Pasaporte",
}


def buyer_id_label(id_type: str | None) -> str:
    if not id_type:
        return "Identificación"
    return BUYER_ID_LABELS.get(id_type, id_type)


def _doc_title(doc: FiscalDocument) -> str:
    if doc.doc_type == "NOTA_VENTA":
        return "NOTA DE VENTA"
    return "FACTURA ELECTRÓNICA"


def _legal_legend(doc: FiscalDocument) -> str:
    if doc.doc_type == "NOTA_VENTA":
        return (
            "Nota de venta — documento interno; "
            "no requiere autorización electrónica del SRI."
        )
    return "Representación impresa del documento electrónico (RIDE)."


def _generate_pdf_weasyprint(html: str) -> bytes:
    from weasyprint import HTML

    return HTML(string=html).write_pdf()


def _generate_pdf_reportlab_nota(
    doc: FiscalDocument,
    *,
    business: dict[str, str],
    regime: str,
) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Image,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    buffer = BytesIO()
    pdf = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=18 * mm,
        bottomMargin=22 * mm,
    )
    styles = getSampleStyleSheet()
    brand_name = ParagraphStyle(
        "BrandName",
        parent=styles["Heading1"],
        fontSize=16,
        textColor=colors.HexColor("#0a0e13"),
        spaceAfter=4,
        leading=20,
    )
    meta = ParagraphStyle(
        "Meta",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#4b5563"),
        leading=12,
    )
    doc_type_style = ParagraphStyle(
        "DocType",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#3d8bff"),
        alignment=TA_RIGHT,
        fontName="Helvetica-Bold",
        spaceAfter=2,
    )
    number_style = ParagraphStyle(
        "DocNumber",
        parent=styles["Normal"],
        fontSize=13,
        textColor=colors.HexColor("#0a0e13"),
        alignment=TA_RIGHT,
        fontName="Helvetica-Bold",
        spaceAfter=4,
    )
    right_meta = ParagraphStyle(
        "RightMeta",
        parent=meta,
        alignment=TA_RIGHT,
    )
    section = ParagraphStyle(
        "Section",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.HexColor("#6b7280"),
        spaceBefore=8,
        spaceAfter=4,
        fontName="Helvetica-Bold",
    )
    footer_style = ParagraphStyle(
        "Footer",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.HexColor("#6b7280"),
        alignment=TA_CENTER,
        leading=11,
    )
    story: list[Any] = []

    text_lines: list[Any] = [Paragraph(f"<b>{business.get('name', '')}</b>", brand_name)]
    for line in [
        f"RUC: {business['ruc']}" if business.get("ruc") else None,
        business.get("address") or None,
        f"Tel: {business['phone']}" if business.get("phone") else None,
        business.get("email") or None,
        REGIME_LABELS.get(regime, regime) if regime else None,
    ]:
        if line:
            text_lines.append(Paragraph(line, meta))

    logo_path = resolve_business_logo_path(settings.business_logo_path or None)
    if logo_path is not None:
        logo_img = Image(str(logo_path), width=22 * mm, height=22 * mm)
        left_block: Any = Table(
            [[logo_img, text_lines]],
            colWidths=[24 * mm, 71 * mm],
        )
        left_block.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
    else:
        left_block = text_lines

    title = _doc_title(doc)
    right_lines = [
        Paragraph(title, doc_type_style),
        Paragraph(doc.document_number, number_style),
    ]
    if doc.created_at:
        right_lines.append(
            Paragraph(
                f"Fecha: {doc.created_at.strftime('%d/%m/%Y %H:%M')}",
                right_meta,
            )
        )
    if doc.access_key:
        right_lines.append(
            Paragraph(f"Clave de acceso: {doc.access_key}", right_meta)
        )
    if doc.authorization_number:
        right_lines.append(
            Paragraph(
                f"Autorización SRI: {doc.authorization_number}",
                right_meta,
            )
        )

    header = Table(
        [[left_block, right_lines]],
        colWidths=[95 * mm, 85 * mm],
    )
    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, -1), 1.5, colors.HexColor("#3d8bff")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    story.append(header)
    story.append(Spacer(1, 12))

    story.append(Paragraph("CLIENTE", section))
    id_value = None
    if doc.buyer_id_number:
        id_value = f"{buyer_id_label(doc.buyer_id_type)} {doc.buyer_id_number}"
    story.append(
        build_client_card(
            name=doc.buyer_name or "—",
            fields=[
                ("Identificación", id_value),
                ("Correo", doc.buyer_email),
                ("Dirección", doc.buyer_address),
            ],
            styles=styles,
            colors=colors,
            mm=mm,
            Paragraph=Paragraph,
            Table=Table,
            TableStyle=TableStyle,
            ParagraphStyle=ParagraphStyle,
        )
    )
    story.append(Spacer(1, 12))

    story.append(Paragraph("DETALLE", section))
    rows: list[list[Any]] = [
        ["Cant.", "Descripción", "P. Unit.", "Desc.", "Total"]
    ]
    for item in doc.line_items or []:
        desc = str(item.get("description", ""))[:80]
        sku = item.get("sku")
        if sku:
            desc = f"{desc} ({sku})"
        rows.append(
            [
                str(item.get("quantity", "")),
                desc,
                _format_money(item.get("unit_price", 0)),
                _format_money(item.get("discount") or 0),
                _format_money(item.get("line_total", 0)),
            ]
        )
    table = Table(
        rows,
        colWidths=[18 * mm, 82 * mm, 28 * mm, 24 * mm, 28 * mm],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0a0e13")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 8),
                ("FONTSIZE", (0, 1), (-1, -1), 9),
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
                ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
                ("LINEBELOW", (0, 1), (-1, -1), 0.4, colors.HexColor("#e5e7eb")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 12))

    totals_data: list[list[Any]] = [
        ["Subtotal", _format_money(doc.subtotal)],
    ]
    if doc.discount_total and float(doc.discount_total) > 0:
        totals_data.append(["Descuento", _format_money(doc.discount_total)])
    if doc.tax_total and float(doc.tax_total) > 0:
        totals_data.append(
            [
                f"IVA ({float(doc.tax_rate) * 100:.0f}%)",
                _format_money(doc.tax_total),
            ]
        )
    if doc.shipping_total and float(doc.shipping_total) > 0:
        totals_data.append(["Envío", _format_money(doc.shipping_total)])
    totals_data.append(["Total", _format_money(doc.total)])

    totals = Table(totals_data, colWidths=[40 * mm, 30 * mm], hAlign="RIGHT")
    totals.setStyle(
        TableStyle(
            [
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, -1), (-1, -1), 12),
                ("LINEABOVE", (0, -1), (-1, -1), 1.5, colors.HexColor("#3d8bff")),
                ("TOPPADDING", (0, -1), (-1, -1), 8),
            ]
        )
    )
    story.append(totals)
    story.append(Spacer(1, 24))
    story.append(Paragraph("Documento generado por GEMA Technology.", footer_style))
    story.append(Paragraph(_legal_legend(doc), footer_style))

    def _page_footer(canvas: Any, _doc: Any) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#6b7280"))
        left = business.get("name", "")
        if business.get("phone"):
            left = f"{left} · {business['phone']}"
        canvas.drawString(16 * mm, 12 * mm, left[:70])
        page = canvas.getPageNumber()
        canvas.drawRightString(A4[0] - 16 * mm, 12 * mm, f"Página {page}")
        canvas.restoreState()

    pdf.build(story, onFirstPage=_page_footer, onLaterPages=_page_footer)
    return buffer.getvalue()


def _template_context(
    doc: FiscalDocument,
    *,
    store_config: StoreConfigRead,
    regime: str,
    title: str,
) -> dict[str, Any]:
    return {
        "doc": doc,
        "items": doc.line_items or [],
        "business": store_config.business_dict(),
        "regime_label": REGIME_LABELS.get(regime, regime),
        "buyer_id_label": buyer_id_label(doc.buyer_id_type),
        "title": title,
        "logo_src": business_logo_data_uri(settings.business_logo_path or None),
    }


def render_nota_venta_html(
    doc: FiscalDocument,
    *,
    store_config: StoreConfigRead,
    regime: str,
) -> str:
    template = _env.get_template("nota_venta_pdf.html")
    return template.render(
        **_template_context(
            doc,
            store_config=store_config,
            regime=regime,
            title="NOTA DE VENTA",
        )
    )


def render_ride_html(
    doc: FiscalDocument,
    *,
    store_config: StoreConfigRead,
    regime: str,
) -> str:
    template = _env.get_template("nota_venta_pdf.html")
    return template.render(
        **_template_context(
            doc,
            store_config=store_config,
            regime=regime,
            title="FACTURA ELECTRÓNICA",
        )
    )


def generate_fiscal_pdf(
    doc: FiscalDocument,
    *,
    store_config: StoreConfigRead,
    regime: str,
) -> bytes:
    if doc.doc_type == "FACTURA":
        html = render_ride_html(doc, store_config=store_config, regime=regime)
    else:
        html = render_nota_venta_html(doc, store_config=store_config, regime=regime)
    try:
        return _generate_pdf_weasyprint(html)
    except Exception:
        return _generate_pdf_reportlab_nota(
            doc,
            business=store_config.business_dict(),
            regime=regime,
        )
