# GEMA Technology — Plan de migración FastAPI/Python → Next.js/TypeScript

**Fecha:** 2026-10-20  
**Estado:** Planificación (sin cambios de código, migraciones, dependencias ni configuración)  
**Alcance de este entregable:** solo este documento  
**Fuente de verdad:** inspección de `apps/api`, `apps/web`, Alembic `001`–`021`, pruebas y docs de arquitectura existentes

---

## 0. Principios de esta migración

1. **No reescribir ni eliminar** el backend FastAPI mientras no haya paridad funcional y pruebas equivalentes.
2. **Contratos `/api/v1/*` estables**: mismos paths, métodos, códigos y formas de error (`detail`), salvo diferencias documentadas.
3. **Una sola fuente de reglas de negocio** en cada fase: o Python o TypeScript, nunca ambas activas para el mismo flujo.
4. **Migración por verticales pequeños**, con feature flag / rewrite selectivo y reversión inmediata al proxy FastAPI.
5. **Paridad ≠ endpoint equivalente**: checkout, inventario, pagos y SRI exigen pruebas de concurrencia, idempotencia y regresión.
6. **Multiempresa** se diseña aquí y se implementa en fases posteriores; el esquema actual es **single-store**.
7. **PostgreSQL se conserva**; las migraciones futuras deben ser compatibles con datos Alembic existentes.

---

## 1. Inventario del backend (verificado)

### 1.1 Estado de partida confirmado

| Elemento | Estado verificado |
|----------|-------------------|
| `apps/web` Next.js App Router + React + TypeScript | Sí — Next `16.2.12`, React `19.2.4`, App Router en `src/app/` |
| `apps/api` FastAPI + Python | Sí — factory `create_app()` en `apps/api/app/main.py` |
| PostgreSQL + Alembic | Sí — migraciones `001`–`021` en `apps/api/alembic/versions/` |
| Autenticación y roles | Sí — cookie `gema_session`, roles `CUSTOMER` / `ADMIN` / `SUPER_ADMIN` |
| Catálogo, proveedores, inventario, precios | Sí |
| Carrito, checkout, pedidos, reservas de stock | Sí (reservas = hold de inventario ligado a orden, no booking de mesas) |
| Pagos | Sí — PayPhone, transferencia, COD, manual |
| Integraciones fiscales SRI | Sí — config, firma XAdES, SOAP, PDF/XML |
| Notificaciones / correo | Sí — SMTP opcional (`email_enabled` por defecto `false`), dedupe por constraint |
| Tareas programadas | Sí — cron/sidecar HTTP a `POST /api/v1/internal/reservations/expire` (no Celery/APScheduler) |
| Route Handlers en Next.js | **No** — `/api/*` se reescribe a FastAPI (`apps/web/next.config.ts`) |
| Multiempresa / `company_id` / `tenant_id` | **No** en API ni web |
| JWT Bearer | **No** — solo sesiones por cookie |
| Paquetes compartidos `packages/` | Vacío (solo `.gitkeep`) |

### 1.2 Estructura modular FastAPI

Prefijo global: `/api/v1` (montaje en `main.py`).

| Módulo | Rutas (resumen) | Servicio / lógica clave |
|--------|-----------------|-------------------------|
| `health` | `GET /health`, `GET /health/ready` | Liveness / readiness Postgres (+ Redis si aplica) |
| `auth` | `POST /auth/register\|login\|logout`, `GET /auth/me`, `POST /auth/accept-invite` | Argon2 (`pwdlib`), sesión cookie |
| `users` | `/users/me`, `/admin/customers*` | Perfil, COD whitelist, activar clientes |
| `employees` | `/admin/employees*` | Invitaciones, roles, último `SUPER_ADMIN` |
| `store_config` | `/admin/store-config` | Singleton `id=1` |
| `categories` / `brands` / `products` | públicos + `/admin/*` | CRUD, soft-delete, listados |
| `suppliers` | `/admin/suppliers*`, links producto↔proveedor | Costos / disponibilidad |
| `inventory` | `/admin/locations\|inventory*`, movimientos, `POST /internal/reservations/expire` | Stock, reserve/release/consume, expire |
| `pricing` | `/admin/products/{id}/prices*`, margen | Ventanas RETAIL/WHOLESALE/PROMOTIONAL |
| `cart` | `/cart*` | Carrito ACTIVE por usuario, sync precios |
| `checkout` | `POST /checkout/preview`, `POST /checkout` | Transacción: lock cart → orden → reserva |
| `orders` | `/orders*`, `/admin/orders*` | Ownership (404 si no es dueño), cancel, fulfillment |
| `ops` | `GET /admin/ops/summary` | KPIs admin |
| `payments` | pagos por orden, sync, webhooks PayPhone/genérico, admin confirm | Idempotencia `payment_events` |
| `quotes` | pricing-config, catálogo cotización, quotes + PDF | PDF WeasyPrint/reportlab |
| `sri` | config, cert, fiscal-documents, emit/retry, pdf/xml | Firma + SOAP `zeep` |
| `search` | `POST /search/assist` | Parser reglas + OpenAI opcional |
| `commerce` | (sin router) | `totals.py`, `shipping.py`, `tax.py` (IVA gated por `COMMERCE_TAX_ENABLED`) |
| `notifications` | (sin router público) | Email order.created/paid/shipped |

