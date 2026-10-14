# GEMA Technology — Reservation Scheduler (Fase 0B / 0B.1)

**Última actualización:** 2026-10-08  
**Estado:** Implementación auditada y verificada de extremo a extremo en este entorno. **No** declara producción comercial lista.

---

## 1. Componentes comprobados

| Pieza | Existe | Rol verificado |
|-------|--------|----------------|
| `InventoryService.expire_due_reservations` | Sí | `pg_advisory_xact_lock` (Postgres), `SELECT … FOR UPDATE`, claim atómico ACTIVE→EXPIRED, cancel PENDING_PAYMENT |
| `POST /api/v1/internal/reservations/expire` | Sí | Auth `X-GEMA-Internal-Secret` vía `verify_internal_job_secret` (`hmac.compare_digest`) |
| `apps/api/app/scripts/expire_reservations.py` | Sí | Caller HTTP one-shot / `--loop`; códigos de salida; no loguea el secreto |
| `infrastructure/jobs/expire-reservations-loop.sh` | Sí | Loop `curl` + `sleep`; falla sin tumbar el proceso; no imprime el secreto |
| Compose `reservation-expire` (profile `scheduler`) | Sí | Imagen `curlimages/curl`; secreto solo por env; script montado en `/job.sh` |
| Librería in-process (APScheduler/Celery) | **No** | Correcto: no se añade |

```text
cron / systemd / compose sidecar / python --loop
  → POST /api/v1/internal/reservations/expire
  → Header X-GEMA-Internal-Secret  (= INTERNAL_JOB_SECRET del API)
  → InventoryService.expire_due_reservations
       · pg_advisory_xact_lock(742653601) en PostgreSQL
       · SELECT … FOR UPDATE en reservas / órdenes / inventario
       · ACTIVE ∧ expires_at ≤ now → EXPIRED + release stock
       · PENDING_PAYMENT → CANCELLED (claim atómico)
```

### Qué depende de configuración externa

| Dependencia | Notas |
|-------------|-------|
| API alcanzable en `API_ORIGIN` | Compose **no** empaqueta el API; el sidecar asume uvicorn (u otro) fuera del profile |
| `INTERNAL_JOB_SECRET` idéntico en caller y API | Si difieren → HTTP 401; el endpoint no se desactiva |
| PostgreSQL | Semántica de advisory lock solo en Postgres; SQLite hace no-op del lock |
| Profile `scheduler` | Opt-in: `docker compose --profile scheduler up -d` |
| `RESERVATION_EXPIRE_ENABLED` | Solo apaga **caller/loop**; el endpoint interno sigue activo |

---

## 2. Pruebas realmente ejecutadas (2026-10-08)

### 2.1 Suite unitaria / SQLite (pytest)

```text
apps/api$ python -m pytest tests/test_expire_reservations_script.py \
  tests/test_reservation_lifecycle.py \
  tests/test_reservation_expire_postgres.py -v
→ 25 passed
```

| Archivo | Resultado | Qué cubre |
|---------|-----------|-----------|
| `tests/test_expire_reservations_script.py` | 6 passed | Éxito HTTP, 401, unreachable, **timeout**, `ENABLED=false`, secreto faltante; secreto ausente en logs |
| `tests/test_reservation_lifecycle.py` | 16 passed | Ciclo de vida, idempotencia, auth del endpoint, concurrencia en SQLite file DB |
| `tests/test_reservation_expire_postgres.py` | 3 passed | Contra **PostgreSQL 16 real** (`localhost:5433`) |

**Limitación SQLite (documentada, no simulada como Postgres):**  
`_acquire_expire_job_lock` es no-op fuera de `postgresql`. Las pruebas de lifecycle en SQLite demuestran claim atómico + invariantes de stock, **no** la semántica de `pg_advisory_xact_lock`.

### 2.2 Integración PostgreSQL (ejecutada)

Entorno: contenedor `gema-postgres` healthy, `POSTGRES_PORT=5433`.

| Prueba | Resultado |
|--------|-----------|
| `test_pg_advisory_lock_serializes_overlapping_holders` | **PASS** — segunda conexión bloqueada hasta commit de la primera |
| `test_pg_concurrent_expire_does_not_double_release` | **PASS** — dos workers: `expired_reservations` = `[0,1]`; stock sin doble release |
| `test_pg_expire_idempotent_second_pass` | **PASS** — segunda pasada `expired=0`, `cancelled=0` |

### 2.3 Caller HTTP (ejecutado)

