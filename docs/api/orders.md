# API — Orders & Checkout

## Checkout

```http
POST /api/v1/checkout
```

Requiere sesión. Body vacío `{}`. El backend:

1. bloquea el carrito ACTIVE del usuario;
2. valida items, productos activos y precio RETAIL vigente;
3. reserva inventario (no descuenta físico);
4. crea `Order` + `OrderItems` con snapshots;
5. marca el carrito como `CONVERTED`;
6. responde `PENDING_PAYMENT`.

Errores: `400` carrito vacío; `409` producto/precio/stock/cart convertido.

## Customer orders

| Método | Ruta |
|--------|------|
| GET | `/api/v1/orders` |
| GET | `/api/v1/orders/{order_id}` |
| GET | `/api/v1/orders/by-number/{order_number}` |

Solo órdenes propias.

## Admin

| Método | Ruta |
|--------|------|
| GET | `/api/v1/admin/orders` |
| GET | `/api/v1/admin/orders/{order_id}` |

Incluye cliente y reservas.

## Precio

Checkout usa **RETAIL vigente** (`map_current_retail_prices`), no el precio promocional del storefront/cart.

## Inventario

Reserva vía `InventoryService.reserve(commit=False)` + fila `inventory_reservations` (`ACTIVE`, `expires_at` + `RESERVATION_TTL_HOURS`). Expiración: `POST /api/v1/internal/reservations/expire` + scheduler externo — ver `docs/architecture/reservation-scheduler-v1.md`.