Auth por endpoint (patrón verificado):

- **Public** + rate limit: register/login/accept-invite, search assist  
- **Session** (`CurrentUser`): cart, checkout, orders/payments del cliente  
- **Admin** (`ADMIN` \| `SUPER_ADMIN`): catálogo admin, inventario, etc.  
- **SuperAdmin**: invite/role/reset password empleados  
- **Internal**: `X-GEMA-Internal-Secret`  
- **Webhook**: secretos de proveedor (`X-GEMA-Payment-Secret` u homologable)

### 1.3 Modelos y relaciones (PostgreSQL)

**No hay columnas de tenant.** Ownership actual: `user_id` en carts/orders; empleados vía `employees.user_id`; config/SRI/quote counters como singletons `id=1`.

| Tabla(s) | Origen modelo | Notas |
|----------|---------------|-------|
| `users`, `roles`, `user_roles` | `roles/models.py` | Incluye `allow_cash_on_delivery` |
| `categories`, `brands`, `products`, `product_images`, `brand_categories` | `catalog/models.py` | |
| `suppliers`, `supplier_products` | `suppliers/models.py` | |
| `locations`, `inventory`, `inventory_movements`, `inventory_reservations` | `inventory/models.py` | Reservas → `order_id` |
| `product_prices` | `pricing/models.py` | |
| `carts`, `cart_items` | `cart/models.py` | Índice parcial: un ACTIVE cart / user |
| `orders`, `order_items`, `order_daily_counters`, `order_status_events` | `orders/models.py` | Snapshots cliente/shipping |
| `payments`, `payment_events` | `payments/models.py` | Unique `(provider, provider_event_id)` |
| `quote_*`, counters | `quotes/models.py` | Catálogo de cotización separado |
| `store_config` | `store_config/models.py` | Singleton |
| `employees` | `employees/models.py` | Invite tokens |
| `sri_config`, `fiscal_documents` | `sri/models.py` | Singleton + docs por orden |
| `notification_dispatches` | `notifications/models.py` | Unique `(order_id, event_key, channel)` |

Migraciones Alembic (alto nivel): `001` auth → `002` catálogo → `003` suppliers → `004` inventory → `005` pricing → `006` cart → `007` orders/reservations → `008` payments → `009` AI (luego `015` drop) → `010`–`014` consistencia/shipping/quotes/snapshots/images → `016` brand_categories → `017` COD → `018` employees → `019` store_config → `020` SRI → `021` fulfillment notifications.

### 1.4 Transacciones, bloqueos e idempotencia

| Patrón | Dónde |
|--------|--------|
| `SELECT … FOR UPDATE` | cart, checkout, inventory, orders, payments, quote counters, sri_config |
| `pg_advisory_xact_lock(742653601)` | `InventoryService.expire_due_reservations` |
| Idempotencia webhooks | unique `payment_events(provider, provider_event_id)` + manejo IntegrityError |
| Idempotencia notificaciones | unique dispatch constraint |
| Release/consume reservas | documentado e idempotente en servicio de inventario |
| Header HTTP `Idempotency-Key` | **No encontrado** |

Cualquier port TypeScript de estos flujos **debe** preservar semántica de bloqueo en PostgreSQL; no basta un handler “equivalente” en happy path.

### 1.5 Integraciones externas

