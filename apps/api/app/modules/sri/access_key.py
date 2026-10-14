"""Clave de acceso (49 dígitos) según especificación SRI Ecuador."""

from __future__ import annotations

import random
from datetime import date, datetime


def modulo11_check_digit(body48: str) -> str:
    """Dígito verificador módulo 11 para clave de acceso SRI."""
    if len(body48) != 48 or not body48.isdigit():
        raise ValueError("Access key body must be 48 digits")
    factors = [2, 3, 4, 5, 6, 7]
    total = 0
    factor_idx = 0
    for digit in reversed(body48):
        total += int(digit) * factors[factor_idx]
        factor_idx = (factor_idx + 1) % len(factors)
    remainder = total % 11
    check = 11 - remainder
    if check == 11:
        return "0"
    if check == 10:
        return "1"
    return str(check)


def build_access_key(
    *,
    emission_date: date | datetime,
    doc_type_code: str,
    ruc: str,
    ambiente: str,
    establecimiento: str,
    punto_emision: str,
    sequential: int,
    numeric_code: str | None = None,
    emission_type: str = "1",
) -> str:
    """
    Build 49-digit clave de acceso.

    fecha(8) + tipo(2) + ruc(13) + ambiente(1) + estab(3) + pto(3)
    + secuencial(9) + codigo(8) + tipoEmision(1) + digito(1)
    """
    if isinstance(emission_date, datetime):
        emission_date = emission_date.date()
    date_part = emission_date.strftime("%d%m%Y")
    ruc_clean = "".join(c for c in ruc if c.isdigit()).zfill(13)[:13]
    estab = establecimiento.zfill(3)[:3]
    pto = punto_emision.zfill(3)[:3]
    seq = f"{int(sequential):09d}"
    code = numeric_code or f"{random.randint(0, 99_999_999):08d}"
    if len(code) != 8 or not code.isdigit():
        raise ValueError("numeric_code must be 8 digits")
    tipo = doc_type_code.zfill(2)[:2]
    amb = str(ambiente)[:1]
    emision = str(emission_type)[:1]
    body = f"{date_part}{tipo}{ruc_clean}{amb}{estab}{pto}{seq}{code}{emision}"
    return body + modulo11_check_digit(body)


def format_document_number(establecimiento: str, punto_emision: str, sequential: int) -> str:
    return f"{establecimiento.zfill(3)[:3]}-{punto_emision.zfill(3)[:3]}-{int(sequential):09d}"
