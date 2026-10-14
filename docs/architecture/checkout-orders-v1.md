# GEMA Technology — Checkout & Orders v1.0

## Architecture Audit & Implementation Blueprint

| Campo | Valor |
|-------|-------|
| Estado | Auditoría + blueprint (sin implementación en esta fase) |
| Fecha | 2026-07-28 |
| Alcance | Cart → Checkout → Order → Reservation → Payment (existente) → Shipping / SRI (futuro) |
| Regla | El frontend nunca es fuente de verdad para precios, stock, descuentos o totales |

> **Hallazgo crítico:** Checkout, Orders, OrderItems, InventoryReservation y Payments **ya están implementados** en backend y frontend. Esta fase no parte de cero: documenta el estado real y propone la evolución hacia un checkout comercial completo (dirección, shipping, cancelación, expiración de reservas, alineación de precios).

---

## 1. Current Architecture

### Monorepo

```text
gema-technology/
├── apps/web          # Next.js 16 · React 19 · TypeScript · Tailwind (Premium Light Theme)
├── apps/api          # FastAPI · SQLAlchemy 2 · Alembic · PostgreSQL
└── docs/             # API / database / architecture
```

### Backend — módulos relevantes (`apps/api/app/modules/`)

| Módulo | Responsabilidad |
|--------|-----------------|
| `auth` | Sesión por cookie, deps `CurrentUser` / `RequireAdmin` |
| `roles` / `users` | `User`, `Role`, `UserRole` — no existe entidad `Customer` |
| `catalog` / `products` | Productos, imágenes, disponibilidad pública |
| `pricing` | `ProductPrice` RETAIL / WHOLESALE / PROMOTIONAL |
| `inventory` | `Location`, `Inventory`, movimientos, `InventoryReservation` |
| `cart` | `Cart`, `CartItem` (1 carrito ACTIVE por usuario) |
| `orders` | `Order`, `OrderItem`, `OrderDailyCounter`, schemas de lectura |
| `checkout` | `CheckoutService` + `POST /checkout` (sin body) |
| `payments` | `Payment`, `PaymentEvent`, confirm/webhook → consume reserva |

Patrón típico por módulo: `models` → `schemas` → `repository` → `service` → `router`.

### Frontend — superficies relevantes (`apps/web`)

| Ruta | Rol |
|------|-----|
| `/cart` | Revisión / mutación de carrito |
| `/checkout` | Review + confirm → crea orden |
| `/orders`, `/orders/[order_number]` | Listado y detalle de cliente |
| `/orders/[order_number]/payment` | Inicio de pago |
| `/payment/success`, `/payment/failed` | Resultado de pago |
| `/admin/orders`, `/admin/payments` | Operaciones |

Providers globales: `AuthProvider` → `CartProvider` → `ToastProvider`.

Clientes API: `cart-api.ts`, `orders-api.ts`, `payments-api.ts`, `auth-api.ts`.

### Identidad: usuario vs customer

1. **Usuario autenticado:** cookie de sesión → `GET /auth/me` → `User` (`id`, `email`, nombres, `roles[]`).
2. **Customer:** no hay tabla `customers`. Un “cliente” es un `User` con rol `CUSTOMER` (asignado al registrar).
3. **Cart / Order ownership:** ambos usan `user_id` → `users.id`.
4. **Admin:** roles `ADMIN` | `SUPER_ADMIN` vía `RequireAdmin` / `isAdmin` en web.

---

## 2. Current Cart Flow

```text
AddToCartButton / CartDrawer / CartPage
        ↓
   cartApi.*  (credentials: include)
        ↓
POST/PATCH/DELETE /api/v1/cart...
        ↓
CartService (get_or_create ACTIVE cart)
        ↓
CartRead (precios públicos + availability display)
```

### Modelo

- **`Cart`:** `id`, `user_id`, `status` (`ACTIVE` | `ABANDONED` | `CONVERTED`), timestamps. Índice único parcial: un `ACTIVE` por usuario.
- **`CartItem`:** `cart_id`, `product_id`, `quantity` (> 0), unique `(cart_id, product_id)`.

### Comportamiento actual

| Aspecto | Realidad |
|---------|----------|
| Auth | Obligatoria — no hay carrito guest/session |
| Precio en carrito | `PricingService.map_public_prices` → **PROMOTIONAL si vigente, si no RETAIL** |
| Stock al agregar | **No se valida** — solo se muestra `availability` |
| Ownership | Item solo si `cart.user_id == current_user.id` y cart `ACTIVE` |
| Tras checkout | Cart → `CONVERTED`; el próximo `GET /cart` crea un nuevo ACTIVE |
| `ABANDONED` | Definido, **no usado** en servicios |

### Endpoints

| Método | Path |
|--------|------|
| GET | `/api/v1/cart` |
| POST | `/api/v1/cart/items` |
| PATCH | `/api/v1/cart/items/{item_id}` |
| DELETE | `/api/v1/cart/items/{item_id}` |
| DELETE | `/api/v1/cart` |

