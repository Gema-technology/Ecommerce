# GEMA Technology — Fase 0D: Auditoría de preparación del backend para producción

**Fecha:** 2026-10-08  
**Alcance:** Backend FastAPI, PostgreSQL, Redis, Docker Compose local, jobs de expiración de reservas, configuración y controles de seguridad.  
**Fuera de alcance:** Integración de pasarela de pago real, correo transaccional, nuevas funcionalidades comerciales, commits/cambios de rama.  
**Entorno verificado:** Desarrollo local (Windows). **Ningún control se ejecutó en producción.**

---

## 1. Resumen ejecutivo

El backend tiene una base comercial sólida (precios y totales server-side, reservas con locks, pagos idempotentes vía `PaymentEvent`, RBAC en API) y gates de `APP_ENV=production` que rechazan varios defaults inseguros. **No existe infraestructura de producción desplegable** (sin Dockerfiles de API/web, sin CI, sin backups documentados, sin proveedor de pago distinto de `manual`).

Se corrigieron tres defectos de severidad alta/media con pruebas: rate limit auth **fail-closed** en producción ante caída de Redis en runtime, comparación de secretos sin 500 por longitud distinta, readiness de dependencias, y endurecimiento de `.gitignore` / `.env.example`.

**Decisión de salida:** **APTO CON BLOQUEOS DOCUMENTADOS** — se puede iniciar la fase de integración de pagos en sandbox, pero no desplegar comercialmente ni aceptar dinero real hasta resolver los bloqueos de la sección 5.

---

## 2. Matriz de hallazgos

