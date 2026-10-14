# API — Authentication & Users

## Modelo de autenticación

Sesión basada en cookie:

- Nombre: `gema_session` (configurable)
- Flags: `HttpOnly`, `SameSite=Lax` (configurable), `Secure` en producción
- Store: memoria en proceso (`SESSION_BACKEND=memory`), preparado para Redis

No se usan JWT ni `localStorage` para credenciales.

## Roles

Semilla vía `python -m app.scripts.seed`:

- `CUSTOMER`
- `ADMIN`
- `SUPER_ADMIN`

## Endpoints

### Auth

| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| POST | `/api/v1/auth/register` | No | Registro + sesión + rol CUSTOMER |
| POST | `/api/v1/auth/login` | No | Login + sesión |
| POST | `/api/v1/auth/logout` | Opcional | Invalida sesión |
| GET | `/api/v1/auth/me` | Sí | Usuario actual |

### Users

| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| GET | `/api/v1/users/me` | Sí | Perfil propio |
| PATCH | `/api/v1/users/me` | Sí | Actualiza first_name, last_name, phone |

### Admin

| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| GET | `/api/v1/admin/users` | ADMIN o SUPER_ADMIN | Lista usuarios |

## Flujo de registro

1. Cliente envía email, password, nombre, apellido, teléfono.
2. API normaliza email, valida password (≥ 8), rechaza duplicados.
3. Hash Argon2id; crea usuario; asigna `CUSTOMER` (el cliente no elige rol).
4. Crea sesión y setea cookie.

## Flujo de login

1. Valida usuario activo + password.
2. Error genérico `Invalid email or password` (no revela si el email existe).
3. Crea sesión y setea cookie.

## Variables de entorno relevantes

```env
CORS_ORIGINS=http://localhost:3000
SESSION_COOKIE_NAME=gema_session
SESSION_TTL_SECONDS=604800
SESSION_COOKIE_SAMESITE=lax
SESSION_BACKEND=memory
SEED_ADMIN_EMAIL=
SEED_ADMIN_PASSWORD=
```