---

## 3. Current Inventory Flow

### Modelo de stock

```text
Inventory.quantity              # on-hand
Inventory.reserved_quantity     # holds activos
available = quantity - reserved_quantity
```

Constraints: `quantity >= 0`, `reserved_quantity >= 0`, `reserved_quantity <= quantity`.  
Ubicación por defecto: `Location.code = MAIN`.

### Operaciones (`InventoryService`)

| Método | Efecto |
|--------|--------|
| `purchase` / `return_stock` | ↑ `quantity` |
| `sale` | ↓ `quantity` (requiere available) |
| `reserve` | ↑ `reserved_quantity` (requiere available) |
| `release` | ↓ `reserved_quantity` |
| `consume_for_order` | reservas ACTIVE → CONSUMED; ↓ qty y reserved; movimiento SALE |
| `adjust` / `damage` | ajustes con guards |

Concurrencia: `SELECT … FOR UPDATE` sobre filas de inventario (y cart/order/counter en checkout).

### Reservation (ya existe)

Tabla `inventory_reservations`:

| Campo | Notas |
|-------|-------|
| `inventory_id`, `order_id` | FKs |
| `quantity` | > 0 |
| `status` | `ACTIVE` \| `RELEASED` \| `CONSUMED` \| `EXPIRED` |
| `expires_at` | Checkout setea `now + 24h`; **sin job de expiración** |

Creada en checkout junto con `InventoryService.reserve(..., commit=False)`.  
Consumida en pago exitoso (`PaymentService` → `consume_for_order`).  
Pago fallido: **no libera** reserva (queda `ACTIVE`).

---

## 4. Proposed Order Architecture

### Principio

**Extender** el pipeline existente; no reemplazarlo.

```text
Cart (ACTIVE)
  → Validate cart / products / prices / stock   [backend]
  → Collect customer + shipping info            [frontend → body futuro]
  → Calculate totals                            [backend]
  → Reserve inventory + InventoryReservation    [backend, atómico]
  → Create Order + OrderItems (snapshots)       [backend]
  → Cart CONVERTED
  → PENDING_PAYMENT
  → Payment success → PAID + consume reservation
  → PROCESSING → SHIPPED → DELIVERED            [admin / futuro]
  → CANCELLED → release reservation             [faltante]
```

### Decisiones alineadas al código actual

| Propuesta del brief | Decisión |
|---------------------|----------|
| `customer_id` | Mantener `user_id` (User = customer). Introducir `Customer` solo si aparece perfil comercial (RUC, direcciones múltiples). |
| Status `PENDING` | Mantener **`PENDING_PAYMENT`** (ya acoplado a payments/UI/tests). Alias semántico: “pendiente de pago”. |
| `CONFIRMED` | Equivalente operativo: **`PAID`**. |
| `shipping_address` / `customer_notes` | **Implementados** (§21): JSON + texto en `orders`; body obligatorio en checkout. |
| Snapshots | Ya existen name/sku/unit_price/`line_discount`; ampliar con `specifications_snapshot` JSON opcional (fase futura). |
| Precio checkout | **Resuelto (Commerce Core Hardening Phase 1 — Pricing Consistency):** ver §19. |

---

## 5. Entity Model

```text
User (CUSTOMER)
  ├── 1..* Cart (ACTIVE | CONVERTED | ABANDONED)
  │         └── 1..* CartItem → Product
  └── 1..* Order
            ├── 1..* OrderItem → Product (+ snapshots)
            ├── 0..* InventoryReservation → Inventory
            └── 0..* Payment → PaymentEvent

Product
  ├── 0..* ProductPrice
  └── 0..* Inventory (por Location)
            └── 0..* InventoryMovement
```

### Order (actual + extensión propuesta)

| Campo | Estado |
|-------|--------|
| `id`, `order_number`, `user_id`, `status`, `currency` | Existe |
| `subtotal`, `tax_total`, `shipping_total`, `discount_total`, `total` | Existe (tax/shipping/discount = 0 hoy) |
| `cart_id` | Existe |
| `created_at`, `updated_at` | Existe |
| `shipping_address` (JSON estructurado) | **Existe** (§21) |
| `customer_notes` | **Existe** (§21) |
| `billing_address` | Futuro (SRI / factura) |

### OrderItem (actual + extensión)

| Campo | Estado |
|-------|--------|
| `product_id`, `product_name_snapshot`, `sku_snapshot` | Existe |
| `unit_price`, `quantity`, `line_total` | Existe |
| `line_discount` | Existe (migración `010_pricing_consistency`) |
| `specifications_snapshot` (JSONB) | **Propuesto** |
| `price_type_snapshot` (RETAIL/PROMOTIONAL) | **Propuesto** (trazabilidad) |

---

## 6. Database Model

### Tablas existentes (migraciones)