| Integración | Estado | Dependencia Python notable |
|-------------|--------|----------------------------|
| PayPhone | Implementado (link, webhook, sync) | HTTP client |
| Bank transfer / COD / manual | Implementado | — |
| SMTP | Implementado, deshabilitado por defecto | stdlib / SMTP |
| SRI | Implementado (PKCS#12, XAdES, SOAP, PDF/XML) | `cryptography`, `lxml`, `zeep`, WeasyPrint |
| OpenAI search | Opcional (`AI_ENABLED`) | `openai` |
| Redis | Sesiones + rate limit auth | `redis` |
| Push / SMS / WhatsApp | **No encontrado** | — |

### 1.6 Dependencias Python sin reemplazo trivial en Node

| Paquete (`pyproject.toml`) | Riesgo | Estrategia de sustitución propuesta |
|----------------------------|--------|-------------------------------------|
| `weasyprint` (+ Cairo/Pango) | Alto | PDF via servicio dedicado, `@react-pdf/renderer`, o Puppeteer/Chromium; evaluar paridad visual con quotes/SRI |
| `reportlab` | Medio | Fallback PDF; unificar con una sola librería TS |
| `zeep` | Alto | Cliente SOAP WSDL en TS (`soap`/`strong-soap`) o micro-adapter temporal solo para SRI |
| `lxml` + `cryptography` (XAdES-BES) | Muy alto | Librería XAdES madura en Node o **mantener módulo SRI en Python** hasta paridad certificada |
| `pwdlib[argon2]` | Medio | `argon2` / `@node-rs/argon2` — migrar hashes sin re-hash masivo si se conserva el mismo esquema |
| `sqlalchemy` + `alembic` + `psycopg` | Alto (volumen) | ORM/query builder TS + política de migraciones §2.4 |
| `fastapi` / `pydantic` / `uvicorn` | Esperado | Route Handlers + Zod (u homologable) |
| `redis` / `openai` | Bajo | Clientes Node oficiales |

**Implicación:** SRI y PDFs son el **último bloqueador** para retirar Python del producto, no el primero.

### 1.7 Pruebas que protegen flujos críticos

Directorio: `apps/api/tests/` (pytest + httpx; SQLite en memoria; subset Postgres).

| Área | Archivos representativos |
|------|--------------------------|
| Auth / roles | `test_auth.py`, `test_authorization.py`, `test_employees_customers.py` |
| Cart / checkout / stock | `test_cart.py`, `test_orders_checkout.py`, `test_checkout_commercial.py` |
| Inventario / reservas | `test_inventory.py`, `test_reservation_lifecycle.py`, `test_reservation_expire_postgres.py`, `test_expire_reservations_script.py` |
| Pagos | `test_payments.py`, `test_payphone.py`, `test_bank_transfer.py`, `test_cash_on_delivery.py` |
| Pricing / fiscal | `test_pricing.py`, `test_pricing_consistency.py`, `test_tax_fiscal_consistency.py`, `test_sri.py` |
| Quotes / notificaciones / ops | `test_quotes.py`, `test_notifications.py`, `test_order_fulfillment.py`, `test_ops_summary.py` |
| Seguridad / health | `test_security_hardening*.py`, `test_health.py`, `test_store_config.py` |

Frontend: Vitest en `apps/web/src/__tests__/` (componentes/API clients; **no** sustituyen las pruebas de dominio del API).

### 1.8 Frontend (`apps/web`) — acoplamiento actual

- Clientes tipados a mano: `src/lib/*-api.ts` (sin Zod/OpenAPI codegen).
- Auth: `AuthProvider` → `GET /auth/me`; cookie HttpOnly; gate en `src/proxy.ts` para `/account/*` y `/admin/*`.
- Same-origin `/api/v1/*` → rewrite `API_ORIGIN` (default `http://127.0.0.1:8000`).
- Dominios UI alineados con módulos API: catálogo, cart, checkout, orders, payments, admin inventario/proveedores/precios/cotizaciones/SRI/config/ops/empleados/clientes.

---

## 2. Arquitectura TypeScript de destino

### 2.1 Diagrama lógico

```text
Browser
  │  credentials: include (gema_session)
  ▼
Next.js (apps/web)
  ├─ App Router UI (sin cambio de stack)
  ├─ proxy / auth gate (cuenta + admin)
  └─ Route Handlers  /api/v1/*   ← migrados incrementalmente
        │
        ▼
   Controllers (thin)     Validación Zod in/out
        │
        ▼
   Application services   ← reglas de negocio (única fuente por fase)
        │
        ▼
   Repositories / DAL     Transacciones + FOR UPDATE / advisory locks
        │
        ▼
   PostgreSQL (esquema legado + migraciones aditivas)
        │
   Adapters: Redis sessions, SMTP, PayPhone, SRI*, PDF*, OpenAI, cron HTTP
```

\*SRI/PDF pueden permanecer en FastAPI más tiempo vía **proxy selectivo** (rewrite) sin duplicar reglas.

### 2.2 Capas propuestas (ubicaciones objetivo)

Sin instalar paquetes en esta fase. Estructura objetivo cuando se implemente:

```text
apps/web/src/
  app/api/v1/…/route.ts          # Controllers HTTP (Route Handlers)
  server/
    auth/                        # sesión cookie, requireUser/Admin/SuperAdmin/internal
    db/                          # client, transactions, locks helpers
    modules/<domain>/
      schemas.ts                 # Zod (paridad con Pydantic)
      repository.ts
      service.ts
      providers/                 # pagos, email, etc.
    jobs/                        # callers o handlers internos tipados
  lib/                           # clientes UI existentes (apuntan a same-origin)
```

Reglas:

| Capa | Responsabilidad | Prohibido |
|------|-----------------|-----------|
| Route Handler | Parse HTTP, status codes, cookies, wiring | Reglas de precio/stock/pago |
| Service | Casos de uso, orquestación, authz de dominio | SQL crudo disperso |
| Repository | Queries tipadas, locks, constraints | Decisiones de negocio |
| Adapter | HTTP externo, SMTP, firma, PDF | Conocer detalles HTTP de la app |

### 2.3 Autorización centralizada

Portar el modelo de `apps/api/app/modules/auth/dependencies.py`:

1. Resolver sesión desde cookie (`SESSION_COOKIE_NAME`, hoy `gema_session`).
2. `requireAuthenticatedUser` → 401.
3. `requireAnyRole(ADMIN, SUPER_ADMIN)` / `requireRole(SUPER_ADMIN)` → 403.
4. Ownership de recursos cliente: si `resource.user_id !== session.userId` → **404** (paridad con Python, no 403).
5. Jobs: header `X-GEMA-Internal-Secret` con comparación constante en tiempo.
6. Webhooks: secretos de proveedor existentes.

Cuando exista multiempresa (§3), la capa de authz añadirá `companyId` activo + membership **sin** romper el patrón 404 de ownership.

### 2.4 Acceso a datos: Prisma vs Drizzle

Evaluación sobre el esquema y consultas **reales** (no preferencia de moda):

| Criterio | Hallazgo en GEMA | Prisma | Drizzle |
|----------|------------------|--------|---------|
| Esquema legacy Alembic 21 migraciones | Debe mapear tablas existentes sin reset | Bueno con `db pull`; migraciones Prisma vs Alembic = **riesgo dual** | Excelente como query layer sobre SQL existente |
| `FOR UPDATE` / locks explícitos | Crítico en cart/checkout/inventory/payments | Limitado / verboso; a menudo raw SQL | SQL-like explícito; `for('update')` natural |
| `pg_advisory_xact_lock` | Expire reservations | Solo raw | Raw/sql template cómodo |
| Transacciones anidadas / rollback | Checkout + payments | Soportado | Soportado (`db.transaction`) |
| Singletons `id=1` + counters | store_config, sri, quote/order counters | OK | OK |
| Índices parciales / uniques compuestos | cart ACTIVE, payment_events, notifications | Requiere cuidado en schema | Claro en SQL migrations |
| Tipado + DX equipo Next | — | Muy alto | Alto |
| Estrategia de migración de esquema | No romper datos | **Evitar dos motores de migración** | Preferible: **Drizzle Kit o SQL migrator único** adoptando el historial; o mantener Alembic hasta cutover y solo entonces congelar |

**Recomendación:** **Drizzle** como DAL tipado por defecto para esta migración, porque el dominio depende de SQL de concurrencia explícito y de un historial Alembic que no debe bifurcarse. Prisma queda como alternativa solo si el equipo acepta raw SQL frecuente en paths críticos y una política estricta de **un solo** sistema de migraciones.

**No instalar** Prisma ni Drizzle en esta fase.

Migraciones futuras:

1. Corto plazo: seguir Alembic mientras Python sea source of truth del esquema.
2. Al migrar un dominio a TS: cambios de esquema **aditivos** (nullable → backfill → NOT NULL), nunca drop prematuro.
3. Cutover de migraciones: congelar Alembic, generar baseline SQL desde Postgres real, continuar solo con el migrator TS elegido.

### 2.5 Validación

- Zod (o Valibot) espejando schemas Pydantic por módulo (`RegisterRequest`, `CheckoutRequest`, etc.).
- Validar **entrada y salida** en la frontera HTTP para no filtrar campos internos.
- Reutilizar nombres de campos JSON actuales para no romper `*-api.ts`.

### 2.6 Procesos programados en TypeScript

Conservar el patrón ya documentado en `docs/architecture/reservation-scheduler-v1.md`:

```text
cron / compose sidecar / script loop
  → POST /api/v1/internal/reservations/expire
  → handler TS (cuando migre) o FastAPI (hasta entonces)
```

No introducir Celery/Bull “porque sí”. Opcional posterior: `node` one-shot equivalente a `app/scripts/expire_reservations.py` llamando el mismo endpoint.

### 2.7 Integraciones desacopladas

Interfaces estables (nombres orientativos):

- `PaymentProvider` — ya conceptualizado en Python (`manual`, `payphone`, `bank_transfer`, `cash_on_delivery`)
- `EmailSender`
- `SessionStore` (memory | Redis)
- `FiscalIssuer` / `PdfRenderer` — pueden apuntar a implementación Python vía HTTP interno **temporalmente** sin duplicar reglas SRI

### 2.8 Relación con FastAPI durante la transición

```text
next.config rewrites:
  /api/v1/<migrated>/*  →  Next Route Handler (mismo proceso)
  /api/v1/<resto>/*     →  API_ORIGIN (FastAPI)
```

Alternativa equivalente: rewrite catch-all a FastAPI + Route Handlers que “ganan” por especificidad de ruta en App Router. La política exacta se fija al implementar la primera ruta migrada; el invariante es **un solo backend responde cada path**.

---

## 3. Estrategia multiempresa (diseño; sin implementar)

El producto hoy es **una tienda** (`store_config` singleton, sin `company_id`). La plataforma destino debe soportar tecnología, cafeterías, restaurantes y ferreterías como **empresas** (tenants) aisladas.

### 3.1 Modelo conceptual

| Entidad | Rol |
|---------|-----|
| `companies` | Tenant: nombre, sector (`technology` \| `cafe` \| `restaurant` \| `hardware`), timezone, flags |
| `company_memberships` | `user_id` + `company_id` + rol membership (`OWNER` / `ADMIN` / `STAFF` / `CUSTOMER`) |
| `company_branches` (sucursales) | Opcional v1.1; mapa a `locations` existentes |
| Empresa activa | Cookie/header de contexto `X-GEMA-Company-Id` **o** membership única; validada en servidor |

Roles globales actuales (`CUSTOMER` / `ADMIN` / `SUPER_ADMIN`) se reinterpretan:

- `SUPER_ADMIN` plataforma (cross-company) — restringido.
- Admin de tienda → membership `ADMIN`/`OWNER` en una company.
- Cliente → membership `CUSTOMER` (o pedidos con `company_id` + `user_id`).

### 3.2 Aislamiento de datos

Toda fila de negocio lleva `company_id` (UUID NOT NULL tras backfill):

- Catálogo: categories, brands, products, images, prices  
- Proveedores e inventario (locations, stock, movements, reservations)  
- Carts, orders, payments, quotes, fiscal_documents, notification_dispatches  
- `store_config` / `sri_config` dejan de ser singleton global → **uno por company** (o 1:1)

Índices compuestos típicos:

- `UNIQUE (company_id, slug)` en products/categories/brands  
- `UNIQUE (company_id, user_id) WHERE status = 'ACTIVE'` en carts  
- `UNIQUE (company_id, provider, provider_event_id)` en payment_events si el provider id no es globalmente único  
- FK compuestos donde aplique para impedir cross-tenant references

### 3.3 Autorización

En cada request autenticado de negocio:

1. Resolver `companyId` activo.
2. Verificar membership.
3. Todas las queries del repositorio **obligan** `WHERE company_id = :active`.
4. Tests de acceso cruzado: usuario A de company 1 no lee/escribe recursos de company 2 (esperar 404).

Sucursales: permisos `branch_ids` en membership; movimientos de inventario acotados a locations de esas sucursales.

### 3.4 Sectores

El sector no bifurca el core commerce en microservicios. Extensiones por sector = módulos de configuración / campos opcionales (p. ej. aplazables: mesas en restaurante, SKU ferretero), **después** del aislamiento base.

### 3.5 Orden respecto a la migración TS

1. Migrar verticales TS **single-tenant** con paridad.  
2. Introducir `companies` + backfill company “GEMA Technology” default.  
3. Endurecer índices y tests cross-company.  
4. UI de selector de empresa / onboarding.

No implementar multiempresa en la primera tarea (§6).

---

## 4. Plan de migración incremental

### 4.1 Estrategia de transición y reversión

| Mecanismo | Uso |
|-----------|-----|
| Proxy/rewrite selectivo | Rutas no migradas siguen en FastAPI |
| Feature flag env (ej. `TS_API_MODULES=health`) | Activa handlers TS por módulo |
| Misma base de datos | Sin dual-write de negocio |
| Reversión | Quitar path del flag / volver rewrite a `API_ORIGIN` — RPO de datos = 0 si no hubo migración destructiva |
| Paridad | Suite pytest legacy en verde **y** tests TS del módulo; comparación de respuestas en casos fijados (golden fixtures) |
| Criterio de retiro Python del módulo | Paridad + pruebas + N días estable en staging + cero tráfico al router Python |

**Prohibido:** dual-run de la misma regla de negocio en Python y TS “por si acaso”.

### 4.2 Fases

#### Fase 0 — Cimientos (sin dominio de negocio)

| | |
|--|--|
| **Incluye** | Layout `server/db`, `server/auth` stubs, decisión Drizzle confirmada, harness de test (Vitest/Node) contra Postgres de test, documentación de rewrite selectivo |
| **Origen** | `apps/api/app/core/{database,sessions,security,config}.py` |
| **Destino** | `apps/web/src/server/**` (nuevo) |
| **DB** | Ningún cambio de esquema |
| **Pruebas** | Conexión ready, cookie parse unitario |
| **Aceptación** | App sigue 100% proxy a FastAPI; CI web verde |
| **Retiro Python** | Ninguno |
| **Riesgos** | Instalar ORM demasiado pronto; scope creep |

#### Fase 1 — Health

| | |
|--|--|
| **Incluye** | `GET /api/v1/health`, `GET /api/v1/health/ready` |
| **Origen** | `apps/api/app/modules/health.py` |
| **Destino** | `apps/web/src/app/api/v1/health/route.ts`, `.../health/ready/route.ts` |
| **DB** | Solo `SELECT 1` |
| **Pruebas** | Paridad con `test_health.py`; ready falla si Postgres caído |
| **Aceptación** | Con flag, tráfico health no toca FastAPI; sin flag, comportamiento idéntico vía proxy |
| **Retiro** | Cuando staging use TS health y probes de compose apunten al web origin si aplica |
| **Riesgos** | Bajos |

#### Fase 2 — Auth + sesión + `/users/me`

| | |
|--|--|
| **Incluye** | register, login, logout, me, profile patch; session store memory/Redis; Argon2 compatible |
| **Origen** | `auth/*`, `users/*`, `core/sessions.py`, `core/security.py` |
| **Destino** | `server/modules/auth`, `server/modules/users`, route handlers equivalentes |
| **DB** | Sin cambio; leer `users`/`roles`/`user_roles` |
| **Pruebas** | Portar escenarios de `test_auth.py`, `test_authorization.py` (subset) |
| **Aceptación** | Login web existente sin cambios de UI; cookie HttpOnly mismos atributos |
| **Retiro** | Routers auth/users Python tras paridad + empleados aún en Python OK |
| **Riesgos** | Divergencia cookie Secure/SameSite; hash incompatible |

#### Fase 3 — Catálogo lectura pública + admin CRUD

| | |
|--|--|
| **Incluye** | categories, brands, products (públicos + admin) |
| **Origen** | `categories`, `brands`, `products`, `catalog/models` |
| **Destino** | `server/modules/catalog` (+ submódulos) |
| **DB** | Sin cambio |
| **Pruebas** | `test_catalog_*.py` escenarios; tests contrato JSON vs `catalog-types.ts` |
| **Aceptación** | Storefront y admin productos sin regresión UI |
| **Retiro** | Routers catálogo Python |
| **Riesgos** | Filtros/paginación/sort; soft-delete |

#### Fase 4 — Store config, employees, customers admin

| | |
|--|--|
| **Incluye** | store-config, employees invite/accept, customers COD/active |
| **Origen** | `store_config`, `employees`, partes admin de `users` |
| **Destino** | módulos TS homólogos |
| **DB** | Sin cambio |
| **Pruebas** | `test_employees_customers.py`, `test_store_config.py` |
| **Aceptación** | Flujos admin equipo/clientes/config |
| **Retiro** | Routers correspondientes |
| **Riesgos** | Invitaciones email + tokens; último SUPER_ADMIN |

#### Fase 5 — Pricing + suppliers

| | |
|--|--|
| **Incluye** | precios, margen, suppliers y links |
| **Origen** | `pricing`, `suppliers` |
| **Destino** | `server/modules/pricing`, `suppliers` |
| **Pruebas** | `test_pricing*.py`, `test_suppliers.py` |
| **Aceptación** | Paneles admin precios/proveedores |
| **Retiro** | Tras paridad |
| **Riesgos** | Solapes de ventanas de precio |

#### Fase 6 — Cart

| | |
|--|--|
| **Incluye** | CRUD cart, sync-prices |
| **Origen** | `cart/*` |
| **Destino** | `server/modules/cart` |
| **Pruebas** | `test_cart.py` + locks |
| **Aceptación** | Drawer/página cart |
| **Retiro** | Router cart Python |
| **Riesgos** | Carrera ACTIVE cart; quoted prices |

#### Fase 7 — Inventario + expire job

| | |
|--|--|
| **Incluye** | locations, movements, reserve/release/…, expire internal |
| **Origen** | `inventory/*`, script expire, workflow cron |
| **Destino** | `server/modules/inventory` + job HTTP TS |
| **Pruebas** | `test_inventory.py`, `test_reservation_lifecycle.py`, `test_reservation_expire_postgres.py` **obligatorias** |
| **Aceptación** | Sin overselling; expire idempotente bajo paralelismo |
| **Retiro** | Solo con pruebas Postgres de locks en verde |
| **Riesgos** | **Altos** — concurrencia |

#### Fase 8 — Checkout + orders

| | |
|--|--|
| **Incluye** | preview/checkout, orders customer/admin, cancel, status transitions, commerce totals/shipping/tax |
| **Origen** | `checkout`, `orders`, `commerce/*` |
| **Destino** | módulos TS |
| **Pruebas** | `test_orders_checkout.py`, `test_checkout_commercial.py`, `test_order_fulfillment.py` |
| **Aceptación** | Orden + reserva + cart CONVERTED atómico |
| **Retiro** | Tras fase 7 estable |
| **Riesgos** | **Altos** — corazón del negocio |

#### Fase 9 — Payments + notifications

| | |
|--|--|
| **Incluye** | create/sync/webhooks/admin confirm; email dispatches |
| **Origen** | `payments/*`, `notifications/*` |
| **Pruebas** | `test_payments.py`, `test_payphone.py`, `test_bank_transfer.py`, `test_cash_on_delivery.py`, `test_notifications.py` |
| **Aceptación** | Idempotencia webhook; consume reserva en éxito |
| **Retiro** | Providers Python |
| **Riesgos** | Altos (dinero) |

#### Fase 10 — Quotes + search + ops

| | |
|--|--|
| **Incluye** | quotes CRUD, pricing-config, PDF; search assist; ops summary |
| **Origen** | `quotes`, `search`, `ops` |
| **Pruebas** | `test_quotes.py`, ops/search según exista |
| **Aceptación** | PDF legible; assist rate-limit |
| **Retiro** | Parcial: PDF puede quedar adapter externo |
| **Riesgos** | WeasyPrint parity |

#### Fase 11 — SRI / fiscal

| | |
|--|--|
| **Incluye** | config, cert, emisión, retry, pdf/xml |
| **Origen** | `sri/*` |
| **Pruebas** | `test_sri.py`, `test_tax_fiscal_consistency.py` |
| **Aceptación** | Autorización SRI en ambiente de pruebas; XML firmado válido |
| **Retiro Python** | **Último**; si XAdES/SOAP no alcanzan paridad, mantener **solo** este bounded context en FastAPI detrás del mismo path |
| **Riesgos** | Muy altos (cumplimiento) |

#### Fase 12 — Multiempresa

| | |
|--|--|
| **Incluye** | companies, memberships, backfill, índices, company activa, tests cross-tenant |
| **DB** | Migraciones aditivas mayores |
| **Aceptación** | Aislamiento total; sector como metadata |
| **Retiro** | N/A |
| **Riesgos** | Backfill; unique globales actuales (email usuario puede seguir global o volverse por company — decisión explícita antes de implementar) |

#### Fase 13 — Retiro FastAPI

| | |
|--|--|
| **Incluye** | Eliminar rewrite a `API_ORIGIN`, imagen API, deps Python del producto runtime |
| **Condición** | Todas las fases de producto en TS (SRI puede ser excepción documentada) |
| **Aceptación** | Compose/prod sin servicio `api`; probes y cron contra Next |

---

## 5. Criterios globales de “migración completa” por módulo

Un módulo **no** se considera migrado si solo existe un Route Handler. Debe cumplir:

1. Mismos contratos HTTP y códigos de error.  
2. Misma semántica de authz/ownership.  
3. Mismas invariantes de DB (uniques, soft-delete, snapshots).  
4. Pruebas unitarias del servicio + integración HTTP + regresión de concurrencia donde aplique.  
5. Tráfico staging estable y flag de reversión probado.  
6. Router Python sin tráfico y luego eliminado en un PR dedicado.

---

## 6. Primera tarea de implementación (pequeña, verificable)

### Objetivo

Migrar **solo** el endpoint de liveness:

`GET /api/v1/health` → Route Handler en Next.js

sin tocar checkout, auth, schema ni dependencias de ORM pesadas.

### Alcance incluido

1. Crear `apps/web/src/app/api/v1/health/route.ts` que responda JSON paridad con FastAPI:

   ```json
   { "status": "ok", "service": "gema-api" }
   ```

   (mantener `service: "gema-api"` por contrato actual en `health.py`, o documentar cambio a `gema-web` **solo** si se actualiza `test_health.py` y clientes a la vez — por defecto **conservar** el valor).

2. Ajustar el rewrite de Next para que `/api/v1/health` **no** se envíe a FastAPI (o usar la precedencia de Route Handler sobre rewrite, verificada en runtime).

3. Añadir test Vitest/integration mínimo que llame al handler o a la ruta y aserte status 200 + cuerpo.

4. Verificar manualmente: con API Python caída, `GET /api/v1/health` vía `:3000` sigue OK; `GET /api/v1/health/ready` sigue yendo a FastAPI (aún no migrado).

### Alcance excluido

- `/health/ready`  
- Sesiones, DB client, Drizzle/Prisma install  
- Cualquier otro path `/api/v1/*`  
- Cambios en `apps/api`  
- Multiempresa  

### Criterios de aceptación

- [ ] Respuesta idéntica en campos a FastAPI para `GET /api/v1/health`.  
- [ ] Resto de la API sigue proxied a FastAPI.  
- [ ] Test automatizado en `apps/web` en verde.  
- [ ] Reversión documentada en el PR: eliminar el Route Handler restaura el proxy.  
- [ ] Ningún otro archivo de negocio modificado.

### Archivos previstos (solo en la tarea futura)

| Acción | Archivo |
|--------|---------|
| Crear | `apps/web/src/app/api/v1/health/route.ts` |
| Crear | `apps/web/src/__tests__/api-health.test.ts` (o equivalente) |
| Posible ajuste mínimo | `apps/web/next.config.ts` (si el rewrite captura antes que el handler — verificar antes de cambiar) |

**Esta tarea no forma parte de este entregable:** el único archivo creado en la fase actual de planificación es este documento.

---

## 7. Referencias internas verificadas

- `apps/api/app/main.py` — montaje routers  
- `apps/api/pyproject.toml` — dependencias  
- `apps/api/alembic/versions/001_*.py` … `021_*.py`  
- `apps/web/next.config.ts` — rewrite `/api/*`  
- `apps/web/src/lib/*-api.ts` — contratos consumidos por UI  
- `docs/architecture/overview.md`  
- `docs/architecture/reservation-scheduler-v1.md`  
- `docs/architecture/checkout-orders-v1.md`  
- `docs/architecture/payphone-ecuador-v1.md`  
- `docs/architecture/security-hardening-v1.md`
