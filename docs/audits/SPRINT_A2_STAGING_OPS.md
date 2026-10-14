# GEMA Technology — Sprint A2: Staging y operaciones mínimas

**Fecha:** 2026-10-13 / 2026-10-14  
**Alcance:** Despliegue reproducible, gates `APP_ENV=staging`, Redis autenticado, scheduler, migraciones controladas, Docker, CI, SMTP sandbox (Mailpit), plantilla PayPhone sandbox.  
**Fuera de alcance:** Cobros reales, outbox A4, IVA/fiscal A3, reembolsos, A6 cuenta/legal, commits/deploy a producción.

---

## 1. Brechas iniciales (inspección real)

| Área | Estado antes de A2 |
|------|--------------------|
| `apps/api/Dockerfile` / `apps/web/Dockerfile` | Ausentes |
| `.github/workflows/` | Ausente |
| Compose app (API/web) | Solo Postgres/Redis + sidecar curl local |
| Redis password en Settings/cliente | No soportado |
| Gates staging | Solo `PAYPHONE_WEBHOOK_SECRET` con PayPhone |
| Cookie `Secure` auto | Solo `production` |
| Rate-limit fail-closed | Solo `production` |
| SMTP sandbox en compose | Ausente |
| `docs/ops/staging-runbook.md` | Ausente |
| Alembic head | `021_fulfillment_notify` (confirmado) |

---

## 2. Arquitectura staging final

```text
Internet → [TLS reverse proxy — operador] → 127.0.0.1:WEB_HOST_PORT (web)
                                              └─ rewrites /api/* → http://api:8000
Docker network staging_internal:
  postgres (sin puertos host)
  redis --requirepass (sin puertos host)
  api :8000 (bind 127.0.0.1)
  web :3000 (bind 127.0.0.1)
  mailpit :1025 SMTP + UI 127.0.0.1:8025
  reservation-expire → POST /api/v1/internal/reservations/expire
migrate (profile): alembic upgrade head (one-shot)
```

**HTTPS / DNS / dominio / VPS:** no inventados; documentados como requisitos del operador en el runbook.

---

## 3. Archivos creados / modificados

### Creados
- `apps/api/Dockerfile`, `apps/api/docker/entrypoint.sh`, `apps/api/.dockerignore`
- `apps/web/Dockerfile`, `apps/web/.dockerignore`
- `docker-compose.staging.yml`
- `.env.staging.example`
- `.github/workflows/ci.yml`
- `docs/ops/staging-runbook.md`
- `docs/audits/SPRINT_A2_STAGING_OPS.md` (este archivo)
- `apps/api/tests/test_staging_ops_a2.py`

### Modificados
- `apps/api/app/core/config.py` — `redis_password`, gates staging, cookie Secure en staging, `auth_rate_limit_fail_closed`
- `apps/api/app/core/redis_client.py` — password opcional
- `apps/api/app/core/rate_limit.py` — fail-closed en staging
- `infrastructure/jobs/expire-reservations-loop.sh` — `--max-time` / connect timeout
- `apps/web/next.config.ts` — `output: "standalone"`
- `.env.example` — Redis password + checklist staging
- `.gitignore` — `!.env.staging.example`
- `apps/api/tests/test_security_hardening_v1_1.py` — fail-closed staging
- `apps/api/tests/test_payphone.py` — staging Settings explícitos

---

## 4. Variables de entorno nuevas / relevantes

| Variable | Uso |
|----------|-----|
| `REDIS_PASSWORD` | Auth Redis (compose staging `--requirepass`) |
| `GEMA_STAGING_ENV_FILE` | Override path `env_file` compose (dry-run con example) |
| `API_HOST_PORT` / `WEB_HOST_PORT` / `MAILPIT_UI_PORT` | Bind loopback |
| `RESERVATION_EXPIRE_TIMEOUT_SECONDS` | Timeout curl del sidecar |
| Checklist staging en `.env.staging.example` | `APP_ENV=staging`, Redis sessions, URLs HTTPS, PayPhone sandbox, Mailpit |

---

## 5. Procedimiento de despliegue (resumen)