| Migración | Tablas |
|-----------|--------|
| `006_cart` | `carts`, `cart_items` |
| `004_inventory` | `locations`, `inventory`, `inventory_movements` |
| `005_pricing` | `product_prices` |
| `007_orders` | `order_daily_counters`, `orders`, `order_items`, `inventory_reservations` |
| `008_payments` | `payments`, `payment_events` |
| `010_pricing_consistency` | `cart_items.quoted_unit_price`, `order_items.line_discount` |

### Extensiones futuras (no generar ahora)

```text
orders
  + shipping_address_json / shipping_* columns
  + customer_notes
  + (opcional) reserved_until  -- denormalizado desde reservations

order_items
  + specifications_snapshot JSONB NULL
  + price_type_snapshot VARCHAR NULL

-- Sin nueva tabla Customer en v1.1 salvo requisito fiscal/RUC
```

`order_number`: formato `GEMA-YYYYMMDD-NNNNNN` vía `OrderDailyCounter` + `FOR UPDATE`.

---

## 7. Order State Machine

### Estados actuales (`OrderStatus`)

```text
PENDING_PAYMENT ──payment success──► PAID ──► PROCESSING ──► SHIPPED ──► DELIVERED
       │                               │
       │                               └── (futuro cancel parcial? no)
       └── cancel / expire ──────────► CANCELLED
```

### Transiciones válidas propuestas

| Desde | Hacia | Actor | Efecto inventario |
|-------|-------|-------|-------------------|
| `PENDING_PAYMENT` | `PAID` | Payment success | `consume_for_order` |
| `PENDING_PAYMENT` | `CANCELLED` | Customer/Admin/expiry job | `release` + reservation `RELEASED`/`EXPIRED` |
| `PAID` | `PROCESSING` | Admin | — |
| `PROCESSING` | `SHIPPED` | Admin | — |
| `SHIPPED` | `DELIVERED` | Admin | — |
| `PAID` / `PROCESSING` | `CANCELLED` | Admin (política) | Return stock / crédito — **definir política** |

**Hoy implementado en servicios:** solo `PENDING_PAYMENT` → `PAID`.  
El resto de estados existe en enum/UI labels pero **sin API de transición**.

### Mapeo vs brief original

| Brief | Equivalente GEMA |
|-------|------------------|
| PENDING | `PENDING_PAYMENT` |
| CONFIRMED | `PAID` |
| PROCESSING / SHIPPED / DELIVERED / CANCELLED | Igual |

---

## 8. Inventory Reservation Strategy

### Estrategia actual (mantener)

```text
available_stock = quantity - reserved_quantity
```

1. Checkout: lock inventory → `reserve` (↑ reserved) → fila `InventoryReservation(ACTIVE, expires_at)`.
2. Payment success: `consume_for_order` (↓ quantity & reserved, status `CONSUMED`).
3. Overselling prevenido por `available` + `FOR UPDATE` (tests de concurrencia existen).

### Gaps a cerrar (fases posteriores)

| Capacidad | Estado |
|-----------|--------|
| Expiración automática (`expires_at`) | Campo existe; **falta job/cron** |
| Release en pago fallido | **No** |
| Cancelación de orden PENDING | **No** |
| Marcar reservation `EXPIRED` + `release` | **No** |
| Admin `release` vs filas reservation | Movimiento existe; no siempre alinea filas de reservation |

### Reglas de diseño futuras

- Una reserva ACTIVE por (order, inventory line) en checkout.
- Expiración: job periódico `WHERE status=ACTIVE AND expires_at < now()` → `release` + status `EXPIRED` + order `CANCELLED` (si aún `PENDING_PAYMENT`).
- Nunca confiar en el frontend para “hay stock”.
- Opcional: soft-check de stock al `add_item` (409) sin reservar hasta checkout.

---

## 9. Checkout Flow

### Flujo actual (implementado)

```text
GET /cart (UI)
  → usuario revisa líneas / subtotal (precio público)
  → POST /api/v1/checkout   [sin body]
       1. Lock ACTIVE cart
       2. Validate non-empty
       3. Resolve RETAIL prices only
       4. Validate product active + price exists
       5. Allocate order_number
       6. Create Order PENDING_PAYMENT + OrderItems snapshots
       7. Reserve inventory + InventoryReservation (24h)
       8. Cart → CONVERTED
       9. commit (rollback total si falla)
  → redirect /orders/{order_number}
  → (opcional) /payment
```

### Responsabilidades

| Capa | Debe hacer | No debe hacer |
|------|------------|---------------|
| **Frontend** | Auth gate, UX review, mostrar errores 409, navegar a orden/pago, formularios futuros de dirección | Enviar precios/totales como verdad; inventar stock; mutar product_id de items ajenos |
| **Backend** | Validar cart ownership, precios, stock, totales, reservas, número de orden, snapshots | Confiar en `unit_price`/`total` del cliente |

