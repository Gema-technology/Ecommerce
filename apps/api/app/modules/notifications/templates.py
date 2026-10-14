"""Plain-text + HTML email bodies for order lifecycle events."""

from __future__ import annotations

from html import escape
from typing import Any


def _money(order: Any) -> str:
    total = order.total
    currency = getattr(order, "currency", "USD") or "USD"
    return f"{currency} {total}"


def _name(order: Any) -> str:
    name = (getattr(order, "customer_name", None) or "").strip()
    return name or "Cliente"


def build_order_created(order: Any, *, app_url: str) -> tuple[str, str, str]:
    subject = f"Pedido recibido — {order.order_number}"
    name = _name(order)
    total = _money(order)
    link = f"{app_url.rstrip('/')}/orders/{order.order_number}"
    text = (
        f"Hola {name},\n\n"
        f"Recibimos tu pedido {order.order_number}.\n"
        f"Total: {total}\n"
        f"Estado: pendiente de pago.\n\n"
        f"Ver pedido: {link}\n\n"
        f"— GEMA Technology\n"
    )
    html = (
        f"<p>Hola {escape(name)},</p>"
        f"<p>Recibimos tu pedido <strong>{escape(order.order_number)}</strong>.</p>"
        f"<p>Total: <strong>{escape(total)}</strong><br/>Estado: pendiente de pago.</p>"
        f'<p><a href="{escape(link)}">Ver pedido</a></p>'
        f"<p>— GEMA Technology</p>"
    )
    return subject, text, html


def build_order_paid(order: Any, *, app_url: str) -> tuple[str, str, str]:
    subject = f"Pago confirmado — {order.order_number}"
    name = _name(order)
    total = _money(order)
    link = f"{app_url.rstrip('/')}/orders/{order.order_number}"
    text = (
        f"Hola {name},\n\n"
        f"Confirmamos el pago de tu pedido {order.order_number}.\n"
        f"Total: {total}\n"
        f"Pronto prepararemos el envío.\n\n"
        f"Ver pedido: {link}\n\n"
        f"— GEMA Technology\n"
    )
    html = (
        f"<p>Hola {escape(name)},</p>"
        f"<p>Confirmamos el pago de tu pedido "
        f"<strong>{escape(order.order_number)}</strong>.</p>"
        f"<p>Total: <strong>{escape(total)}</strong></p>"
        f"<p>Pronto prepararemos el envío.</p>"
        f'<p><a href="{escape(link)}">Ver pedido</a></p>'
        f"<p>— GEMA Technology</p>"
    )
    return subject, text, html


def build_order_shipped(order: Any, *, app_url: str) -> tuple[str, str, str]:
    subject = f"Pedido enviado — {order.order_number}"
    name = _name(order)
    link = f"{app_url.rstrip('/')}/orders/{order.order_number}"
    text = (
        f"Hola {name},\n\n"
        f"Tu pedido {order.order_number} fue marcado como enviado.\n"
        f"Ver pedido: {link}\n\n"
        f"— GEMA Technology\n"
    )
    html = (
        f"<p>Hola {escape(name)},</p>"
        f"<p>Tu pedido <strong>{escape(order.order_number)}</strong> "
        f"fue marcado como enviado.</p>"
        f'<p><a href="{escape(link)}">Ver pedido</a></p>'
        f"<p>— GEMA Technology</p>"
    )
    return subject, text, html
