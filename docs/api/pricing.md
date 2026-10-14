# API — Pricing

## Admin (ADMIN / SUPER_ADMIN)

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/api/v1/admin/products/{id}/prices` | Crear precio |
| GET | `/api/v1/admin/products/{id}/prices` | Listar |
| GET | `/api/v1/admin/products/{id}/prices/current` | Vigente (`price_type` query) |
| GET | `/api/v1/admin/products/{id}/prices/history` | Historial |
| PATCH | `/api/v1/admin/products/{id}/prices/{price_id}` | Editar (futuros / flags) |
| DELETE | `/api/v1/admin/products/{id}/prices/{price_id}` | Soft deactivate |
| GET | `/api/v1/admin/products/{id}/margin` | Margen (`supplier_product_id` opcional) |

## Público

`GET /api/v1/products` y `GET /api/v1/products/{slug}` incluyen:

```json
"price": { "amount": "1199.99", "currency": "USD", "price_type": "RETAIL" }
```

o `price: null` si no hay retail vigente.

Filtros: `min_price`, `max_price` (retail vigente; productos sin precio excluidos del filtro).

## Reglas

- Overlap activo mismo `product_id` + `price_type` → 409
- amount >= 0, Decimal/NUMERIC
- No modificar amount/currency/starts_at de precios ya iniciados
- CUSTOMER → 403 en admin
- Margen: `(sale - cost) / sale * 100`; si sale=0 → `margin_percentage=null`
