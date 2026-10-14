# Database — Inventory

## Entidades

### Location
- Bodegas / ubicaciones físicas
- `code` único (default seed: `MAIN` — Bodega Principal, Ibarra)
- Soft active flag
- Preparado para múltiples ubicaciones (sin transferencias aún)

### Inventory
- Unique: `(product_id, location_id)`
- `quantity`, `reserved_quantity`, reorder thresholds
- Check constraints: no negativos; `reserved_quantity <= quantity`
- **No** almacena `available_quantity` (calculado: `quantity - reserved_quantity`)

### InventoryMovement
- Auditoría de cambios de stock
- `quantity` siempre positivo
- `direction` `IN`/`OUT` (necesario para ADJUSTMENT +/-)
- Tipos: `PURCHASE`, `SALE`, `RESERVATION`, `RELEASE`, `ADJUSTMENT`, `RETURN`, `DAMAGE`
- `created_by` → usuario de sesión (nunca del cliente)

## Relaciones

```text
Product ──< Inventory >── Location
                │
                └── InventoryMovement
```

Inventario físico ≠ `SupplierProduct` (costo/disponibilidad del proveedor).

## Migración

`004_inventory` (revisa `003_suppliers`)