1. Copiar `.env.staging.example` → `.env.staging` y completar secretos + URLs HTTPS reales.  
2. `docker compose -f docker-compose.staging.yml --env-file .env.staging build`  
3. `… --profile migrate run --rm migrate` (**antes** de levantar/reemplazar API).  
4. `… up -d`  
5. Configurar reverse proxy TLS → `127.0.0.1:WEB_HOST_PORT`.  
6. Configurar PayPhone Notificación Externa HTTPS + SMTP (Mailpit ya cableado).  

Detalle: `docs/ops/staging-runbook.md`.

---

## 6. Comandos ejecutados y resultados reales

| Comando | Resultado |
|---------|-----------|
| `pytest tests/test_staging_ops_a2.py -q` | **10 passed** |
| `pytest tests/test_staging_ops_a2.py tests/test_security_hardening_v1_1.py tests/test_health.py -q` | **36 passed, 5 skipped** (~263s; skips Redis no disponible / opcionales) |
| `docker compose … --env-file .env.staging.example config --quiet` (con `GEMA_STAGING_ENV_FILE=.env.staging.example`) | **exit 0** |
| `npm run typecheck --workspace=apps/web` | **exit 0** |
| `docker build` API/web en host staging | **No ejecutado** (sin host staging en esta sesión) |
| PayPhone sandbox E2E / SMTP bandeja real | **Pendiente validación externa** |
| Scheduler 24h en vivo | **Pendiente validación externa** |
| Multi-réplica API E2E | **No ejecutado** — soporte por diseño Redis; no declarado como E2E validado |

---

## 7. Criterios de aceptación — estado

| Criterio | Estado |
|----------|--------|
| Config staging reproducible (compose + env template) | **Implementado** |
| Dockerfiles API/web | **Implementado** (build imagen no corrido aquí) |
| Postgres/Redis sin exposición a Internet en compose staging | **Implementado** |
| Redis sessions + RL + password | **Implementado** + tests unitarios gates |
| Scheduler con secret no logueado + timeout | **Implementado** |
| Migraciones one-shot (no por réplica) | **Implementado** + documentado |
| Health / ready | **Ya existía**; documentado para staging |
| CI GitHub Actions | **Implementado** (no corrido en GitHub en esta sesión) |
| PayPhone/SMTP sandbox cableados en plantilla | **Implementado**; E2E **pendiente externo** |
| Gates staging (no placeholders, no localhost CORS/URL) | **Implementado** + tests |
| Sin IVA/outbox/refunds/prod deploy | **Cumplido** |

---

## 8. Pendientes que requieren intervención humana

1. Host/VPS, DNS y certificados TLS.  
2. Archivo `.env.staging` real (secretos).  
3. Credenciales **sandbox** PayPhone + URL Notificación Externa.  
4. `docker compose build/up` + migrate en ese host.  
5. Smoke: checkout → pago sandbox → PAID → fulfillment → correo en Mailpit.  
6. Confirmar CI verde en el remoto GitHub tras push.  
7. (Opcional) Escalar a 2 réplicas API y verificar sesión compartida.

---

## 9. Riesgos

- Rate-limit / sessions fallan cerrados si Redis cae en staging (intencional).  
- Sin outbox A4: emails pueden perderse si el proceso muere tras commit.  
- OpenAPI sigue habilitado por defecto en staging salvo `OPENAPI_ENABLED=false` (recomendado en example).  
- Confirmación manual de pagos sigue permitida en staging si no se fija `ALLOW_MANUAL_PAYMENT_CONFIRM=false`.  
- Imágenes Docker no verificadas aún con build real en este entorno.

---

## 10. Decisión

### **APTO para preparar validación integral en staging** (artefactos listos)

Condiciones: el operador completa DNS/TLS/secretos/sandbox y ejecuta el runbook.

### **NO APTO para declarar staging validado E2E**

Falta ejecución real en host con PayPhone sandbox + Mailpit + scheduler observado.

### **NO APTO para producción / cobro real**

Bloqueado por A3 (fiscal), A4 (email durable), A5 (cutover).
