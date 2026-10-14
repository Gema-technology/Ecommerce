# GEMA Technology — Contra entrega (clientes de confianza) v1

**Fecha:** 2026-10-12

## Política

Contra entrega **no** está disponible para todos. Solo clientes con
`users.allow_cash_on_delivery = true`, activado por un admin en
`/admin/users`.

## Flujo

1. Admin habilita contra entrega para un cliente de confianza.
2. Ese cliente ve la opción en el pago de la orden.
3. Al elegirla, se crea un pago `provider=cash_on_delivery` (sin PayPhone).
4. Tras entregar y cobrar en efectivo, el admin confirma el pago en
   `/admin/payments/{id}`.
5. Orden → `PAID` y se consumen reservas.

Clientes sin el flag reciben **403** si intentan el método por API.

## API

| Método | Ruta | Rol |
|--------|------|-----|
| PATCH | `/api/v1/admin/users/{id}/cash-on-delivery` | Admin |
| POST | `/api/v1/orders/{id}/payment` `{ "method": "CASH_ON_DELIVERY" }` | Cliente trusted |
| POST | `/api/v1/admin/payments/{id}/confirm` | Admin |

## Migración

```bash
cd apps/api
alembic upgrade head   # 017_user_allow_cash_on_delivery
```