| ID | Área | Hallazgo | Severidad | Evidencia concreta | Impacto real | Corrección / acción | Prueba de verificación |
|----|------|----------|-----------|--------------------|--------------|---------------------|------------------------|
| F01 | Auth / ops | Rate limit Redis **fail-open** en runtime incluso en producción | **Alto** | `apps/api/app/core/rate_limit.py` `RedisSlidingWindowRateLimiter.check` | Caída de Redis elimina protección brute-force en login/register | **Corregido:** fail-closed (503) si `is_production` | `test_redis_rate_limit_fail_closed_in_production` |
| F02 | Auth | `hmac.compare_digest` con longitudes distintas → `ValueError` / 500 | **Medio** | `internal_auth.py`, `payments/providers/manual.py` | Ruido 500 + señal de longitud del secreto | **Corregido:** `secrets_equal` en `core/security.py` | `test_internal_secret_compare_rejects_length_mismatch_as_401` |
| F03 | Ops | Health solo liveness; sin readiness DB/Redis | **Alto** | `apps/api/app/modules/health.py` (antes solo `GET /health`) | Orquestadores marcarían “sano” con Postgres/Redis caídos | **Corregido:** `GET /api/v1/health/ready` | `test_readiness_check_reports_dependencies` |
| F04 | Config | `.gitignore` no cubría `.env.production` / `.env.staging` | **Alto** | `.gitignore` (solo `.env`, `.env.local`, `.env.*.local`) | Riesgo de commit de secretos de entorno | **Corregido:** ignorar `.env.*` con excepción `!.env.example` | Revisión de `.gitignore` |
| F05 | Config | `.env.example` omitía vars AI/business consumidas por Settings | **Bajo** | `config.py` vs `.env.example` | Arranque limpio incompleto / defaults silenciosos | **Corregido:** documentadas en `.env.example` | Diff `.env.example` |
| F06 | Pagos | Producción rechaza `manual` pero solo existe provider `manual` | **Alto** | `config.py` `_enforce_production_safety`; `payments/providers/__init__.py` | Settings “seguro” arranca; primer pago lanza `ValueError` | **Pendiente** (fase pagos) | `_production_settings(payment_default_provider="stripe")` vs `get_provider("stripe")` |
| F07 | Pagos | Webhook manual autentica solo con secreto compartido en header | **Alto** | `ManualPaymentProvider.handle_webhook`; `POST /api/v1/payments/webhooks/{provider}` | Secreto filtrado → marcar cualquier pago SUCCEEDED y consumir stock | **Pendiente:** PSP real + firma de cuerpo + red restringida | `test_payments.py` (auth fail con secret wrong) |
| F08 | Infra | Sin Dockerfile API/web; compose solo Postgres/Redis (+ scheduler curl) | **Alto** | `docker-compose.yml`; ausencia de `apps/*/Dockerfile`; `infrastructure/docker/.gitkeep` | No hay imagen reproducible ni deploy containerizado de la app | **Pendiente** | `Test-Path` Dockerfiles → False |
| F09 | Ops | Sin CI (`.github/` ausente) | **Alto** | No hay workflows | Regresiones de auth/checkout pueden llegar sin gate | **Pendiente** | Glob `.github/**` vacío |
| F10 | Datos | Sin procedimiento documentado de backup/restore PostgreSQL | **Alto** | Ausencia en `docs/` / README | Pérdida de órdenes/inventario sin RPO/RTO | **Pendiente** (propuesta aislada) | Búsqueda `pg_dump` / backup en docs |
| F11 | Migraciones | BD local detrás del head Alembic | **Medio** | `alembic current` → `014_category_image_url`; head → `015_drop_ai_gateway` | Drift local; `alembic check` falla | **Pendiente ops:** `alembic upgrade head` en entorno controlado | Comandos ejecutados 2026-10-08 |
| F12 | Auth | Sin reset password, verificación email, lockout por cuenta | **Medio** | Ausencia de rutas; `email_verified=False` nunca exigido | Cuentas no verificadas; abuso sin lockout (solo IP RL) | **Pendiente** (fase cuenta) | Inspección `auth/` |
| F13 | Auth | Enumeración de email en registro (409) | **Medio** | `auth/service.py` register | Confirma existencia de cuentas | **Pendiente** | Registro con email existente |
| F14 | Auth | Sesión sin renew / idle timeout | **Medio** | `core/sessions.py` `get()` no extiende TTL | Cookie robada válida hasta TTL absoluto (7d default) | **Pendiente** | Inspección store |
| F15 | Config | Staging (`APP_ENV!=production`) bypasea todos los gates | **Medio** | `Settings.is_production` exact match | Staging con secrets débiles / memory / manual confirm | **Pendiente** política ops | `config.py` |
| F16 | Infra | Redis compose sin `requirepass`, puerto publicado | **Medio** | `docker-compose.yml` servicio `redis` | En LAN compartida: lectura/escritura de sesiones y RL | Aceptable solo local; endurecer en staging/prod | Compose |
| F17 | Comercio | Concurrencia de reserva en checkout: lock `FOR UPDATE` confirmado; prueba “concurrente” de admin reserve es secuencial | **Medio** (riesgo residual) | `InventoryService._get_locked_inventory`; `test_reservation_concurrency_serialized` | Doble venta concurrente no demostrada con dos clientes PG paralelos en checkout | **Pendiente:** test PG paralelo checkout | Expire concurrente **sí** cubierto en PG |
| F18 | Scheduler | Sidecar depende de `API_ORIGIN`/`INTERNAL_JOB_SECRET` correctos; compose no corre API | **Medio** | `docker-compose.yml` `reservation-expire`; docs scheduler | Holds vencidos huérfanos si job no corre o secret mismatch | Documentado; ops obligatorio | `reservation-scheduler-v1.md` |
| F19 | Config | `OPENAPI_ENABLED=true` permitido en production | **Bajo** | `config.py` `openapi_docs_enabled` | Superficie de API documentada en prod | **Pendiente** (política) | Default off verificado en tests |
| F20 | Config | `CORS_ORIGINS` localhost no rechazado en production | **Medio** | Default `cors_origins` | Misconfiguración de CORS en deploy | **Pendiente** gate prod | `config.py` |
| F21 | Seguridad | CSRF token ausente; mitiga `SameSite=lax` + HttpOnly | **Bajo** | Cookies sesión | Riesgo bajo en same-site; sube si SameSite=none | Monitorear política cookie | Inspección |
| F22 | Observabilidad | Logs stdlib sin formato estructurado ni alertas; sin Sentry/etc. | **Medio** | `logging.getLogger` disperso | Incidentes de pago/expire difíciles de detectar | **Pendiente** (mínimo necesario en fase ops) | Inspección |
| F23 | Docs | `docs/architecture/overview.md` aún dice Redis sessions “futuro” | **Bajo** | overview vs `sessions.py` | Confusión operativa | **Pendiente** doc | — |