### Flujo objetivo v1.1 (evolución)

```text
Cart → Validate → Collect shipping/notes → Quote totals
  → Reserve → Create order → Confirmation → Payment
```

Body propuesto (futuro):

```json
{
  "shipping_address": { "...": "..." },
  "customer_notes": "opcional",
  "accept_price_changes": true
}
```

Totales siempre recalculados en servidor.

---

## 10. API Design

### Existente (fuente de verdad)

| Método | Path | Notas |
|--------|------|-------|
| POST | `/api/v1/checkout` | Crea orden + reserva; sin body |
| GET | `/api/v1/orders` | Lista propia |
| GET | `/api/v1/orders/{id}` | Detalle propio |
| GET | `/api/v1/orders/by-number/{order_number}` | Detalle propio |
| GET | `/api/v1/admin/orders` | Admin |
| GET | `/api/v1/admin/orders/{id}` | Incluye customer + reservations |
| POST | `/api/v1/orders/{id}/payment` | Inicia pago |
| POST | `/api/v1/payments/{id}/confirm` | Confirmación manual |
| POST | `/api/v1/payments/webhooks/{provider}` | Webhook |

### Endpoints propuestos (no implementar en esta fase)

| Método | Path | Propósito |
|--------|------|-----------|
| POST | `/api/v1/checkout` | Extender con body (address/notes); misma semántica |
| POST | `/api/v1/orders/{id}/cancel` | Solo `PENDING_PAYMENT` + release stock |
| PATCH | `/api/v1/admin/orders/{id}/status` | Transiciones PROCESSING→… |
| POST | `/api/v1/internal/reservations/expire` | Job/cron protegido |

Contrato de error recomendado (ya informalmente usado):

| Código | Casos |
|--------|-------|
| 400 | Carrito vacío / inválido |
| 401 | No autenticado |
| 403 | Admin only |
| 404 | Orden ajena (como not found) |
| 409 | Stock, precio, producto inactivo, conflicto |

---

## 11. Frontend Architecture

### Estado actual

- **Checkout:** `app/checkout/page.tsx` — review + `ordersApi.checkout()`; no wizard; copy de “pago posterior” desactualizado.
- **Cart state:** `CartProvider` + fetches locales duplicados en `CartPage`/`CheckoutPage`.
- **Órdenes/pago:** páginas customer + admin; payment method select (`CARD` / `BANK_TRANSFER` / `CASH_ON_DELIVERY`).
- **Design System:** Light Theme; usar `btn-*`, `gema-panel`, `input-field`, `Drawer`, `StoreShell`.

### Integración sin duplicar

1. Reutilizar `ordersApi.checkout()` — no crear segundo path de creación.
2. Extraer UI compartida: líneas de carrito (`CartPage`/`CartDrawer`), resumen de orden (`OrderDetail`/`Payment`), helper `money()`/`formatPrice`.
3. Preferir `useCart().cart` + `refresh()` en checkout para evitar drift.
4. Nuevos formularios de shipping: componentes bajo `components/checkout/` consumiendo el mismo layout `StoreShell` + tokens.
5. Tras confirm: opcional redirect directo a `/orders/.../payment`.
6. Usar `EmptyState` / `Button` / `useToast` en lugar de paneles ad-hoc nuevos.

### Flujo UI objetivo

```text
/cart → /checkout (review + address) → confirm
  → /orders/{number} → /payment → success|failed
```

---

## 12. Security Rules

| Regla | Estado / acción |
|-------|-----------------|
| Ownership de carrito | Enforce `user_id` en todos los cart ops |
| Ownership de órdenes | Lectura solo propia; admin vía `/admin` |
| Precios | Solo backend (`PricingRepository`); ignorar precios del cliente |
| Cantidades | Validar `> 0` y stock available en checkout |
| `product_id` | Solo desde cart items del usuario; no aceptar lista libre de productos en checkout (hoy correcto) |
| Totales | Recalcular siempre en servidor |
| Cross-user IDOR | Responder 404 (patrón actual) |
| RBAC | Customer checkout/orders; Admin list/status |
| CSRF / sesión | Cookie session `credentials: include` — mantener same-site policies |
| Guest checkout | No soportado; requeriría diseño de ownership explícito |

> **Inconsistencia de seguridad/UX:** el carrito muestra precio promocional pero checkout cobra RETAIL → el usuario puede ver un total distinto al confirmado. Debe unificarse o advertirse explícitamente.

---

## 13. Transaction Boundaries

### Checkout (actual — correcto mantener)

```text
BEGIN (implícito en Session)
  FOR UPDATE cart ACTIVE
  resolve prices
  next_order_number (FOR UPDATE counter)
  INSERT order + items
  FOR UPDATE inventory → reserve (commit=False)
  INSERT inventory_reservations
  cart.status = CONVERTED
COMMIT
ON ANY ERROR → ROLLBACK (CheckoutService.checkout try/except)
```

### Payment success (actual)

