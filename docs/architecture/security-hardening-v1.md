# GEMA Technology — Security Hardening

**Última actualización:** 2026-10-08  
**Versiones:** Fase 0 (2026-08-31) · **v1.1** (2026-10-08)

---

## Resumen v1.1

Correcciones de seguridad verificadas contra el código actual tras la auditoría QA del 2026-10-08. **No se reconstruyeron** módulos comerciales (cart, checkout, orders, reservations, pricing) ni se integró pasarela real.

| Área | Antes (verificado) | Después |
|------|-------------------|---------|
| Artefacto E2E | `.e2e-last-order.json` con password en claro, no en `.gitignore` | Ignorado + eliminado del working tree (nunca versionado en Git) |
| `INTERNAL_JOB_SECRET` | Comparación `!=` | `hmac.compare_digest` vía `verify_internal_job_secret` |
| OpenAPI `/docs` `/redoc` | Siempre activos | Deshabilitados en producción por defecto; `OPENAPI_ENABLED` override |
| Confirmación manual de pago | Admin en cualquier `APP_ENV` | Solo development/staging/test; **403 en production** |
| Sesiones Redis | `NotImplementedError` | `RedisSessionStore` funcional; fallo duro si Redis cae con `SESSION_BACKEND=redis` |
| Rate limit auth | Solo memoria | Redis compartido cuando backend=`redis`; fail-open si Redis cae (no-prod) |
| Secretos de desarrollo | Aceptados en production | `Settings` rechaza defaults inseguros y `manual`+`memory` en production |

**GEMA no está lista para producción comercial** solo porque pasen estos tests: falta pasarela real, email, CI/CD, fulfillment, etc.

---

## 1. Hallazgos confirmados (Fase 1)

| # | Hallazgo | Ubicación | Riesgo | Estado v1.1 |
|---|----------|-----------|--------|-------------|
| 1 | Artefacto E2E con credenciales | `.e2e-last-order.json` | Exposición accidental al versionar | **CORREGIDO** |
| 2 | Comparación no constant-time | `inventory/router.py` | Timing side-channel menor | **CORREGIDO** |
| 3 | OpenAPI siempre expuesto | `main.py` | Superficie de ataque / enumeración | **CORREGIDO** |
| 4 | Confirm manual en prod | `payments/router.py` | Marcar PAID sin pasarela | **CORREGIDO** |
| 5 | Redis sessions stub | `core/sessions.py` | Multi-instancia imposible | **CORREGIDO** |
| 6 | Rate limit solo en proceso | `core/rate_limit.py` | Bypass multi-worker | **CORREGIDO** (con Redis) |
| 7 | Defaults inseguros | `config.py`, `.env.example` | Deploy inseguro | **CORREGIDO** (gate prod) |

---

## 2. Credenciales E2E

- Archivo local `.e2e-last-order.json` contenía campos `email` / `password` (valores no documentados aquí).
- **No estaba en el índice Git** ni en historial detectable (`git log` vacío para ese path).
- Patrones añadidos a `.gitignore`: `.e2e-last-order.json`, `.e2e-*.json`, `*e2e-last-order*.json`.
- Artefacto eliminado del working tree.
- **Ningún test del repo genera este archivo.**
- **Rotación:** si la cuenta del artefacto era real (no solo seed local), rotar su contraseña. Añadir a `.gitignore` **no** limpia historial Git si algún día se hubiera commiteado.

---

## 3. Secreto de jobs internos

**Archivo:** `apps/api/app/core/internal_auth.py`  
**Uso:** `POST /api/v1/internal/reservations/expire` (`X-GEMA-Internal-Secret`)

- Comparación: `hmac.compare_digest`.
- Ausente / vacío / incorrecto → **401** con mensaje genérico (sin filtrar el secreto).
- En `APP_ENV=production`, `INTERNAL_JOB_SECRET` no puede ser un placeholder de desarrollo.

---

## 4. OpenAPI / Swagger / ReDoc

**Archivo:** `apps/api/app/main.py` — `create_app()`

| Condición | `/docs` `/redoc` `/openapi.json` |
|-----------|----------------------------------|
| `APP_ENV != production` y `OPENAPI_ENABLED` unset | Habilitados |
| `APP_ENV=production` y unset | **Deshabilitados** (404) |
| `OPENAPI_ENABLED=true` | Habilitados (incluso en prod; no recomendado) |
| `OPENAPI_ENABLED=false` | Deshabilitados |

Ocultar docs **no** autentica endpoints de negocio.

---

## 5. Confirmación manual de pago

**Endpoint:** `POST /api/v1/admin/payments/{id}/confirm` (rol ADMIN)

| Entorno | Comportamiento por defecto |
|---------|----------------------------|
| development / staging / test | Permitido |
| production | **403** |

Overrides: `ALLOW_MANUAL_PAYMENT_CONFIRM=true|false`.  
En production, `ALLOW_MANUAL_PAYMENT_CONFIRM=true` y `PAYMENT_DEFAULT_PROVIDER=manual` **rechazan el arranque** (`Settings` validator).

CUSTOMER sigue sin poder confirmar (403 RBAC). No hay auto-confirm por redirect del frontend.

---

## 6. Sesiones Redis

**Archivo:** `apps/api/app/core/sessions.py`

| Backend | Comportamiento |
|---------|----------------|
| `SESSION_BACKEND=memory` | `MemorySessionStore` (tests / single-process) |
| `SESSION_BACKEND=redis` | `RedisSessionStore` (TTL Redis `SET` + `ex`) |
| Redis caído + backend redis | **`RuntimeError`** — sin fallback silencioso a memoria |

