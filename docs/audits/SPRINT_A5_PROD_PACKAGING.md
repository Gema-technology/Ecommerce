# GEMA Technology — Sprint A5 (parcial): empaquetado de producción

**Fecha:** 2026-10-14  
**Alcance:** Compose/env/runbook de producción, backup script, gate CORS localhost en production.  
**Fuera de alcance:** Cutover live, DNS/TLS reales, cobros reales, outbox email (A4), A6.

Complementa A3 (IVA opción A) y reutiliza el patrón A2.

---

## 1. Artefactos

| Artefacto | Rol |
|-----------|-----|
| `docker-compose.production.yml` | postgres, redis (auth), api, web, migrate, reservation-expire — **sin Mailpit** |
| `.env.production.example` | `APP_ENV=production`, tax on, email off, placeholders `REPLACE_*` |
| `docs/ops/production-runbook.md` | Deploy, migrate, health, backup/restore, smoke |
| `infrastructure/ops/pg-backup.sh` | `pg_dump` → `.sql.gz` |
| `config.py` | Rechaza CORS localhost en production |

---

## 2. Comandos verificados en esta sesión

| Comando | Resultado |
|---------|-----------|
| `pytest tests/test_tax_fiscal_consistency.py` | **6 passed** |
| `pytest tests/test_sri.py` | **12 passed** |
| `pytest` fiscal + security + staging (− multiprocess) | **41 passed, 4 skipped** |
| `docker compose -f docker-compose.production.yml … config --quiet` | **exit 0** |
| `npm run typecheck --workspace=apps/web` | **exit 0** |
| Deploy/build en host prod | **Pendiente operador** |
| Backup/restore ensayado | **Pendiente operador** (script entregado) |

---

## 3. Decisión

### **APTO empaquetado producción (artefactos listos)**

Operador puede seguir el runbook cuando tenga host, secretos y PayPhone/SRI live.

### **NO APTO para declarar go-live / cobro real**

Faltan: host+TLS, secretos reales, smoke live, email durable (A4), restore ensayado.
