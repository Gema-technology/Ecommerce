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
from app.modules.quotes.models import Quote
from app.modules.sri.timeutil import format_ecuador_datetime
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


def _format_pct(value: Any) -> str:
    try:
        num = float(value) * 100
    except (TypeError, ValueError):
        return str(value)
    return f"{num:.0f}%"


_env.filters["money"] = _format_money
_env.filters["pct"] = _format_pct
_env.filters["ecuador_dt"] = format_ecuador_datetime


def business_info(store_config: StoreConfigRead | None = None) -> dict[str, str]:
    cfg = store_config or StoreConfigRead.from_settings()
    return cfg.business_dict()


def render_quote_html(
    quote: Quote, *, store_config: StoreConfigRead | None = None
) -> str:
    template = _env.get_template("quote_pdf.html")
    return template.render(
        quote=quote,
        items=quote.items,
        business=business_info(store_config),
        logo_src=business_logo_data_uri(settings.business_logo_path or None),
    )


def _generate_pdf_weasyprint(html: str) -> bytes:
    from weasyprint import HTML

    return HTML(string=html).write_pdf()


def _generate_pdf_reportlab(
    quote: Quote, *, store_config: StoreConfigRead | None = None
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
    biz = business_info(store_config)

    text_lines: list[Any] = [Paragraph(f"<b>{biz.get('name', '')}</b>", brand_name)]
    for line in [
        f"RUC: {biz['ruc']}" if biz.get("ruc") else None,
        biz.get("address") or None,
        f"Tel: {biz['phone']}" if biz.get("phone") else None,
        biz.get("email") or None,
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

    right_lines = [
        Paragraph("PROFORMA / COTIZACIÓN", doc_type_style),
        Paragraph(quote.number, number_style),
        Paragraph(
            f"Fecha: {format_ecuador_datetime(quote.created_at, False)}",
            right_meta,
        ),
    ]
    if quote.valid_until:
        right_lines.append(
            Paragraph(
                f"Válida hasta: {quote.valid_until.strftime('%d/%m/%Y')}",
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
    story.append(
        build_client_card(
            name=quote.client_name or "—",
            fields=[
                ("Identificación", quote.client_id_number),
                ("Teléfono", quote.client_phone),
                ("Correo", quote.client_email),
                ("Dirección", quote.client_address),
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
    rows: list[list[Any]] = [["Producto", "Cant.", "P. unit.", "Subtotal"]]
    for item in quote.items:
        rows.append(
            [
                str(item.product_name)[:80],
                str(item.quantity),
                _format_money(item.unit_price),
                _format_money(item.line_total),
            ]
        )
    table = Table(
        rows,
        colWidths=[90 * mm, 22 * mm, 34 * mm, 34 * mm],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0a0e13")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 8),
                ("FONTSIZE", (0, 1), (-1, -1), 9),
                ("ALIGN", (1, 0), (1, -1), "CENTER"),
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

    totals = Table(
        [
            ["Subtotal", _format_money(quote.subtotal)],
            [
                f"IVA ({_format_pct(quote.iva_pct)})",
                _format_money(quote.iva_amount),
            ],
            ["Total USD", _format_money(quote.total)],
        ],
        colWidths=[40 * mm, 30 * mm],
        hAlign="RIGHT",
    )
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

    if quote.notes:
        story.append(Spacer(1, 14))
        notes_box = Table(
            [
                [Paragraph("<b>Notas y condiciones</b>", styles["Normal"])],
                [Paragraph(str(quote.notes).replace("\n", "<br/>"), meta)],
            ],
            colWidths=[180 * mm],
        )
        notes_box.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f9fafb")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#dbe3ee")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("LINEBEFORE", (0, 0), (0, -1), 3, colors.HexColor("#3d8bff")),
                ]
            )
        )
        story.append(notes_box)

    story.append(Spacer(1, 24))
    story.append(Paragraph("Documento generado por GEMA Technology.", footer_style))
    story.append(
        Paragraph(
            "Documento informativo — no constituye comprobante fiscal "
            "autorizado por el SRI.",
            footer_style,
        )
    )

    def _page_footer(canvas: Any, _doc: Any) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#6b7280"))
        left = biz.get("name", "")
        if biz.get("phone"):
            left = f"{left} · {biz['phone']}"
        canvas.drawString(16 * mm, 12 * mm, left[:70])
        canvas.drawRightString(
            A4[0] - 16 * mm, 12 * mm, f"Página {canvas.getPageNumber()}"
        )
        canvas.restoreState()

    pdf.build(story, onFirstPage=_page_footer, onLaterPages=_page_footer)
    return buffer.getvalue()


def generate_quote_pdf(
    quote: Quote, *, store_config: StoreConfigRead | None = None
) -> bytes:
    html = render_quote_html(quote, store_config=store_config)
    try:
        return _generate_pdf_weasyprint(html)
    except Exception:
        # Windows often lacks WeasyPrint native deps; ReportLab keeps the styled layout.
        return _generate_pdf_reportlab(quote, store_config=store_config)
