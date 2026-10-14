# GEMA Technology — Staging runbook

**Audience:** operators deploying the A2 staging stack.  
**Compose file:** `docker-compose.staging.yml`  
**Env template:** `.env.staging.example` → copy to `.env.staging` (never commit).

This runbook does **not** cover production cutover (Sprint A5) or durable email outbox (A4).

---

## 1. What staging includes

| Service | Role |
|---------|------|
| `postgres` | Persistent DB (internal network only) |
| `redis` | Sessions + auth rate limit (`--requirepass`) |
| `api` | FastAPI (`APP_ENV=staging`) |
| `web` | Next.js storefront (rewrites `/api/*` → `http://api:8000`) |
| `mailpit` | SMTP sandbox + UI on host loopback |
| `reservation-expire` | Sidecar calling `POST /api/v1/internal/reservations/expire` |
| `migrate` | One-shot Alembic (`--profile migrate`) |

**Not included:** TLS certificates, DNS, public IP, PayPhone/SRI live credentials. Those are operator-owned.

---

## 2. Prerequisites (operator-supplied)

Fill before first `up`:

1. **DNS + HTTPS** for the staging storefront (and API path via same origin or proxy).
2. **Reverse proxy** (Caddy / nginx / Traefik / cloud LB) terminating TLS and forwarding:
   - `https://<staging-host>/` → `127.0.0.1:${WEB_HOST_PORT}` (default 3000)
   - Storefront already proxies `/api/*` to the API container via `API_ORIGIN=http://api:8000` (in-cluster). Prefer exposing only `web` publicly; keep `api` on loopback unless the proxy needs it.
3. **`.env.staging`** from `.env.staging.example` with strong secrets (no `change_me` / `dev-*` placeholders).
4. **PayPhone sandbox** token + storeId + webhook secret.
5. **Notificación Externa** URL in PayPhone console, HTTPS, including `?token=<PAYPHONE_WEBHOOK_SECRET>` (or configured header — see `docs/architecture/payphone-ecuador-v1.md`).

Settings gates reject staging boot if Redis is `memory`, secrets are placeholders, or `PUBLIC_APP_URL` / `CORS_ORIGINS` contain localhost.

---

## 3. First-time deploy

```bash
# From repo root on the staging host
cp .env.staging.example .env.staging
# Edit .env.staging — replace every REPLACE_* and URL placeholder

docker compose -f docker-compose.staging.yml --env-file .env.staging build

# Controlled migration (never run from every API replica)
docker compose -f docker-compose.staging.yml --env-file .env.staging --profile migrate run --rm migrate

docker compose -f docker-compose.staging.yml --env-file .env.staging up -d

docker compose -f docker-compose.staging.yml --env-file .env.staging ps
```

Verify Alembic head inside migrate/api image when needed:

```bash
docker compose -f docker-compose.staging.yml --env-file .env.staging run --rm api alembic current
docker compose -f docker-compose.staging.yml --env-file .env.staging run --rm api alembic heads
```

---

## 4. Health checks

| Check | URL / command | Expect |
|-------|---------------|--------|
| Liveness | `GET /api/v1/health` | `{"status":"ok","service":"gema-api"}` |
| Readiness | `GET /api/v1/health/ready` | `status=ok`, `postgres=ok`, `redis=ok` |
| Compose | `docker compose … ps` | `api` / `web` healthy; `reservation-expire` running |

From the host (loopback):

```bash
curl -fsS http://127.0.0.1:8000/api/v1/health
curl -fsS http://127.0.0.1:8000/api/v1/health/ready
```

Via public HTTPS (after proxy):

```bash
curl -fsS https://REPLACE_STAGING_FRONTEND_HOST/api/v1/health/ready
```

Readiness returns **503** with `checks` if Postgres or Redis is down. Responses do not include connection strings or secrets.

---

## 5. Migrations

**Rule:** one controlled job per release. Do **not** auto-migrate on API container start.

```bash
# Before starting/replacing API containers on a new revision:
docker compose -f docker-compose.staging.yml --env-file .env.staging --profile migrate run --rm migrate
```

**On failure:** leave the previous API image running if possible; inspect migrate logs; fix migration or restore DB from backup; do not force `downgrade` in staging without a written plan.

