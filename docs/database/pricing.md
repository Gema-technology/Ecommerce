# Database — Pricing

## Entidad

### ProductPrice
- `amount` NUMERIC(14,4) — precio de venta (nunca float)
- `price_type`: `RETAIL` | `WHOLESALE` | `PROMOTIONAL` (extensible)
- `currency` default `USD` (sin conversión automática)
- Vigencia: `starts_at` / `ends_at` (null = abierto)
- Historial: no sobrescribir; crear nuevos registros
- Soft flag: `is_active`
- `cost_reference` opcional (snapshot Decimal)
- `supplier_product_id` opcional (fuente de costo explícita)
- `created_by` → usuario de sesión

## Relación

```text
Product ──< ProductPrice
                │
                └── (optional) SupplierProduct.cost
```

No existe `Product.price` ni `Product.cost`.

## Impuestos (futuro)

`ProductPrice.amount` = precio base. IVA / SRI se aplicarán como capa posterior (`TaxRule` → Final Price), no hardcodeados aquí.

## Migración

`005_pricing` (revisa `004_inventory`)