| Escenario | Exit code | Evidencia |
|-----------|-----------|-----------|
| API 200 (live `http://127.0.0.1:8000`) | 0 | `reservation expire ok expired=0 cancelled=0` |
| HTTP 401 (secreto incorrecto) | 1 | `failed http=401` — secreto no en log |
| API inaccesible (`URLError`) | 1 | unit + mock |
| Timeout | 1 | **Defect fix:** `TimeoutError` ahora se captura (antes tumbaba el proceso); live hang server + unit |
| `INTERNAL_JOB_SECRET` ausente | 1 | `INTERNAL_JOB_SECRET is required` |
| `RESERVATION_EXPIRE_ENABLED=false` | 0 | `reservation expire disabled` |

### 2.4 Docker Compose profile `scheduler` (ejecutado)

| Chequeo | Resultado |
|---------|-----------|
| `docker compose config --quiet` | OK (sintaxis válida) |
| `docker compose config --profiles` | `scheduler` |
| Imagen `curlimages/curl:8.12.1` | Sin `INTERNAL_JOB_SECRET` en `Config.Env` de la imagen |
| Secreto | Solo via `environment:` / `.env` / shell env — **no** en imagen, script ni logs |
| Sidecar con `API_ORIGIN=http://host.docker.internal:8000` + secreto coincidente | **ok http=200** `expired_reservations=2, cancelled_orders=2` (holds ACTIVE vencidos preexistentes en la BD de desarrollo) |
| Sidecar con secreto desincronizado | `failed http=401`, loop continúa, **NO_SECRET_IN_LOGS** |

**Config efectiva observada con el `.env` actual del repo (sin overrides):**

| Variable | Valor efectivo | Impacto |
|----------|----------------|---------|
| `API_ORIGIN` | `http://localhost:8000` (desde `.env`) | Dentro del contenedor `localhost` **no** es el host → fallaría el reachability |
| `INTERNAL_JOB_SECRET` | `""` (ausente en `.env`) | El shell sale con error `INTERNAL_JOB_SECRET is required` |
| Default Compose sin `.env` | `http://host.docker.internal:8000` | Correcto para API en el host |

Por tanto: el profile está **bien definido**, y en este entorno se demostró funcional **solo** al inyectar `INTERNAL_JOB_SECRET` y `API_ORIGIN=http://host.docker.internal:8000`. Con el `.env` crudo del repo el sidecar **no** arrancaría correctamente.

### 2.5 Automatización / loop (ejecutado)

| Chequeo | Resultado |
|---------|-----------|
| Intervalo shell (`INTERVAL=2`) | ~3 intentos en ~5.6s ante API inaccesible → `sleep` respetado |
| Error HTTP/curl no termina el proceso | Continúa tras `failed http=000` / `401` |
| Python `--loop` tras fallo | `run_once` retorna 1; `time.sleep(interval)` se ejecuta (probado con mock) |
| `RESERVATION_EXPIRE_ENABLED=false` (shell) | exit 0, mensaje disabled |
| `RESERVATION_EXPIRE_ENABLED=false` (python) | exit 0 |

---

## 3. Defecto corregido en esta verificación

**Timeout del caller:** `urllib.request.urlopen(..., timeout=…)` lanza `TimeoutError` (built-in), que **no** es subclase de `urllib.error.URLError`. Antes del fix el timeout propagaba y mataba el proceso (y el `--loop`).

- Fix en `apps/api/app/scripts/expire_reservations.py`: capturar `TimeoutError` → log seguro → exit 1.
- Cobertura: `test_run_once_timeout_does_not_log_secret` + reproducción live.

No se modificaron reglas de negocio de cart / checkout / pricing / orders.

---

## 4. Configuración

| Variable | Default | Quién la lee | Uso |
|----------|---------|--------------|-----|
| `RESERVATION_TTL_HOURS` | `24` | API (`settings`) | `expires_at` al crear/re-reservar |
| `INTERNAL_JOB_SECRET` | `dev-internal-job-secret` (API) | API + caller | Auth del job; **debe coincidir** |
| `API_ORIGIN` | `http://127.0.0.1:8000` (python) / `host.docker.internal:8000` (compose default) | Caller / Compose | Base URL del API |
| `RESERVATION_EXPIRE_ENABLED` | `true` | Caller / shell **solo** | Desactiva ejecución automática |
| `RESERVATION_EXPIRE_INTERVAL_SECONDS` | `300` | Caller / shell | Periodo del loop |

`settings.reservation_expire_*` y `settings.api_origin` en `config.py` existen para paridad con `.env.example`; el proceso FastAPI **no** programa el job.

### Desincronización caller ↔ API (riesgo real)

