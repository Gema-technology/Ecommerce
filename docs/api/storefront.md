# API — Storefront (público)

Consumo exclusivo del storefront MVP. No expone suppliers, costos, márgenes ni movimientos de inventario.

## Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/v1/categories` | Categorías activas |
| GET | `/api/v1/categories/{slug}` | Detalle de categoría |
| GET | `/api/v1/brands` | Marcas activas (`?category=` filtra por afinidad al subárbol) |
| GET | `/api/v1/products` | Listado público paginado |
| GET | `/api/v1/products/{slug}` | Detalle público |

## Query params — marcas

| Param | Descripción |
|-------|-------------|
| `category` | Slug de categoría: marcas cuya afinidad intersecta el subárbol (padre incluye hijos; afinidad en ancestro incluye el nodo filtrado) |

## Query params — productos

| Param | Descripción |
|-------|-------------|
| `search` | Búsqueda textual (nombre, SKU, descripción) |
| `category` | Slug de categoría (incluye descendientes) |
| `brand` | Slug de marca |
| `min_price` / `max_price` | Rango sobre precio público vigente |
| `sort` | `relevance` \| `price_asc` \| `price_desc` \| `name_asc` \| `name_desc` \| `newest` |
| `page` / `page_size` | Paginación |

## Respuesta pública de producto

Incluye:

- brand, category, images, specifications
- `price` — RETAIL vigente o PROMOTIONAL público si aplica
- `availability` — `IN_STOCK` \| `LOW_STOCK` \| `OUT_OF_STOCK` \| `UNKNOWN`

No incluye:

- supplier / supplier cost
- reserved_quantity
- WHOLESALE, cost_reference, margin
- inventory movements

## Ejemplos

```text
GET /api/v1/brands?category=celulares
GET /api/v1/products?category=laptops&brand=asus&min_price=500&max_price=1500&sort=price_asc
GET /api/v1/products?search=asus&sort=relevance
GET /api/v1/products/asus-tuf-gaming-a15
```
