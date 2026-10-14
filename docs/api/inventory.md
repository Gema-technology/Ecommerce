# API — Inventory

Todos los endpoints requieren `ADMIN` o `SUPER_ADMIN`.

## Locations

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/v1/admin/locations` | Listar (crea MAIN si no existe en runtime/dev) |
| POST | `/api/v1/admin/locations` | Crear ubicación |

## Inventory

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/v1/admin/inventory` | Listar (`location_id`, `product_id`) |
| GET | `/api/v1/admin/inventory/low-stock` | `available <= reorder_point` |
| POST | `/api/v1/admin/inventory` | Crear registro (qty=0); stock solo vía movimientos |
| GET | `/api/v1/admin/inventory/{product_id}` | Detalle (`location_id` opcional) |
| PATCH | `/api/v1/admin/inventory/{product_id}` | Solo umbrales reorder |
| GET | `/api/v1/admin/inventory/{product_id}/movements` | Historial paginado |

## Operaciones (explícitas)

| Método | Ruta | Efecto |
|--------|------|--------|
| POST | `.../purchase` | `quantity += n` |
| POST | `.../sale` | `quantity -= n` (≤ available); preparado para orders |
| POST | `.../reserve` | `reserved += n` (≤ available) |
| POST | `.../release` | `reserved -= n` |
| POST | `.../adjust` | body `{ "delta": ±n }` → ADJUSTMENT IN/OUT |
| POST | `.../return` | `quantity += n` |
| POST | `.../damage` | `quantity -= n` |

## Reglas

- Stock **solo** cambia vía movimientos (atómico + `SELECT … FOR UPDATE`)
- `created_by` desde sesión autenticada
- `available_quantity` calculado en response
- CUSTOMER → 403
