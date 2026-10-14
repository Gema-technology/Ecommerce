# Database — Orders

## `orders`

| Campo | Notas |
|-------|-------|
| order_number | único, formato `GEMA-YYYYMMDD-NNNNNN` |
| status | PENDING_PAYMENT, PAID, PROCESSING, SHIPPED, DELIVERED, CANCELLED |
| subtotal/tax/shipping/discount/total | NUMERIC(14,4) |
| cart_id | FK opcional al carrito convertido |

## `order_items`

Snapshots: `product_name_snapshot`, `sku_snapshot`, `unit_price`, `quantity`, `line_total`.

## `order_daily_counters`

Secuencia diaria para `order_number`.

## `inventory_reservations`

| Campo | Notas |
|-------|-------|
| inventory_id / order_id | FKs |
| quantity | > 0 |
| status | ACTIVE, RELEASED, CONSUMED, EXPIRED |
| expires_at | TTL; job `POST /internal/reservations/expire` + scheduler externo |

Migración: `007_orders` ← `006_cart`.