1. **Secreto distinto** → 401 continuo (visto en sidecar con secreto de prueba vs default del API).
2. **`API_ORIGIN` incorrecto** → unreachable / 000; el `.env` del monorepo usa `localhost:8000`, incompatible con el contenedor.
3. **`RESERVATION_EXPIRE_ENABLED=false`** solo en el caller: el endpoint sigue callable por quien tenga el secreto.
4. **Semántica `ENABLED`:** shell acepta `true`/`1`; Python también `yes`/`on` — valores como `yes` desactivan distinto según el artefacto.

### Development

1. API: `uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`
2. Asegurar en `.env` (o entorno):

```env
INTERNAL_JOB_SECRET=dev-internal-job-secret
API_ORIGIN=http://127.0.0.1:8000
RESERVATION_EXPIRE_ENABLED=true
RESERVATION_EXPIRE_INTERVAL_SECONDS=300
```

3. One-shot / loop en host:

```bash
cd apps/api
python -m app.scripts.expire_reservations
python -m app.scripts.expire_reservations --loop
```

4. Sidecar Compose (API en el host):

```bash
# Obligatorio: secreto + origen alcanzable desde el contenedor
set INTERNAL_JOB_SECRET=dev-internal-job-secret   # PowerShell: $env:INTERNAL_JOB_SECRET=...
set API_ORIGIN=http://host.docker.internal:8000
docker compose --profile scheduler up -d
docker compose --profile scheduler logs -f reservation-expire
```

### Staging

- Programar one-shot cada **5 min** (cron / systemd timer / orquestador) → `python -m app.scripts.expire_reservations`
- o sidecar con `API_ORIGIN` a la URL **interna** del API
- `INTERNAL_JOB_SECRET` fuerte y compartido solo entre API y job runner
- Restringir el path interno en el ingress si es posible; la auth por secreto sigue siendo obligatoria

### Production

- Scheduler externo **obligatorio** (CronJob, systemd, sidecar). No confiar en lifespan/BackgroundTasks por worker.
- Concurrencia segura: advisory lock + `FOR UPDATE` + claim atómico (verificado en Postgres).
- `APP_ENV=production` rechaza placeholders de `INTERNAL_JOB_SECRET` (Security Hardening v1.1).
- Monitorizar: `reservation expire ok|failed|timeout` **sin** headers/secretos.

---

## 5. Pasos reproducibles de verificación

```bash
# 1) Unit + Postgres integration (requiere Postgres reachable vía settings/.env)
cd apps/api
python -m pytest tests/test_expire_reservations_script.py \
  tests/test_reservation_lifecycle.py \
  tests/test_reservation_expire_postgres.py -v

# 2) Caller contra API live
export INTERNAL_JOB_SECRET=dev-internal-job-secret   # debe coincidir con el API
export API_ORIGIN=http://127.0.0.1:8000
python -m app.scripts.expire_reservations
# expect exit 0

# 3) Compose profile (API en host)
export INTERNAL_JOB_SECRET=dev-internal-job-secret
export API_ORIGIN=http://host.docker.internal:8000
docker compose config --quiet
docker compose --profile scheduler up -d reservation-expire
docker compose --profile scheduler logs --tail 20 reservation-expire
# expect: ok http=200  (y ausencia del valor del secreto en logs)
docker compose --profile scheduler stop reservation-expire
```

---

## 6. Riesgos pendientes

1. **`.env` del monorepo incompleto para el scheduler:** falta `INTERNAL_JOB_SECRET`; `API_ORIGIN=localhost` rompe el sidecar. Operadores deben overridear antes de `profile scheduler`.
2. **Holds ACTIVE vencidos huérfanos:** si el scheduler no corre, el stock permanece reservado hasta el primer job exitoso (comportamiento esperado; en esta verificación el E2E liberó 2 holds antiguos de la BD de desarrollo).
3. **Compose no incluye el servicio API** — el profile solo es el caller.
4. **Sin métricas/alerting** formales (solo logs).
5. **Shell `set -eu` + `curl -sS`:** stderr de curl puede mezclarse con el mensaje `failed http=000`; el loop no se detiene, pero el ruido de log es mayor que el del caller Python.
6. No hay pasarela de pago real ni email — el scheduler solo libera holds vencidos.

---

## 7. Fuera de alcance (sin cambios)

- Cart, checkout, pricing, orders (salvo el efecto legítimo de expirar holds `PENDING_PAYMENT` vencidos).
- Reimplementación del scheduler / APScheduler / Celery.
- Commits (esta fase es verificación + documentación + fix de timeout del caller).
