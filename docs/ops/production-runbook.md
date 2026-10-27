# GEMA Technology — Production runbook

**Audience:** operators performing cutover after A3 fiscal alignment and A2 staging validation.  
**Compose:** `docker-compose.production.yml`  
**Env template:** `.env.production.example` → `.env.production` (never commit).

This runbook packages production ops. It does **not** by itself authorize live charges until the checklist below is complete. **Email durable (A4)** is deferred — keep `EMAIL_ENABLED=false` until outbox/SMTP are validated.

---

## 1. Preconditions

- [ ] Staging smoke OK (PayPhone sandbox, fulfillment, scheduler, Redis sessions).
- [ ] Sprint A3 opción A: `COMMERCE_TAX_ENABLED=true` — checkout total = PayPhone = factura.
- [ ] DNS + TLS certificates for the public storefront host.
- [ ] Live PayPhone token/storeId + Notificación Externa HTTPS URL.
- [ ] SRI production certificate (`.p12`) + `SRI_CERT_PASSWORD` (operator).
- [ ] Strong unique secrets (no `change_me` / `dev-*` / `REPLACE_*` left in `.env.production`).
- [ ] Backup destination writable; restore procedure read once.

---

## 2. First deploy

```bash
cp .env.production.example .env.production
# Edit every REPLACE_* and HTTPS host

docker compose -f docker-compose.production.yml --env-file .env.production build

# The API container also runs `alembic upgrade head` on start (advisory lock).
# This job applies revisions before new replicas boot.
docker compose -f docker-compose.production.yml --env-file .env.production \
  --profile migrate run --rm migrate

# First SUPER_ADMIN (idempotent if email already exists)
# Requires SEED_ADMIN_EMAIL / SEED_ADMIN_PASSWORD in .env.production
# Default email in the template: gematechnology17@gmail.com
docker compose -f docker-compose.production.yml --env-file .env.production \
  run --rm api python -m app.scripts.seed

docker compose -f docker-compose.production.yml --env-file .env.production up -d
docker compose -f docker-compose.production.yml --env-file .env.production ps
```

After the admin exists: rotate or remove `SEED_ADMIN_PASSWORD` from the host env (keep the account; do not leave a long-lived seed password on disk longer than needed).

Login: `https://<prod-host>/login` with `SEED_ADMIN_EMAIL` and the password you set.

Reverse proxy (operator): `https://<prod-host>/` → `127.0.0.1:${WEB_HOST_PORT}`.

Dry-run compose against the example file:

```bash
GEMA_PROD_ENV_FILE=.env.production.example \
  docker compose -f docker-compose.production.yml --env-file .env.production.example config --quiet
```

---

## 3. Health

```bash
curl -fsS http://127.0.0.1:8000/api/v1/health
curl -fsS http://127.0.0.1:8000/api/v1/health/ready
# Via public HTTPS after proxy:
curl -fsS https://REPLACE_PRODUCTION_FRONTEND_HOST/api/v1/health/ready
```

Expect `postgres=ok`, `redis=ok`. No secrets in response bodies.

---

## 4. Migrations

The API image runs `alembic upgrade head` on start, behind a Postgres advisory lock. On Compose you can still apply revisions before replacing replicas:

```bash
docker compose -f docker-compose.production.yml --env-file .env.production \
  --profile migrate run --rm migrate
```

On failure: keep previous API image; inspect logs; do not blind `downgrade` without a written plan.

---

## 5. Backup and restore

### Backup

```bash
# Discover container name:
docker compose -f docker-compose.production.yml --env-file .env.production ps postgres

chmod +x infrastructure/ops/pg-backup.sh
./infrastructure/ops/pg-backup.sh <postgres_container_name> /var/backups/gema
```

Schedule via cron/systemd (operator), e.g. daily. Retain off-host copies.

### Restore (isolated rehearsal — do not run against live without maintenance window)

```bash
gunzip -c /var/backups/gema/gema-YYYYMMDDTHHMMSSZ.sql.gz \
  | docker exec -i <postgres_container_name> \
    sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

Document RPO/RTO targets for the business (suggested starting point: RPO ≤ 24h with daily dumps; RTO = time to restore + DNS/proxy verification).

---

## 6. Scheduler

`reservation-expire` sidecar posts to `http://api:8000/api/v1/internal/reservations/expire` with `X-GEMA-Internal-Secret`. Logs omit the secret. `restart: unless-stopped`.

```bash
docker compose -f docker-compose.production.yml --env-file .env.production logs -f reservation-expire
```

---

## 7. Fiscal (opción A)

- `COMMERCE_TAX_ENABLED=true`, `COMMERCE_TAX_RATE=0.15`
- New orders: PayPhone amount = `order.total` including IVA
- FACTURA emission refuses to start if tax is disabled in production
- Do **not** rewrite historical orders created under tax-off

---

## 8. Email (deferred)

`EMAIL_ENABLED=false` by default in `.env.production.example`. A1 hooks exist but A4 outbox/retries are not in this cutover. Enable SMTP only after a dedicated email sprint.

---

## 9. Go-live smoke (operator)

1. Place a **low-amount** live order.
2. Confirm PAID via webhook/sync (not browser return alone).
3. Admin fulfillment PROCESSING → SHIPPED.
4. Emit FACTURA in SRI producción (or pruebas if still gated).
5. Verify totals: checkout = payment = factura.
6. Confirm scheduler still logging `ok http=200`.

Rollback: set maintenance page on proxy; scale api/web down; restore DB from last good dump if data corruption; rotate PayPhone webhook secret if leaked.

---

## 10. Common failures

| Symptom | Action |
|---------|--------|
| Settings `ValueError` on boot | Fix placeholders / localhost CORS / memory sessions |
| `/ready` redis unavailable | Check `REDIS_PASSWORD` |
| FACTURA 400 about `COMMERCE_TAX_ENABLED` | Set tax true (opción A) |
| Scheduler 401 | Align `INTERNAL_JOB_SECRET` |
| No emails | Expected while `EMAIL_ENABLED=false` |

---

## 11. Local quality gates (same as CI)

```bash
cd apps/api && ruff check app tests && pytest -q
npm ci && npm run typecheck --workspace=apps/web && npm run lint --workspace=apps/web \
  && npm run test --workspace=apps/web && npm run build --workspace=apps/web
```
