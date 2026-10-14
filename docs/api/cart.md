# API — Shopping Cart

Carrito de compra para usuarios autenticados. No reserva inventario ni crea órdenes.

## Endpoints

Todos requieren sesión autenticada (`CurrentUser`). El `user_id` se toma de la sesión; nunca del body.

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/v1/cart` | Obtiene o crea el carrito ACTIVE |
| POST | `/api/v1/cart/items` | Agrega producto (`product_id`, `quantity`) |
| PATCH | `/api/v1/cart/items/{item_id}` | Actualiza cantidad (`quantity`; `0` elimina) |
| DELETE | `/api/v1/cart/items/{item_id}` | Elimina item |
| DELETE | `/api/v1/cart` | Vacía items; mantiene el carrito ACTIVE |

## Reglas

- Máximo un carrito `ACTIVE` por usuario.
- Unique `(cart_id, product_id)`; re-agregar incrementa quantity.
- Solo productos existentes y `is_active=true` al agregar.
- Precio: retail/promotional público actual vía `PricingService` (no acepta price del cliente).
- Totales (`line_total`, `subtotal`) calculados en backend con `Decimal`.
- Agregar al carrito **no** modifica inventory ni reserved.

## Respuesta

Incluye `items[]` con producto (id, name, slug, sku, image, price, is_active, availability), `quantity`, `line_total`, `available`, más `subtotal`, `currency`, `item_count`.

Productos desactivados después de agregarse permanecen visibles con `available: false` y no suman al subtotal.
