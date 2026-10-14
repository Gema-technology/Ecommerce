# Database — Shopping Cart

## Tablas

### `carts`

| Columna | Tipo | Notas |
|---------|------|-------|
| id | UUID PK | |
| user_id | UUID FK → users.id | CASCADE |
| status | VARCHAR(20) | ACTIVE / ABANDONED / CONVERTED |
| created_at / updated_at | timestamptz | |

Índice único parcial: un solo `ACTIVE` por `user_id` (`uq_carts_user_active`).

### `cart_items`

| Columna | Tipo | Notas |
|---------|------|-------|
| id | UUID PK | |
| cart_id | UUID FK → carts.id | CASCADE |
| product_id | UUID FK → products.id | RESTRICT |
| quantity | INTEGER | CHECK > 0 |
| created_at / updated_at | timestamptz | |

Unique: `(cart_id, product_id)`.

**No** almacena price, cost ni margin (precio vigente se resuelve al leer).

## Migración

`006_cart` revisa `005_pricing`.