```text
lock payment/order
  status → PAID
  consume_for_order (reservations ACTIVE → CONSUMED)
COMMIT
```

### Cancel / expire (propuesto)

```text
FOR UPDATE order (PENDING_PAYMENT)
  FOR UPDATE inventory rows
  release reserved_quantity
  reservation.status = RELEASED|EXPIRED
  order.status = CANCELLED
COMMIT
```

`get_db` no auto-commit: los services son dueños de `commit`/`rollback`.

---

## 14. Error Handling

### Backend

- Dominio: `HTTPException` + `detail` string (sin capa DomainError compartida salvo `AIError`).
- Códigos: 400 / 401 / 403 / 404 / 409 / 422.
- Checkout: conflictos de stock/precio/producto → **409**.

### Frontend

- `ApiError` desde `auth-api` / fetch helpers.
- Patrón: `err instanceof ApiError ? err.message : fallback`.
- `role="alert"` en checkout/cart; Toast global montado pero poco usado en este flujo.

### Mejoras propuestas

- Códigos de error estables (`CART_EMPTY`, `INSUFFICIENT_STOCK`, `PRICE_UNAVAILABLE`) para UI i18n.
- Distinguir “precio cambió” vs “sin precio” cuando se unifique pricing.

---

## 15. Testing Strategy

### Cobertura existente (mantener)

| Suite | Qué valida |
|-------|------------|
| `apps/api/tests/test_cart.py` | CRUD, ownership, pricing display, no mutate inventory on add |
| `apps/api/tests/test_inventory.py` | reserve/release, concurrency, RBAC |
| `apps/api/tests/test_orders_checkout.py` | checkout feliz, empty, inactive, no price, stock, oversell, ownership, admin |
| `apps/api/tests/test_payments.py` | success consume once, failure keeps reservation, webhooks, idempotency |
| `apps/web/src/__tests__/cart.test.tsx` | UI carrito / add |
| `apps/web/src/__tests__/orders.test.tsx` | checkout redirect / 409 |
| `apps/web/src/__tests__/payments.test.tsx` | flujo de pago |

### Añadir en fases futuras

- Cancel + release stock.
- Expiry job.
- Checkout con address body + snapshots extendidos.
- Alineación cart price == checkout price.
- Frontend: `CartDrawer`, redirect post-checkout a payment, formularios shipping.

---

## 16. Implementation Phases

| Fase | Objetivo | Implementar código? |
|------|----------|---------------------|
| **0 — Audit** | Documento blueprint | Hecho (solo docs) |
| **1 — Pricing Consistency** | Unificar pricing cart/checkout; quotes; `PRICE_CHANGED`; snapshots de precio | **Hecho** (§19) |
| **1b / 2 — Inventory Reservation Lifecycle** | Release on payment fail; cancel PENDING; expiry job; re-reserve on retry | **Hecho** (§20) |
| **2 — Checkout comercial** | Address + notes; persistir en Order; UX fail/cancel/expire | **Hecho** (§21) |
| **3 — Fulfillment** | Admin status transitions PROCESSING→DELIVERED | Sí |
| **4 — Snapshots ricos** | specifications / price_type en OrderItem | Sí |
| **5 — Shipping engine** | `shipping_total` real, métodos, zonas EC | Sí |
| **6 — Fiscal / SRI** | Invoice, RUC, billing — fuera de v1 | Más adelante |
| **Payments** | Ya existe core; providers reales (Pasarela EC) | Incremental |

---

## 17. Risks

| Riesgo | Impacto | Mitigación |
|--------|---------|------------|
| Precio carrito ≠ checkout | Desconfianza / abandono | Una sola función de precio público en ambos |
| Reservas huérfanas tras pago fallido | Stock fantasma | Release on fail + expiry job |
| Sin cancelación | Usuarios atrapados en PENDING | Endpoint cancel + UI |
| Estados SHIPPED/DELIVERED sin API | Admin manual inconsistente | Transiciones admin versionadas |
| Duplicación UI cart/checkout | Bugs de sync | Extraer componentes + usar CartProvider |
| Guest checkout futuro | Reescritura ownership | No improvisar; diseño explícito |
| Over-engineering Customer entity | Complejidad | Mantener User hasta necesidad fiscal |

---

## 18. Open Questions

1. **¿Checkout debe usar precio público (promo) o siempre RETAIL?** Hoy diverge.
2. **¿TTL de reserva 24h es correcto para Ecuador / COD?**
3. **¿Pago fallido libera stock inmediatamente o espera expiry?**
4. **¿El cliente puede cancelar `PENDING_PAYMENT` desde la UI?**
5. **¿Se necesita dirección de envío antes del MVP de pasarela, o basta notas libres?**
6. **¿`shipping_total` / `tax_total` se calculan en checkout o post-pago?**
7. **¿Moneda solo USD o multi-currency (USD/EUR/…) para EC?**
8. **¿Se introduce entidad `Customer` + direcciones guardadas, o campos en Order bastan?**
9. **Política de cancelación post-`PAID`:** ¿restock automático o solo admin?
10. **¿Validar stock al agregar al carrito (soft) además del checkout (hard)?**