---

## 6. Reservation scheduler

- Image: `curlimages/curl` + `infrastructure/jobs/expire-reservations-loop.sh`
- Auth: header `X-GEMA-Internal-Secret` (value from `INTERNAL_JOB_SECRET`; never logged by the script)
- Target: `http://api:8000/api/v1/internal/reservations/expire`
- Interval: `RESERVATION_EXPIRE_INTERVAL_SECONDS` (default 300)
- Timeout: `RESERVATION_EXPIRE_TIMEOUT_SECONDS` (default 30)
- Restart: `restart: unless-stopped`

Logs:

```bash
docker compose -f docker-compose.staging.yml --env-file .env.staging logs -f reservation-expire
```

Look for `reservation-expire: ok http=200`. Failures print `failed http=…` without the secret.

Local alternative (host-side, API already up):

```bash
cd apps/api
python -m app.scripts.expire_reservations --loop
```

---

## 7. Redis sessions

- `SESSION_BACKEND=redis`, `AUTH_RATE_LIMIT_BACKEND=redis`, `REDIS_PASSWORD` set
- Cookie `Secure` defaults **on** for `APP_ENV=staging` (requires HTTPS)
- Session data lives in Redis keys `gema:session:*` — survives API container restart while TTL remains
- Shared Redis is what enables multi-instance session sharing (verify with ≥2 API replicas if you scale; single-replica is the compose default)

If Redis is down: session store fails hard; auth rate limiter **fail-closed** (503) in staging.

---

## 8. Email (Mailpit)

Compose wires API SMTP to `mailpit:1025` (`SMTP_USE_TLS=false`, `EMAIL_ENABLED=true`).

UI (host loopback only): `http://127.0.0.1:8025`

Expected A1 events (no durable outbox yet): `order.created`, `order.paid`, `order.shipped`.

---

## 9. PayPhone sandbox smoke

1. Configure Notificación Externa to the **public HTTPS** webhook URL.
2. Place order → pay with sandbox → confirm via webhook/sync (not browser return alone).
3. Admin: `PAID → PROCESSING → SHIPPED` and check Mailpit for shipped mail.

Do **not** use live PayPhone credentials in staging.

---

## 10. Secrets & rotation

- Store `.env.staging` only on the host (permissions `600`).
- Rotate `INTERNAL_JOB_SECRET`, `PAYPHONE_WEBHOOK_SECRET`, `REDIS_PASSWORD`, DB password independently; bounce affected containers after rotation.
- Never bake secrets into images or CI logs.

---

## 11. Common failures

| Symptom | Likely cause | Action |
|---------|--------------|--------|
| API exits on start with Settings `ValueError` | Placeholder secret / localhost CORS / memory sessions | Fix `.env.staging` |
| `/health/ready` → 503 redis | Wrong `REDIS_PASSWORD` or Redis down | Check redis logs / password |
| Scheduler `failed http=401` | Secret mismatch | Align `INTERNAL_JOB_SECRET` on api + expire |
| Scheduler `failed http=000` | API not reachable | `depends_on` / network / API crash |
| Cookies not sent | HTTP without Secure override | Use HTTPS or (lab only) `SESSION_COOKIE_SECURE=false` |
| No emails | `EMAIL_ENABLED` false / wrong SMTP | Confirm Mailpit + env |
| PayPhone never PAID | Webhook URL/secret / sandbox creds | Check API payment logs; use sync endpoint |

---

## 12. Restart / teardown

```bash
docker compose -f docker-compose.staging.yml --env-file .env.staging restart api web reservation-expire
docker compose -f docker-compose.staging.yml --env-file .env.staging down
# Destructive (wipes DB/Redis volumes):
docker compose -f docker-compose.staging.yml --env-file .env.staging down -v
```

---

## 13. Local quality gates (same as CI)

```bash
# API
cd apps/api && pip install -e ".[dev]" && ruff check app tests && pytest -q

# Web (repo root)
npm ci
npm run typecheck --workspace=apps/web
npm run lint --workspace=apps/web
npm run test --workspace=apps/web
npm run build --workspace=apps/web
```

CI workflow: `.github/workflows/ci.yml` (PR + push to main/master). Does **not** deploy.