### Aspectos positivos confirmados

| Área | Evidencia |
|------|-----------|
| Precios/totales server-side | `CheckoutService._load_cart_lines` / `_summarize_lines`; `compute_order_totals`; rechazo `PRICE_CHANGED` |
| Snapshot comercial en orden | `OrderItem` name/sku/unit_price; migración `013_order_customer_snapshot` |
| Reservas + expire idempotente | `expire_due_reservations` + advisory lock; tests PG concurrentes **3 passed** |
| Pagos idempotentes | `PaymentEvent` unique + IntegrityError; `_apply_success` no re-consume si orden ya PAID |
| RBAC / ownership | `RequireAdmin`; órdenes/pagos filtran `user_id`; tests hardening |
| Hash contraseñas | Argon2 (`pwdlib`) |
| Sesiones Redis | Hard fail si Redis caído con `SESSION_BACKEND=redis` (sin fallback memoria) |
| Gates production | Rechazo passwords/secrets placeholder, `manual`, `memory` sessions/RL |

### No verificados

- Cookie flags a través del rewrite Next en navegador real con HTTPS.
- Arranque real con `APP_ENV=production` + Redis + secretos fuertes en este host (Settings unit-tested; no se levantó stack prod).
- Restore de backup en entorno aislado (no existe procedimiento).
- Integridad completa del módulo search/AI más allá de wiring de config.
- Comportamiento del scheduler compose E2E en esta sesión (no se levantó profile `scheduler`).

---

## 3. Resultados de controles

| Control | Comando | Resultado real |
|---------|---------|----------------|
| Suite backend | `cd apps/api && python -m pytest -q --tb=line` | **181 passed, 5 skipped**, exit 0 (~39s) |
| Seguridad + health (delta) | `pytest tests/test_security_hardening_v1_1.py tests/test_health.py tests/test_security_hardening.py -q` | **31 passed, 5 skipped**, exit 0 |
| Expire Postgres | `pytest tests/test_reservation_expire_postgres.py -v` | **3 passed**, exit 0 |
| Ruff (archivos tocados) | `ruff check app/core/security.py … tests/test_health.py` | **All checks passed** |
| Docker Compose | `docker compose config --quiet` | exit **0** |
| Compose runtime | `docker compose ps` | `gema-postgres` y `gema-redis` **healthy** (puertos 5433/6379) |
| Alembic heads | `alembic heads` | `015_drop_ai_gateway (head)` — cadena lineal 001→015 |
| Alembic current | `alembic current` | **`014_category_image_url`** (BD local **1 revisión atrás**) |
| Alembic check | `alembic check` | **FAILED:** Target database is not up to date |
| Dockerfiles API/web | `Test-Path apps/api/Dockerfile` / `apps/web/Dockerfile` | **False / False** |
| CI workflows | Glob `.github/**` | **Ausente** |
| Upgrade limpio / restore | — | **No ejecutado** (sin entorno aislado; evitar riesgo sobre BD local) |
| Frontend lint/test/build | — | Fuera de alcance Fase 0D backend; no re-ejecutados aquí |
| Scheduler live E2E | compose `--profile scheduler` | **No ejecutado** en esta sesión |

