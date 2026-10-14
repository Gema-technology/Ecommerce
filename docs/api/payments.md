# API — Payments

Payment Core is provider-agnostic.

| Entorno | Provider típico |
|---------|-----------------|
| development / test | `manual` |
| staging / production (Ecuador) | `payphone` |

See also: [PayPhone Ecuador v1](../architecture/payphone-ecuador-v1.md).

## Customer

| Método | Ruta | Auth |
|--------|------|------|
| POST | `/api/v1/orders/{order_id}/payment` | Session |
| GET | `/api/v1/orders/{order_id}/payments` | Session (owner) |
| GET | `/api/v1/payments/{payment_id}` | Session (owner) |
| POST | `/api/v1/payments/{payment_id}/sync` | Session (owner) — PayPhone Sale poll |

`POST /payments/{id}/confirm` for customers was removed. Manual confirm is admin-only and env-gated.

### Create payment

Body (optional):

```json
{ "method": "CARD" }
```

Methods: `CARD`, `BANK_TRANSFER`, `CASH_ON_DELIVERY`.

**Amount and currency always come from `Order.total` / `Order.currency`.** Frontend must not send amount.

Order must be `PENDING_PAYMENT`. `PAID` / `CANCELLED` → `409`.

Response includes `payment_id`, `order_id`, `order_number`, `status`, `amount`, `currency`, `provider`, and optional `client_action`:

| Provider | `client_action.type` | Uso |
|----------|----------------------|-----|
| `manual` | `manual_pending` | Esperar confirm admin/webhook |
| `payphone` | `redirect` + `url` | Abrir link de cobro PayPhone |
| `bank_transfer` | `bank_transfer_instructions` | Mostrar cuenta + referencia (método `BANK_TRANSFER`) |

`BANK_TRANSFER` always uses the offline `bank_transfer` provider (ignores `PAYMENT_DEFAULT_PROVIDER`).  
`CASH_ON_DELIVERY` uses `cash_on_delivery` and requires `users.allow_cash_on_delivery` (admin whitelist).  
Card methods use PayPhone/manual according to `PAYMENT_DEFAULT_PROVIDER`.

Customer: `POST /api/v1/payments/{id}/mark-transferred` (bank transfer only; does not mark paid).  
Admin: `POST /api/v1/admin/payments/{id}/confirm` works for `bank_transfer` and `cash_on_delivery` in all environments.  
Admin whitelist: `PATCH /api/v1/admin/users/{id}/cash-on-delivery`.

## Webhooks (public)

```http
POST /api/v1/payments/webhooks/{provider}
POST /api/v1/payments/webhooks/payphone/NotificacionPago
```

No session cookie. Authenticity is provider-specific.

### Manual provider

Header: `X-GEMA-Payment-Secret: <PAYMENT_WEBHOOK_SECRET>`

```json
{
  "event_id": "unique-event-id",
  "event_type": "payment.succeeded",
  "payment_id": "<uuid>"
}
```

`event_type`: `payment.succeeded` | `payment.failed` (others ignored).

### PayPhone

JSON Notificacion Externa (`ClientTransactionId`, `TransactionId`, `StatusCode`, `Amount`, `StoreId`, …).

Respuesta requerida por PayPhone:

```json
{ "Response": true, "ErrorCode": "000" }
```

Optional auth: `PAYPHONE_WEBHOOK_SECRET` via `?token=` or `X-GEMA-Payment-Secret`.

Idempotency: unique `(provider, provider_event_id)` in `payment_events`.

## Admin

| Método | Ruta |
|--------|------|
| GET | `/api/v1/admin/payments` |
| GET | `/api/v1/admin/payments/{payment_id}` |
| POST | `/api/v1/admin/payments/{payment_id}/confirm?success=` | Solo `manual`, no production |

Roles: `ADMIN`, `SUPER_ADMIN`.

## Success side effects (transactional)

1. `Payment.status = SUCCEEDED`
2. `Order.status = PAID`
3. Reservations → `CONSUMED`
4. Inventory SALE movement (physical stock decreases once)

Failure: `Payment = FAILED`, ACTIVE reservations released for `PENDING_PAYMENT` orders (re-reserved on next payment attempt).
