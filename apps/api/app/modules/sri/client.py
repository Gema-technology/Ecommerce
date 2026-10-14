"""Cliente SOAP SRI — recepción y autorización offline."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any

WSDL_RECEPCION = {
    "1": (
        "https://celcer.sri.gob.ec/comprobantes-electronicos-ws/"
        "RecepcionComprobantesOffline?wsdl"
    ),
    "2": (
        "https://cel.sri.gob.ec/comprobantes-electronicos-ws/"
        "RecepcionComprobantesOffline?wsdl"
    ),
}

WSDL_AUTORIZACION = {
    "1": (
        "https://celcer.sri.gob.ec/comprobantes-electronicos-ws/"
        "AutorizacionComprobantesOffline?wsdl"
    ),
    "2": (
        "https://cel.sri.gob.ec/comprobantes-electronicos-ws/"
        "AutorizacionComprobantesOffline?wsdl"
    ),
}


@dataclass
class RecepcionResult:
    estado: str
    messages: list[str]
    raw: Any = None


@dataclass
class AutorizacionResult:
    estado: str
    numero_autorizacion: str | None
    fecha_autorizacion: str | None
    comprobante_xml: str | None
    messages: list[str]
    raw: Any = None


def _extract_messages(obj: Any) -> list[str]:
    messages: list[str] = []
    if obj is None:
        return messages
    comps = getattr(obj, "comprobantes", None) or getattr(obj, "autorizaciones", None)
    if comps is None:
        # Try dict-like
        if isinstance(obj, dict):
            for key in ("mensajes", "comprobantes", "autorizaciones"):
                if key in obj:
                    return _extract_messages(obj[key])
        return messages

    items = getattr(comps, "comprobante", None) or getattr(comps, "autorizacion", None)
    if items is None and hasattr(comps, "__iter__") and not isinstance(comps, str | bytes):
        items = list(comps)
    if items is None:
        items = []
    if not isinstance(items, list):
        items = [items]

    for item in items:
        msgs = getattr(item, "mensajes", None)
        if msgs is None and isinstance(item, dict):
            msgs = item.get("mensajes")
        if msgs is None:
            continue
        mensaje_list = getattr(msgs, "mensaje", None)
        if mensaje_list is None and isinstance(msgs, dict):
            mensaje_list = msgs.get("mensaje")
        if mensaje_list is None:
            continue
        if not isinstance(mensaje_list, list):
            mensaje_list = [mensaje_list]
        for m in mensaje_list:
            ident = getattr(m, "identificador", None) or (
                m.get("identificador") if isinstance(m, dict) else None
            )
            msg = getattr(m, "mensaje", None) or (m.get("mensaje") if isinstance(m, dict) else None)
            info = getattr(m, "informacionAdicional", None) or (
                m.get("informacionAdicional") if isinstance(m, dict) else None
            )
            tipo = getattr(m, "tipo", None) or (m.get("tipo") if isinstance(m, dict) else None)
            parts = [p for p in (tipo, ident, msg, info) if p]
            if parts:
                messages.append(" — ".join(str(p) for p in parts))
    return messages


class SriSoapClient:
    """Thin wrapper around zeep; injectable for tests."""

    def __init__(self, *, ambiente: str = "1", transport: Any | None = None) -> None:
        self.ambiente = str(ambiente)
        self._transport = transport

    def _client(self, wsdl: str) -> Any:
        from zeep import Client
        from zeep.transports import Transport

        transport = self._transport or Transport(timeout=60)
        return Client(wsdl=wsdl, transport=transport)

    def enviar_comprobante(self, signed_xml: str) -> RecepcionResult:
        wsdl = WSDL_RECEPCION.get(self.ambiente, WSDL_RECEPCION["1"])
        client = self._client(wsdl)
        payload = base64.b64encode(signed_xml.encode("utf-8")).decode("ascii")
        response = client.service.validarComprobante(payload)
        estado = str(getattr(response, "estado", "") or "")
        return RecepcionResult(estado=estado, messages=_extract_messages(response), raw=response)

    def autorizar_comprobante(self, access_key: str) -> AutorizacionResult:
        wsdl = WSDL_AUTORIZACION.get(self.ambiente, WSDL_AUTORIZACION["1"])
        client = self._client(wsdl)
        response = client.service.autorizacionComprobante(access_key)
        autorizaciones = getattr(response, "autorizaciones", None)
        auth = None
        if autorizaciones is not None:
            auth = getattr(autorizaciones, "autorizacion", None)
            if isinstance(auth, list):
                auth = auth[0] if auth else None
        if auth is None and isinstance(response, dict):
            auths = response.get("autorizaciones") or {}
            auth = auths.get("autorizacion")
            if isinstance(auth, list):
                auth = auth[0] if auth else None

        estado = ""
        numero = None
        fecha = None
        xml = None
        if auth is not None:
            estado = str(getattr(auth, "estado", "") or (auth.get("estado") if isinstance(auth, dict) else "") or "")
            numero = getattr(auth, "numeroAutorizacion", None) or (
                auth.get("numeroAutorizacion") if isinstance(auth, dict) else None
            )
            fecha = getattr(auth, "fechaAutorizacion", None) or (
                auth.get("fechaAutorizacion") if isinstance(auth, dict) else None
            )
            if fecha is not None:
                fecha = str(fecha)
            xml = getattr(auth, "comprobante", None) or (
                auth.get("comprobante") if isinstance(auth, dict) else None
            )
            if isinstance(xml, bytes):
                xml = xml.decode("utf-8", errors="replace")

        messages = _extract_messages(response)
        if auth is not None:
            messages.extend(_extract_messages(auth))

        return AutorizacionResult(
            estado=estado or "DESCONOCIDO",
            numero_autorizacion=str(numero) if numero else None,
            fecha_autorizacion=fecha,
            comprobante_xml=xml,
            messages=messages,
            raw=response,
        )