Skipped (5 en suite completa): principalmente fixtures que requieren Redis/condiciones opcionales según markers existentes; las pruebas PG de expire **sí** corrieron contra Postgres local.

---

## 4. Correcciones realizadas

| Archivo | Cambio |
|---------|--------|
| `apps/api/app/core/rate_limit.py` | Fail-closed 503 en producción si Redis falla en `check` |
| `apps/api/app/core/security.py` | Nuevo `secrets_equal` (HMAC fijo + `compare_digest`) |
| `apps/api/app/core/internal_auth.py` | Usa `secrets_equal` |
| `apps/api/app/modules/payments/providers/manual.py` | Usa `secrets_equal` |
| `apps/api/app/modules/health.py` | Liveness `/health` + readiness `/health/ready` (Postgres; Redis si backend lo requiere) |
| `apps/api/tests/test_security_hardening_v1_1.py` | Tests fail-closed/open + length mismatch → 401 |
| `apps/api/tests/test_health.py` | Test readiness |
| `.gitignore` | Ignora `.env.*` salvo `.env.example` |
| `.env.example` | Documenta AI/business + nota Redis prod |
| `docs/architecture/security-hardening-v1.md` | Actualiza política rate limit prod |

**Pruebas que demuestran el efecto:**  
`test_redis_rate_limit_fail_closed_in_production`, `test_redis_rate_limit_fail_open_outside_production`, `test_internal_secret_compare_rejects_length_mismatch_as_401`, `test_readiness_check_reports_dependencies` — incluidos en la corrida **31 passed** / suite **181 passed**.

**No corregido en esta fase (alcance/arquitectura):** provider de pago real, CI, Dockerfiles, backups, reset password, CORS/OpenAPI gates adicionales, test PG de doble checkout concurrente.

---

## 5. Bloqueos para la siguiente fase

Prioridad para **integración de pagos en sandbox** y luego operación comercial:

1. **P0 — Implementar provider de pago real (sandbox)** y registrar webhook firmado; retirar dependencia del header `X-GEMA-Payment-Secret` como control único en rutas expuestas.
2. **P0 — Definir entorno staging** con secretos fuertes, `SESSION_BACKEND=redis`, Redis autenticado/red privada, CORS HTTPS, scheduler de expire supervisado.
3. **P1 — Pipeline CI** (pytest API, ruff, typecheck/lint/test/build web) antes de merge.
4. **P1 — Dockerfiles + compose/prod** (o PaaS equivalente) para API, web y job expire; health `/ready` en probes.
5. **P1 — Backup/restore PostgreSQL** documentado y ensayado en entorno aislado (RPO/RTO).
6. **P1 — Alinear migraciones** en cada entorno (`alembic upgrade head`); procedimiento de deploy con migraciones.
7. **P2 — Ciclo de cuenta:** verificación email, reset password, política anti-enumeración, lockout opcional.
8. **P2 — Observabilidad mínima:** logs estructurados sin secretos + alerta fallos expire/webhook.
9. **P2 — Test de checkout concurrente en PostgreSQL** (dos clientes, última unidad) para cerrar F17.
10. **P2 — Gates prod adicionales:** rechazar CORS localhost; política explícita OpenAPI en prod.

---

## 6. Decisión de salida

### **APTO CON BLOQUEOS DOCUMENTADOS**

**Justificación:** La integridad comercial del checkout/reservas/pagos (con provider manual) y la autorización server-side son suficientes para **empezar el desarrollo** de la integración de pagos en sandbox. Los controles locales (181 tests + 3 PG concurrency) respaldan esa base. Persisten bloqueos **P0/P1** (provider real, ops, CI, backups, migraciones) que **impiden** declarar el sistema listo para ventas o tráfico de dinero real.

Esta decisión **no** autoriza producción comercial ni pagos reales fuera de sandbox del proveedor elegido.

---

*Informe generado en Fase 0D. Secretos reales no se incluyen. Evidencia basada en código y comandos del 2026-10-08 en entorno de desarrollo local.*
