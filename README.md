# GEMA Technology

Plataforma de comercio electrónico tecnológico para Ecuador.

Monorepo con frontend Next.js, backend FastAPI, PostgreSQL y Redis.

## Requisitos

- **Node.js** 20+
- **Python** 3.12+
- **Docker** y **Docker Compose**
- **npm** 10+

## Instalación

### 1. Configurar entorno

```bash
cp .env.example .env
```

### 2. Infraestructura

```bash
docker compose up -d
```

Por defecto PostgreSQL se expone en el host como `5433` (para evitar conflictos con un Postgres local en `5432`). Ajusta `POSTGRES_PORT` en `.env` si lo necesitas.

Scheduler de expiración de reservas (opcional en local; **obligatorio** en staging/prod ops):

```bash
# Con API en el host (uvicorn :8000):
docker compose --profile scheduler up -d
# o, desde apps/api:
python -m app.scripts.expire_reservations --loop
```

Detalle: `docs/architecture/reservation-scheduler-v1.md`.

### 3. Dependencias Node (siempre desde la raíz)

Este monorepo usa **npm workspaces**. Instala **solo desde la raíz**; no ejecutes `npm install` dentro de `apps/web`.

```bash
# desde gema-technology/
npm install
```

Las dependencias viven en `node_modules/` de la raíz (un solo árbol). Puede aparecer `apps/web/node_modules/.vite` como cache local de tests; no es una segunda instalación completa.

### 4. Backend (un solo entorno Python)

```bash
cd apps/api
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
python -m app.scripts.seed
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

> Hay **un solo venv**: `apps/api/.venv`. No crees otro en la raíz del monorepo.  
> El frontend proxya `/api/*` al backend: la API debe estar en el puerto 8000.

### 5. Frontend

En **otra terminal**, desde la raíz:

```bash
npm run dev
```

Abre `http://localhost:3000`

Rutas disponibles:

- `/` — home storefront (hero, categorías, destacados, búsqueda)
- `/products` — catálogo con filtros/búsqueda/sort/paginación por URL
- `/products/[slug]` — detalle de producto (galería, specs, precio, disponibilidad, agregar al carrito)
- `/categories` — listado de categorías
- `/categories/[slug]` — productos por categoría
- `/cart` — carrito (requiere sesión)
- `/checkout` — confirmar compra (sin pago)
- `/orders` — mis órdenes
- `/orders/[order_number]` — detalle / confirmación
- `/login` — iniciar sesión
- `/register` — crear cuenta
- `/account` — perfil (requiere sesión)
- `/admin` — área admin (ADMIN / SUPER_ADMIN)
- `/admin/orders` — órdenes (admin)

## Autenticación

- Cookie HttpOnly `gema_session` (no localStorage).
- El frontend proxya `/api/*` al backend (`API_ORIGIN`).
- Roles: `CUSTOMER`, `ADMIN`, `SUPER_ADMIN`.
- Documentación detallada: [docs/api/auth.md](docs/api/auth.md)

Admin de desarrollo opcional (no hardcodeado):

```env
SEED_ADMIN_EMAIL=admin@example.com
SEED_ADMIN_PASSWORD=change_me_admin
```

Luego vuelve a ejecutar `python -m app.scripts.seed`.

## Calidad

### Frontend

```bash
npm run lint
npm run typecheck
npm run test --workspace=apps/web
```

### Backend

```bash
cd apps/api
ruff check .
ruff format --check .
pytest
```

## Documentación

- [Arquitectura](docs/architecture/overview.md)
- [API Auth](docs/api/auth.md)
- [API Catálogo](docs/api/catalog.md)
- [API Storefront](docs/api/storefront.md)
- [API Cart](docs/api/cart.md)
- [API Orders](docs/api/orders.md)
- [API Payments](docs/api/payments.md)
- [PayPhone Ecuador](docs/architecture/payphone-ecuador-v1.md)
- [API Proveedores](docs/api/suppliers.md)
- [API Inventario](docs/api/inventory.md)
- [API Pricing](docs/api/pricing.md)
- [Database Catálogo](docs/database/catalog.md)
- [Database Proveedores](docs/database/suppliers.md)
- [Database Inventario](docs/database/inventory.md)
- [Database Pricing](docs/database/pricing.md)
- [Database Cart](docs/database/cart.md)
- [Database Orders](docs/database/orders.md)
- [Database Payments](docs/database/payments.md)

## Estado

Fases completadas: … + **Payment Core** + **PayPhone Ecuador (sandbox-ready)**.