---

## Resumen de hallazgos

### Lo que ya funciona

- Pipeline **Cart → Checkout → Order + OrderItem (snapshots) → InventoryReservation → Payment → consume stock**.
- Concurrencia de inventario con `FOR UPDATE` y tests de overselling.
- Ownership por `user_id` (User con rol CUSTOMER).
- Frontend capaz de crear órdenes reales y pagar (provider manual).
- Admin de órdenes/pagos con visibilidad de reservas.
- **Pricing Consistency (Phase 1):** fuente única `resolve_effective_price` / `map_effective_prices`; quotes; `PRICE_CHANGED`; UI de sync.

### Gaps prioritarios restantes

1. ~~Unificar pricing carrito vs checkout.~~ **Hecho** (§19).
2. ~~Release / expiry de reservas.~~ **Hecho** (§20).
3. ~~Cancelación de órdenes `PENDING_PAYMENT`.~~ **Hecho** (§20).
4. Datos de **envío / notas** en Order + UI de checkout.
5. **Transiciones de fulfillment** (PROCESSING→DELIVERED).
6. Snapshots más ricos (`specifications_snapshot` / `price_type_snapshot`) y totales tax/shipping.

### Principio de evolución

> Extender el checkout atómico existente. No reinventar Order ni Reservation. Cerrar gaps de stock fantasma antes de añadir SRI o shipping complejo.

---

## 19. Commerce Core Hardening Phase 1 — Pricing Consistency

| Campo | Valor |
|-------|-------|
| Estado | **Implementado** |
| Fecha | 2026-07-28 / verificado 2026-07-29 |
| Alcance | Una sola resolución de precio; cart = checkout; detección `PRICE_CHANGED`; snapshots de precio |

### Estrategia de precios (source of truth)

```text
PricingService.map_effective_prices / resolve_effective_price
        │
        ├── PROMOTIONAL activo (starts_at ≤ now < ends_at)  → gana
        └── RETAIL activo                                       → fallback
```

- **Ubicación:** `apps/api/app/modules/pricing/service.py`
- **Consumidores:** `CartService` (add/update/read/sync) y `CheckoutService` (validación + totales de orden).
- **Frontend:** nunca envía `price` / `subtotal` / `total`. Solo `product_id` + `quantity` (cart) o `POST /checkout` sin body.

### Flujo actualizado

```text
Add/Update cart item
  → resolve_effective_price
  → persist cart_items.quoted_unit_price
  → CartRead muestra precio efectivo (+ flag price_changed si diverge)

Checkout
  → map_effective_prices (mismas reglas)
  → si quoted ≠ current → 409 PRICE_CHANGED (antes de reservar stock)
  → crear Order + OrderItem snapshots (unit_price, line_discount, name, sku)
  → inventory.reserve
  → cart → CONVERTED
```

Orden de garantías: **precio → stock → reserva → orden persistida** (el bloqueo de precio ocurre antes de cualquier reserva).

### Cotización y sync

| Pieza | Rol |
|-------|-----|
| `cart_items.quoted_unit_price` | Precio mostrado/comprometido al agregar o al sync |
| `POST /api/v1/cart/sync-prices` | Refresca quotes al precio efectivo actual |
| `CartItemRead.price_changed` / `CartRead.has_price_changes` | Aviso suave en GET cart |
| Checkout `409` | Bloqueo duro si el cliente intenta pagar con quote desactualizado |

### Error `PRICE_CHANGED`

```json
{
  "detail": {
    "code": "PRICE_CHANGED",
    "message": "One or more product prices have changed. Refresh your cart to continue.",
    "items": [
      {
        "product_id": "<uuid>",
        "product_name": "...",
        "previous_unit_price": "999.0000",
        "current_unit_price": "1099.0000",
        "currency": "USD"
      }
    ]
  }
}
```

Frontend (`/checkout`): alerta “Precio actualizado”, antes/ahora, CTA **Actualizar carrito** → `syncPrices()`.

### Decisiones

1. Una sola función de resolución; no `cart_price` / `checkout_price` separados.
2. PROMOTIONAL vigente tiene prioridad sobre RETAIL; promo expirada cae a RETAIL.
3. El cliente no es fuente de verdad; campos de precio en body se ignoran (schema `CartItemCreate`).
4. `line_discount` en `order_items` captura descuento unitario × cantidad al momento del checkout.
5. Specs / `price_type` en snapshot quedan para una fase posterior (no bloquean consistencia de precio).

### Migración

- `010_pricing_consistency`: `cart_items.quoted_unit_price`, `order_items.line_discount`.

### Tests

