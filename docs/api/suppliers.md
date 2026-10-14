# API — Suppliers

Todos los endpoints requieren roles `ADMIN` o `SUPER_ADMIN`.

## Suppliers

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/v1/admin/suppliers` | Listar (`search`, `is_active`) |
| POST | `/api/v1/admin/suppliers` | Crear |
| GET | `/api/v1/admin/suppliers/{id}` | Detalle |
| PATCH | `/api/v1/admin/suppliers/{id}` | Actualizar |
| DELETE | `/api/v1/admin/suppliers/{id}` | Soft delete |

## Supplier Products

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/v1/admin/suppliers/{id}/products` | Productos del proveedor |
| POST | `/api/v1/admin/suppliers/{id}/products` | Asociar producto existente |
| PATCH | `/api/v1/admin/suppliers/{id}/products/{sp_id}` | Actualizar relación |
| DELETE | `/api/v1/admin/suppliers/{id}/products/{sp_id}` | Soft delete relación |

## Product → Suppliers

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/v1/admin/products/{product_id}/suppliers` | Proveedores de un producto |
| POST | `/api/v1/admin/products/{product_id}/suppliers` | Vincular proveedor |

## Reglas

- No duplicar `tax_id` + `tax_id_type`
- No crear SupplierProduct si supplier o product están inactivos
- `cost >= 0`, `lead_time_days >= 0`, `MOQ > 0`
- Currency inicial: solo `USD`
- Availability debe ser un valor del enum
- CUSTOMER recibe 403
