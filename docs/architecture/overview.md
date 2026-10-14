# Arquitectura GEMA Technology

## Visión general

GEMA Technology es una plataforma de comercio electrónico tecnológico para Ecuador. El proyecto se organiza como un **monorepo** con aplicaciones separadas para frontend y backend, más infraestructura compartida.

```text
gema-technology/
├── apps/
│   ├── web/          # Frontend Next.js
│   └── api/          # Backend FastAPI
├── packages/         # Paquetes compartidos (futuro)
├── infrastructure/
│   └── docker/
└── docs/
```

## Estado actual

### Frontend (`apps/web`)

- Next.js App Router, React 19, TypeScript strict, Tailwind CSS.
- Autenticación por sesión/cookie vía `AuthProvider` + `CartProvider`.
- **Storefront**: `/`, `/products`, `/products/[slug]`, `/categories`, `/categories/[slug]`, `/cart`, `/checkout`, `/orders`, `/orders/[order_number]`, `/orders/[order_number]/payment`, `/payment/success`, `/payment/failed`.
- Auth: `/login`, `/register`, `/account`.
- Admin: `/admin`, … `/admin/inventory`, `/admin/orders`, `/admin/payments`.
- Middleware protege `/account` y `/admin` (redirect a `/login` sin cookie).
- Proxy same-origin: Next.js reescribe `/api/*` hacia el backend.
- Clientes: `catalogApi`, `cartApi`, `ordersApi`, `paymentsApi`.
- Design System **Dark Technology**: tokens en `styles/theme.css`, Inter + Space Grotesk, Lucide, UI primitives.

### Backend (`apps/api`)

- FastAPI modular: … `cart`, `orders`, `checkout`, `payments`, `quotes`.
- SQLAlchemy 2 + Alembic.
- Checkout atómico: valida cart/product/price/stock → Order + snapshots → reserva inventario → Cart `CONVERTED`.
- Payment Core: `Payment` + `payment_events` (idempotencia), abstracción `PaymentProvider`, webhook público, éxito → Order `PAID` + consume reserva + movimiento SALE.

### Infraestructura

- PostgreSQL 16 y Redis 7 vía Docker Compose.
- Redis reservado para sesiones multi-instancia (`SESSION_BACKEND=redis` futuro).

## Autenticación

```text
Browser ──credentials──► Next.js (/api proxy) ──► FastAPI
                              │
                              └── Set-Cookie: gema_session (HttpOnly)
```

1. **Register / Login**: el API valida credenciales, crea sesión y setea cookie.
2. **Requests autenticados**: la cookie viaja automáticamente (`credentials: include`).
3. **Logout**: invalida la sesión en el store y borra la cookie.
4. **Autorización**: dependencias `require_authenticated_user`, `require_role`, `require_any_role`.

### Roles

| Rol | Uso |
|-----|-----|
| `CUSTOMER` | Asignado automáticamente al registrarse; carrito propio |
| `ADMIN` | Acceso a `/admin` y `GET /api/v1/admin/users` |
| `SUPER_ADMIN` | Mismos privilegios admin + preparado para privilegios elevados |

## Evolución prevista

| Fase | Ámbito | Descripción |
|------|--------|-------------|
| 1 | Fundación | Monorepo, API, frontend, Postgres, Redis |
| 2 | Auth | Usuarios, roles, sesiones, admin básico |
| 3 | Catálogo | Categories, Brands, Products, Images, Specs JSONB |
| 4 | Proveedores | Suppliers, SupplierProducts (costos/availability) |
| 5 | Inventario | Locations, stock, reservations, movements, low stock |
| 6 | Pricing | ProductPrice, historial, filtros, margen |
| 7 | Storefront MVP | Home, catálogo, detalle, categorías, filtros, SEO |
| 8 | Shopping Cart | Cart / CartItem, totales, UI `/cart` |
| 9 | Orders & Checkout | Order, reservas, PENDING_PAYMENT |
| 10 | Payment Core | Payments, webhooks idempotentes, consume reserva |
| 11 | Quotes / B2B | Cotizaciones, proformas PDF, admin |
| 12 | Comercio | Shipping, facturación, Stripe, WhatsApp, SRI |

## Calidad

- **Backend**: pytest, Ruff.
- **Frontend**: ESLint, TypeScript strict, Vitest.
