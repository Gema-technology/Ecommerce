# Database — Product Catalog

## Entidades

### Category
- Jerárquica (`parent_id` self-FK)
- Soft delete: `is_active`
- `slug` único
- `image_url` opcional (URL externa hasta tener hosting de archivos)

### Brand
- Soft delete: `is_active`
- `slug` único
- `logo_url` / `website_url` opcionales (URL externa)
- Afinidad M2M con categorías vía `brand_categories`

### BrandCategory (`brand_categories`)
- PK compuesta (`brand_id`, `category_id`)
- `ON DELETE CASCADE` hacia `brands` y `categories`
- **Herencia hacia abajo:** una marca asignada a la categoría `C` es válida en `C` y en todos sus descendientes

### Product
- `sku` único (normalizado UPPER)
- `slug` único (auto-generado)
- `specifications` JSONB (flexible por categoría)
- Sin `price`, `stock` en Product. Proveedores vía `SupplierProduct` (módulo suppliers).
- FK a Brand y Category (`ON DELETE RESTRICT`)
- Validación de negocio: el `category_id` del producto debe estar dentro del subárbol permitido por la afinidad de la marca

### ProductImage
- URLs únicamente (S3 después)
- `sort_order`, `is_primary`
- Cascade delete con Product

## Relaciones

```text
Category ──< Category (parent/children)
Brand >──< Category   (brand_categories, afinidad)
Category ──< Product
Brand ──< Product
Product ──< ProductImage
```

## Migraciones

- `002_product_catalog` — tablas base
- `016_brand_categories` — afinidad M2M + backfill desde `products` existentes