| Caso | Archivo |
|------|---------|
| Cart price = Checkout (retail) | `tests/test_pricing_consistency.py` |
| Promo activa $999 | idem |
| Promo expirada → retail | idem |
| `PRICE_CHANGED` 409 | idem + `test_orders_checkout.py` |
| Snapshot estable tras cambio de catálogo | idem |
| Precio manipulado desde cliente ignorado | `test_add_to_cart_ignores_client_supplied_prices` |
| UX checkout + sync | `apps/web/src/__tests__/orders.test.tsx` |

---

*Pricing Consistency implementado. Inventory Reservation Lifecycle implementado (§20). Checkout comercial + UX pago (§21).*

---

## 20. Inventory Reservation Lifecycle

| Campo | Valor |
|-------|-------|
| Estado | **Implementado** |
| Fecha | 2026-07-29 |
| Alcance | Confirm/release/expire/cancel idempotentes; TTL configurable; job HTTP interno |

### Estados de reserva (reutilizados)

```text
ACTIVE
  ├── Payment success → CONSUMED   (consume_for_order; ≈ “CONFIRMED”)
  ├── Payment fail / cancel → RELEASED
  └── TTL job → EXPIRED (+ order CANCELLED si PENDING_PAYMENT)
```

No se renombró `CONSUMED` a `CONFIRMED`: el enum y los movimientos `SALE` ya estaban acoplados a payments/tests.

### Flujo

```text
Checkout (txn + FOR UPDATE)
  → reserve stock + InventoryReservation(ACTIVE, expires_at = now + RESERVATION_TTL_HOURS)
  → Order PENDING_PAYMENT

Payment success (txn)
  → Order PAID + consume_for_order → CONSUMED

Payment failure (txn)
  → Payment FAILED
  → release_for_order → RELEASED (stock disponible)
  → Order permanece PENDING_PAYMENT
  → Siguiente create payment: ensure_active_holds_for_order (re-reserva)

Cancel (customer/admin)
  → Order CANCELLED + RELEASED (idempotente a nivel stock; 2º cancel → 409)

Expire job POST /api/v1/internal/reservations/expire
  → Header X-GEMA-Internal-Secret
  → ACTIVE ∧ expires_at ≤ now → EXPIRED
  → PENDING_PAYMENT → CANCELLED
  → Órdenes PAID se omiten (no liberar stock vendido)
```

### Transacciones y concurrencia

- `release_for_order` / `consume_for_order` / checkout / cancel / expire usan `SELECT … FOR UPDATE` sobre filas de reserva e inventario.
- `commit=False` permite componer con payment/order en una sola transacción.
- Doble release / doble consume: no-op si no hay filas `ACTIVE`.
- Rollback: errores durante release/consume abortan el txn (payment confirm / cancel envuelven `rollback`).

### Configuración

| Setting | Default | Uso |
|---------|---------|-----|
| `RESERVATION_TTL_HOURS` | 24 | `expires_at` en checkout y re-reserva |
| `INTERNAL_JOB_SECRET` | `dev-internal-job-secret` | Auth del endpoint de expiración |
| `RESERVATION_EXPIRE_INTERVAL_SECONDS` | 300 | Periodo del scheduler externo |
| `RESERVATION_EXPIRE_ENABLED` | true | Habilita caller/loop externo |
| `API_ORIGIN` | `http://localhost:8000` | Base URL para el caller HTTP |

### Endpoints nuevos

| Método | Ruta | Notas |
|--------|------|-------|
| POST | `/api/v1/orders/{id}/cancel` | Owner, solo `PENDING_PAYMENT` |
| POST | `/api/v1/admin/orders/{id}/cancel` | Admin |
| POST | `/api/v1/internal/reservations/expire` | Cron / scheduler externo |

### Tests

| Caso | Archivo |
|------|---------|
| Reserva creada / confirmada / liberada / expirada / cancel | `tests/test_reservation_lifecycle.py` |
| Doble release / doble consume / rollback / oversell | idem |
| Pago fail libera + retry re-reserva | idem + `test_payments.py` |
| Multi-attempt then success | `test_payments.py` |

### Decisiones

1. **Confirm = `CONSUMED`**, no nuevo estado.
2. **Pago fallido libera stock** pero **no cancela** la orden → permite reintentos con re-reserva.
3. **Expiración** cancela la orden (no reintentable sin nuevo checkout).
4. Sin Celery: endpoint HTTP + caller externo conectado (`app.scripts.expire_reservations`, Compose profile `scheduler`). Ver `docs/architecture/reservation-scheduler-v1.md`.

---

## 21. Checkout comercial + UX pago (fail / cancel / expire)

| Campo | Valor |
|-------|-------|
| Estado | **Implementado** |
| Fecha | 2026-07-29 |
| Alcance | Dirección de entrega + notas en checkout; persistencia en Order; copy UX para fallos, cancelación y expiración |

### Backend

