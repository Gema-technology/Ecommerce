"""Shared professional client card for ReportLab PDF fallbacks."""

from __future__ import annotations

from typing import Any


def build_client_card(
    *,
    name: str,
    fields: list[tuple[str, str | None]],
    styles: Any,
    colors: Any,
    mm: Any,
    Paragraph: Any,
    Table: Any,
    TableStyle: Any,
    ParagraphStyle: Any,
) -> Any:
    """Return a styled ReportLab table: name + labeled fields in a 2-column grid."""
    label_style = ParagraphStyle(
        "ClientLabel",
        parent=styles["Normal"],
        fontSize=7.5,
        textColor=colors.HexColor("#6b7280"),
        fontName="Helvetica-Bold",
        leading=9,
        spaceAfter=1,
    )
    value_style = ParagraphStyle(
        "ClientValue",
        parent=styles["Normal"],
        fontSize=9.5,
        textColor=colors.HexColor("#111827"),
        leading=12,
    )
    name_style = ParagraphStyle(
        "ClientName",
        parent=styles["Normal"],
        fontSize=11,
        textColor=colors.HexColor("#0a0e13"),
        fontName="Helvetica-Bold",
        leading=14,
        spaceAfter=2,
    )

    cleaned = [
        (label, str(value).strip())
        for label, value in fields
        if value and str(value).strip()
    ]

    def mini_field(label: str, value: str, width: float) -> Any:
        cell = Table(
            [
                [Paragraph(label.upper(), label_style)],
                [Paragraph(value, value_style)],
            ],
            colWidths=[width],
        )
        cell.setStyle(
            TableStyle(
                [
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )
        return cell

    grid_rows: list[list[Any]] = [[Paragraph(name, name_style), ""]]
    col_w = 84 * mm
    i = 0
    while i < len(cleaned):
        left = mini_field(cleaned[i][0], cleaned[i][1], col_w)
        if i + 1 < len(cleaned):
            right = mini_field(cleaned[i + 1][0], cleaned[i + 1][1], col_w)
            grid_rows.append([left, right])
            i += 2
        else:
            grid_rows.append([left, ""])
            i += 1

    card = Table(grid_rows, colWidths=[90 * mm, 90 * mm])
    card.setStyle(
        TableStyle(
            [
                ("SPAN", (0, 0), (1, 0)),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f3f6fa")),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#cfd8e6")),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, 0), 10),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                ("TOPPADDING", (0, 1), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (1, 0), 0.4, colors.HexColor("#dbe3ee")),
            ]
        )
    )
    return card
