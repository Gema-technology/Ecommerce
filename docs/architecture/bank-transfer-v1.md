# GEMA Technology — Transferencia bancaria offline v1

**Fecha:** 2026-10-12

## Flujo

1. Cliente elige **Transferencia bancaria** en el pago de la orden.
2. API crea un pago `provider=bank_transfer` (no usa PayPhone).
3. Se muestran banco, cuenta, titular, monto y referencia (`order_number`).
4. Cliente transfiere y pulsa **Ya transferí** (`POST /payments/{id}/mark-transferred`).
5. Admin verifica el depósito y confirma en `/admin/payments/{id}` (`POST .../confirm`).
6. Orden → `PAID`, reservas consumidas.

## Configuración (`.env`)

```env
BANK_NAME=Banco Pichincha
BANK_ACCOUNT_TYPE=Ahorros
BANK_ACCOUNT_NUMBER=...
BANK_ACCOUNT_HOLDER=GEMA Technology
BANK_ACCOUNT_ID=          # CI o RUC del titular
BANK_TRANSFER_INSTRUCTIONS=Usa el número de orden como referencia.
```

Sin `BANK_NAME` + `BANK_ACCOUNT_NUMBER` + `BANK_ACCOUNT_HOLDER`, el método responde **503**.

## Notas

- `CARD` sigue usando `PAYMENT_DEFAULT_PROVIDER` (PayPhone/manual).
- Confirm admin de `bank_transfer` está permitido en **production** (a diferencia de `manual`).
- No se suben comprobantes en esta versión; el operador valida en el banco.