- Migración `011_order_shipping_notes`: `orders.shipping_address` (JSON/JSONB), `orders.customer_notes` (Text).
- `POST /api/v1/checkout` requiere body `CheckoutRequest`:
  - `shipping_address`: recipient, phone, address_line, city, province, country (+ reference / postal_code opcionales)
  - `customer_notes` opcional (máx. 1000)
- `OrderRead` / `CheckoutResponse` exponen `shipping_address`, `customer_notes`, `reserved_until` (mín. `expires_at` de reservas ACTIVE).

### Frontend

| Pantalla | Comportamiento |
|----------|----------------|
| `/checkout` | Formulario EC (dirección + notas) → checkout con body |
| `/orders/[n]` | Bloque entrega; banner TTL; cancelar; banner reserva expirada |
| `/orders/[n]/payment` | Banner TTL; mensaje claro si CANCELLED / EXPIRED; copy re-reserva |
| `/payment/failed` | Stock liberado + reintento re-reserva; link a orden/cancelar |
| Admin orden | Dirección, notas, cancel admin |

### Decisiones

1. Dirección **obligatoria** en checkout (no guest / pickup en esta fase).
2. Fallo de pago ≠ cancelación: la orden sigue `PENDING_PAYMENT`.
3. Expiración / cancel explícito → mensaje distinto en detalle y pago; no se puede pagar de nuevo.
4. Motor de envío / `shipping_total` real queda para fase Shipping engine.

### Tests

| Caso | Archivo |
|------|---------|
| Checkout persiste address/notes | `tests/test_orders_checkout.py` |
| Body requerido en checkout | idem + payments / pricing / reservation |
| UX formulario + detalle + cancel | `apps/web/src/__tests__/orders.test.tsx` |

---

## Checkout Comercial v1 (2026-09-01)

| Campo | Valor |
|-------|-------|
| Estado | **Implementado** |
| Alcance | Wizard premium, shipping MVP, totals backend, preview, customer snapshot |

### Flujo

```text
Cart → Checkout wizard (Datos → Envío → Revisión) → POST /checkout → /orders/{n}/payment
```

### Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/api/v1/checkout/preview` | Estima subtotal, envío, impuestos y total (sin crear orden) |
| POST | `/api/v1/checkout` | Crea orden + reservas (sin cambios de contrato base) |

**Preview request:** `{ "shipping_address": ShippingAddress | null }`  
**Preview response:** `subtotal`, `discount_total`, `shipping_total`, `tax_total`, `total`, `shipping_method`, `tax_enabled`, `items[]`

### Totales (backend — única fuente de verdad)

```text
merchandise = subtotal - discount_total
shipping    = calculate_shipping(merchandise, province)
tax         = calculate_tax(merchandise)   # deshabilitado por defecto
total       = merchandise + shipping + tax
```

Módulo: `apps/api/app/modules/commerce/` (`shipping.py`, `tax.py`, `totals.py`)

### Shipping MVP (configurable vía env)

| Variable | Default | Descripción |
|----------|---------|-------------|
| `SHIPPING_ENABLED` | `true` | Activa cálculo |
| `SHIPPING_FLAT_RATE` | `5.00` | Tarifa estándar USD |
| `SHIPPING_FREE_THRESHOLD` | `100.00` | Envío gratis si merchandise ≥ umbral |
| `SHIPPING_PROVINCE_RATES` | `""` | JSON opcional por provincia |

### Tax

| Variable | Default | Notas |
|----------|---------|-------|
| `COMMERCE_TAX_ENABLED` | `false` | IVA Ecuador pendiente de reglas fiscales |
| `COMMERCE_TAX_RATE` | `0.15` | Solo aplica si enabled |

### Customer snapshot (migración `013_order_customer_snapshot`)

Campos en `orders`: `customer_email`, `customer_name`, `customer_phone` — congelados al crear la orden.

### Frontend

| Pantalla | Cambios |
|----------|---------|
| `/checkout` | Wizard 4 pasos (Datos → Envío → Revisión → Pago); resumen con preview; redirect directo a pago |
| `/orders/[n]` | Desglose subtotal/envío/impuestos; modal cancelación |
| Componentes | `CheckoutSummary`, `OrderTotalsBreakdown`, `ConfirmCancelDialog` |

### Cancelación y retry

- `POST /api/v1/orders/{id}/cancel` — solo `PENDING_PAYMENT` (sin cambios)
- Pago fallido → `/payment/failed` con reintento (flujo existente)
- Reserva expirada → mensajes en orden y pago (backend `reserved_until`)

### Tests

| Suite | Casos nuevos |
|-------|--------------|
| `test_checkout_commercial.py` | preview, shipping, tax, phone/address validation, snapshot |
| `orders.test.tsx` | wizard 4 pasos, preview mock, redirect a payment |

### Pendiente post-v1

- Motor de envío avanzado (zonas, transportistas, peso)
- IVA / SRI Ecuador
- Pasarela de pago real
- Email transaccional
- Guest checkout