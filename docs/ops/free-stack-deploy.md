# Free demo stack — Vercel + Supabase + Upstash + Render

Deploy GEMA at **$0** for demos (not hard production).  
Template env: [`.env.free-demo.example`](../../.env.free-demo.example).

```text
Browser → Vercel (Next.js)  --rewrite /api/*→  Render (FastAPI)
                                      │
                         ┌────────────┼────────────┐
                         ▼            ▼            ▼
                    Supabase PG   Upstash Redis   GitHub cron (expire)
```

**Limits:** Render free sleeps after ~15 min idle (first request is slow). Supabase/Upstash free tiers have storage/request caps. Use `APP_ENV=staging` + `PAYMENT_DEFAULT_PROVIDER=manual` until you add PayPhone sandbox.

---

## 1. Supabase (Postgres)

1. Create project at [supabase.com](https://supabase.com).
2. **Project Settings → Database → Connection string → URI**.
3. Prefer **Transaction** pooler (`…pooler.supabase.com:6543…`).
4. Copy URI → you will set `DATABASE_URL` on Render.
5. Password must not be a local default (`change_me`, etc.).

The API normalizes `postgres://` → `postgresql+psycopg://` and adds `sslmode=require` for `*.supabase.co`.

---

## 2. Upstash (Redis)

1. Create a Redis database at [upstash.com](https://upstash.com).
2. Copy the **Redis URL** (`rediss://default:…@….upstash.io:6379`).
3. Set on Render as `REDIS_URL`.
4. Keep `SESSION_BACKEND=redis` and `AUTH_RATE_LIMIT_BACKEND=redis`.

Do **not** use the REST API URL/token for this app.

---

## 3. Render (API)

1. Connect GitHub repo `Gema-technology/Ecommerce`.
2. Use Blueprint [`render.yaml`](../../render.yaml) **or** Web Service:
   - Runtime: **Docker**
   - Dockerfile path: `apps/api/Dockerfile`
   - Context: `apps/api`
   - Plan: **Free**
   - Health: `/api/v1/health`
3. Set env vars from `.env.free-demo.example` (at least):

| Variable | Notes |
|----------|--------|
| `APP_ENV` | `staging` |
| `DATABASE_URL` | Supabase URI |
| `REDIS_URL` | Upstash `rediss://…` |
| `PUBLIC_APP_URL` | Vercel URL (update after step 4) |
| `CORS_ORIGINS` | Same as `PUBLIC_APP_URL` |
| `INTERNAL_JOB_SECRET` | Long random |
| `PAYMENT_WEBHOOK_SECRET` | Long random |
| `PAYMENT_DEFAULT_PROVIDER` | `manual` |
| `SESSION_BACKEND` | `redis` |
| `SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD` | For seed only |

4. Deploy → note public URL: `https://gema-api-xxxx.onrender.com`.

### Migrate + seed (once)

Render **Shell** on the service:

```bash
alembic upgrade head
python -m app.scripts.seed
```

---

## 4. Vercel (Web)

1. Import the same GitHub repo.
2. **Root Directory:** `apps/web` (uses [`apps/web/vercel.json`](../../apps/web/vercel.json)).
3. Framework: Next.js.
4. Env vars (**Production + Preview**, include **Build**):

| Variable | Value |
|----------|--------|
| `API_ORIGIN` | `https://gema-api-xxxx.onrender.com` (no trailing slash) |

`next.config.ts` rewrites `/api/*` using `API_ORIGIN` at **build** time — set it before building, and **redeploy** if the Render URL changes.

5. Deploy → note `https://….vercel.app`.
6. Back on Render, set `PUBLIC_APP_URL` and `CORS_ORIGINS` to that Vercel URL; redeploy API.

---

## 5. Reservation expire (GitHub Actions, free)

Workflow: [`.github/workflows/expire-reservations.yml`](../../.github/workflows/expire-reservations.yml).

Repo **Settings → Secrets**:

| Secret | Value |
|--------|--------|
| `FREE_DEMO_API_ORIGIN` | Render API URL |
| `FREE_DEMO_INTERNAL_JOB_SECRET` | Same as Render `INTERNAL_JOB_SECRET` |

Runs every ~15 minutes (or **Actions → Expire reservations → Run workflow**).

---

## 6. Smoke checklist

1. Open Vercel URL → home loads.
2. Wait for Render wake if cold → `/api/v1/health` via storefront proxy.
3. Register / login (admin from seed).
4. Add to cart → checkout with **manual** payment path.
5. Confirm cookie session survives refresh (HTTPS + `Secure`).

---

## Order of operations (short)

1. Supabase + Upstash  
2. Render API + migrate/seed  
3. Vercel web with `API_ORIGIN`  
4. Fix `PUBLIC_APP_URL` / `CORS_ORIGINS` on Render  
5. GitHub secrets for expire cron  

---

## When you outgrow free

Move to Railway (all-in-one) or paid Render + keep Supabase, and switch `APP_ENV=production` + PayPhone live using `.env.production.example`.
