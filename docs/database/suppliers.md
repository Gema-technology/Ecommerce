# Database — Suppliers

## Entidades

### Supplier
- Identificación fiscal: `tax_id` + `tax_id_type` (`RUC`, `CEDULA`, `PASSPORT`, `OTHER`)
- Unique: `(tax_id, tax_id_type)`
- Soft delete: `is_active`
- País por defecto: Ecuador
- Sin validación matemática de RUC (preparado para fase posterior)

### SupplierProduct
- Relación N:M entre Supplier y Product
- Unique: `(supplier_id, product_id)`
- `cost` NUMERIC(14,4) — costo de adquisición (no precio de venta)
- `currency` string (default `USD`)
- `availability` string enum: `IN_STOCK`, `LOW_STOCK`, `OUT_OF_STOCK`, `PREORDER`, `UNKNOWN`
- Sin `stock_quantity` (módulo Inventory posterior)
- `lead_time_days` nullable
- `minimum_order_quantity` default 1
- `last_checked_at` se actualiza al crear/verificar datos, no en lecturas

## Relaciones

```text
Supplier ──< SupplierProduct >── Product
```

Compatible con futuras entidades: PurchaseOrder, SupplierInvoice.

## Migración

`003_suppliers` (revisa `002_product_catalog`)