Logout elimina la clave. No se almacenan contraseñas ni se loguean tokens.

Dependencia: `redis>=5.2.0` en `apps/api/pyproject.toml`. Redis ya existía en `docker-compose.yml`.

---

## 7. Rate limiting auth

**Archivo:** `apps/api/app/core/rate_limit.py`  
**Endpoints:** login / register (contrato y límites sin cambio: default 10 / 60s)

| Backend | Origen |
|---------|--------|
| `AUTH_RATE_LIMIT_BACKEND` | Explícito |
| Si unset | Hereda `SESSION_BACKEND` |

- Redis: sliding window atómico (Lua + ZSET), compartido entre procesos.
- Si Redis falla en **no-producción** con backend redis: fail-open + log (no bloquea a todos los clientes).
- En **producción**, Settings exige backend redis; si Redis no responde al construir el limiter → error.
- En **producción**, si Redis falla **en tiempo de check** → **503 fail-closed** (no se deja el auth sin rate limit).

---

## 8. Configuración y secretos

### Variables por entorno

| Variable | Development | Staging | Production |
|----------|-------------|---------|------------|
| `APP_ENV` | `development` | `staging` | `production` |
| `POSTGRES_PASSWORD` | placeholder OK | fuerte | **obligatorio fuerte** |
| `INTERNAL_JOB_SECRET` | `dev-internal-job-secret` OK | fuerte | **obligatorio fuerte** |
| `PAYMENT_WEBHOOK_SECRET` | placeholder OK | fuerte | **obligatorio fuerte** |
| `PAYMENT_DEFAULT_PROVIDER` | `manual` | `manual` OK | **no `manual`** |
| `SESSION_BACKEND` | `memory` | `redis` recomendado | **`redis` obligatorio** |
| `AUTH_RATE_LIMIT_BACKEND` | `memory` / hereda | `redis` | **`redis` (o hereda redis)** |
| `OPENAPI_ENABLED` | unset → on | unset → on | unset → **off** |
| `ALLOW_MANUAL_PAYMENT_CONFIRM` | unset → on | unset → on | unset → **off** |
| `CORS_ORIGINS` | localhost | staging origin | **HTTPS origin** |
| `API_ORIGIN` | localhost:8000 | staging API | prod API (server-side Next rewrite; no es secreto del bundle) |

Placeholders de ejemplo en `.env.example` **no** son secretos reales. No copiar valores de `.env` a ejemplos.

### Redis en compose

`docker-compose.yml` expone Redis **sin autenticación** en el puerto mapeado — aceptable solo en red de desarrollo local. Endurecer (password / red privada) antes de exponer en staging/prod.

---

## 9. Pruebas ejecutadas (2026-10-08)

| Suite | Resultado |
|-------|-----------|
| Backend `pytest` | **169 passed** |
| Backend `ruff check` (archivos tocados) | **passed** |
| Frontend `npm run test --workspace=apps/web` | **59 passed** |
| Frontend `npm run lint --workspace=apps/web` | **FAILED** — 18 errors / 4 warnings preexistentes (`react-hooks/set-state-in-effect`, etc.); no introducidos por v1.1 |
| Frontend `npm run build` / `typecheck` | **FAILED** — error TS preexistente en `CategoryPicker.tsx` (KeyboardEvent); no introducido por v1.1 |

Cobertura nueva: `apps/api/tests/test_security_hardening_v1_1.py` (secreto interno, OpenAPI, pagos, Settings prod, Redis sessions, rate limit multi-proceso).

Regresión previa: `test_security_hardening.py` (Fase 0) sigue pasando.

---

## 10. Riesgos restantes

1. **Sin pasarela de pago real** — provider `manual` solo válido fuera de production.
2. **Redis compose sin auth** — riesgo en redes no locales.
3. **Rate limit fail-open** ante caída de Redis (diseño consciente; en prod el arranque exige Redis disponible para el limiter).
4. **Sin account lockout por usuario**, MFA, reset password, email verification.
5. **Sin WAF / rate limit global** en APIs públicas.
6. **Webhook manual** (`PAYMENT_WEBHOOK_SECRET`) sigue siendo un atajo de integración — rotar y restringir red.
7. **Módulo search** restaurado desde historial de agente (fuentes `.py` faltaban; solo quedaban `.pyc`) para poder importar la API — no es parte del hardening; revisar integridad del módulo AI/search por separado.

---

## 11. Pasos de despliegue necesarios

1. Instalar dependencia API: `redis>=5.2.0`.
2. Asegurar Redis alcanzable (`REDIS_HOST` / `REDIS_PORT`).
3. Definir secretos fuertes (nunca los placeholders de `.env.example`).
4. `APP_ENV=production` + `SESSION_BACKEND=redis` + provider de pago no-manual.
5. Verificar que `/docs` responde 404 y que confirm manual admin responde 403.
6. Rotar cualquier credencial que hubiera estado en artefactos E2E locales.
7. No asumir producción comercial lista sin pasarela, email y operación post-pago.

---

## Apéndice — Fase 0 (histórico 2026-08-31)

Cambios previos conservados:

- Cliente ya no confirma pagos (`POST /payments/{id}/confirm` → 404).
- Rate limiting auth introducido.
- CORS endurecido.
- Confirm admin-only (ahora además gated por entorno en v1.1).
