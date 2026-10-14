# API — Product Catalog

## Público

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/v1/categories` | Categorías activas |
| GET | `/api/v1/categories/{slug}` | Detalle |
| GET | `/api/v1/brands` | Marcas activas. Query opcional `category={slug}`: solo marcas con afinidad al subárbol (incluye ancestros de afinidad) |
| GET | `/api/v1/brands/{slug}` | Detalle (`category_ids`) |
| GET | `/api/v1/products` | Productos activos (`search`, `category`, `brand`, `min_price`, `max_price`, `sort`, `page`, `page_size`) |
| GET | `/api/v1/products/{slug}` | Detalle con brand, category, specs, images, `price`, `availability` |

Ver también [storefront.md](./storefront.md).

## Admin (ADMIN / SUPER_ADMIN)

| Método | Ruta |
|--------|------|
| GET/POST | `/api/v1/admin/categories` |
| PATCH/DELETE | `/api/v1/admin/categories/{id}` |
| GET/POST | `/api/v1/admin/brands` | GET acepta `category={slug}`; body create/update incluye `category_ids` |
| PATCH/DELETE | `/api/v1/admin/brands/{id}` |
| GET/POST | `/api/v1/admin/products` | create/update valida afinidad marca↔categoría |
| PATCH/DELETE | `/api/v1/admin/products/{id}` |

DELETE = soft delete (`is_active=false`).

No se puede desactivar categoría/marca con productos activos.

### Afinidad marca–categoría

- Cada marca declara `category_ids` (categorías que maneja).
- Herencia hacia abajo: válida en esa categoría y todos sus hijos.
- Producto con marca sin afinidad compatible → `400 Brand not allowed for this category`.
- Marca sin `category_ids` no puede usarse en productos.
