"""Buyer identification used on notas de venta and facturas."""

from __future__ import annotations

import re

BUYER_ID_TYPES = ("CEDULA", "RUC", "PASAPORTE")


def normalize_buyer_identification(
    id_type: str | None,
    id_number: str | None,
) -> tuple[str | None, str | None]:
    """Return a clean type and number. Both empty means consumidor final."""
    cleaned_type = (id_type or "").strip().upper() or None
    cleaned_number = re.sub(r"\s+", "", (id_number or "").strip()) or None
    if cleaned_type is None and cleaned_number is None:
        return None, None
    if cleaned_type is None or cleaned_number is None:
        raise ValueError("Indica el tipo y el número de cédula, RUC o pasaporte")
    if cleaned_type not in BUYER_ID_TYPES:
        raise ValueError("Tipo de identificación no válido")
    if cleaned_type == "CEDULA":
        if not re.fullmatch(r"\d{10}", cleaned_number):
            raise ValueError("La cédula debe tener 10 dígitos")
    elif cleaned_type == "RUC":
        if not re.fullmatch(r"\d{13}", cleaned_number):
            raise ValueError("El RUC debe tener 13 dígitos")
    elif not re.fullmatch(r"[A-Za-z0-9]{5,20}", cleaned_number):
        raise ValueError("El pasaporte debe tener entre 5 y 20 caracteres")
    return cleaned_type, cleaned_number
