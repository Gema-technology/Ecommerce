# GEMA Technology — Plan de sprints hacia producción

**Fecha:** 2026-10-13  
**Estado de partida:** A0 (remediación crítica) + A1 (email/fulfillment) cerrados en sandbox.  
**Decisión global:** **No apto para cobro real** hasta cerrar P0 de A2–A3 y cutover de A5.  
**Referencias:** `SPRINT_A0_CRITICAL_REMEDIATION.md`, `SPRINT_A1_EMAIL_FULFILLMENT.md`, `PHASE_0D_BACKEND_PRODUCTION_READINESS.md`.

---

## 0. Mapa ejecutivo

| Sprint | Nombre | Objetivo | Criterio de salida | Dependencias |
|--------|--------|----------|--------------------|--------------|
| **A2** | Staging & ops mínimo | Entorno staging prod-like + CI + deploy reproducible | Staging estable; scheduler + Redis + PayPhone sandbox E2E | A0/A1 |
| **A3** | Fiscal & totales | Una sola política IVA en checkout + pago + factura | Totales alineados; decisión A/B/C aplicada y testeada | Decisión contable |
| **A4** | Email durable & postventa | Outbox SMTP + política cancel/refund + tracking mínimo | Correos confiables; cancel post-PAID definida | A1, SMTP staging (A2) |
| **A5** | Cutover producción | HTTPS, backups, SMTP/SRI/PayPhone prod, go-live controlado | Primer cobro real supervisado OK | A2–A4 |
| **A6** | Madurez cuenta & legal | Reset password, verificación email, páginas legales | Cuenta segura + compliance básico UX | A5 o paralelo tardío A4 |

```text
A0 ──► A1 ──► A2 (ops/staging) ──► A3 (fiscal) ──► A4 (email durable / postventa)
                      │                 │                    │
                      └─────────────────┴────────────────────┴──► A5 (cutover prod)
                                                                      │
                                                              A6 (cuenta/legal) ──► continuo
```

**Regla:** no activar `APP_ENV=production` con dinero real hasta gate de A5.

---

## A2 — Staging & ops mínimo

**Meta:** Poder validar el flujo comercial completo fuera de la laptop del desarrollador, con secretos y Redis como en producción.

### Alcance

| ID | Tarea | Detalle | Prioridad |
|----|-------|---------|-----------|
| A2-1 | Entorno staging | VPS/PaaS o compose prod; `APP_ENV=staging`; secretos fuertes; `CORS_ORIGINS` HTTPS; `PUBLIC_APP_URL` | P0 |
| A2-2 | Redis prod-like | `SESSION_BACKEND=redis`, `AUTH_RATE_LIMIT_BACKEND=redis`; `requirepass` / red privada; no exponer 6379 a Internet | P0 |
| A2-3 | Scheduler reservas | Profile `scheduler` o systemd/cron apuntando a API staging; verificación de holds vencidos | P0 |
| A2-4 | Migraciones en deploy | Procedimiento `alembic upgrade head` (hoy head `021_fulfillment_notify`); checklist pre-release | P0 |
| A2-5 | Dockerfiles API + web | Imágenes reproducibles; health/ready probes; compose/prod o manifiesto PaaS | P0 |
| A2-6 | CI GitHub Actions | Gate merge: `pytest` + `ruff` (API); `typecheck` + `lint` + `test` + `build` (web) | P0 |
| A2-7 | PayPhone sandbox en staging | Token/storeId staging; `PAYPHONE_WEBHOOK_SECRET`; Notificación Externa → HTTPS staging | P0 |
| A2-8 | SMTP sandbox | Mailpit/Mailhog/SES sandbox + `EMAIL_ENABLED=true`; validar bandeja created/paid/shipped | P1 |
| A2-9 | Gates staging | Política: staging no usa placeholders; documentar qué gates aplica `APP_ENV=staging` vs `production` | P1 |
| A2-10 | Runbook ops | Arranque, secrets rotation, restart scheduler, smoke `/health` + `/health/ready` | P1 |

### Fuera de alcance A2

IVA definitivo, outbox durable, Docker de backup automático ensayado (arranque en A5), páginas legales, reset password.

### DoD (Definition of Done)

1. Staging accesible por HTTPS con cookie `Secure` usable.
2. Login/sesión multi-instancia vía Redis (o al menos un worker + Redis store).
3. Job expire corre sin intervención manual ≥ 24 h de prueba.
4. CI verde en PR de ejemplo.
5. Compra sandbox PayPhone → PAID → fulfillment → correos visibles en SMTP sandbox.
6. Doc de runbook en `docs/` (ops staging).

### Evidencia esperada

- Workflow `.github/workflows/ci.yml`
- `apps/api/Dockerfile`, `apps/web/Dockerfile` (o equivalente PaaS)
- `docs/ops/staging-runbook.md` (nuevo)
- Informe corto `docs/audits/SPRINT_A2_STAGING_OPS.md`

---

## A3 — Fiscal & totales coherentes

**Meta:** Eliminar la divergencia checkout/pago vs factura SRI antes de cualquier cobro real.

### Decisión previa (bloqueante — negocio/contador)

Elegir **una** opción (ya documentada en A0):

| Opción | Checkout / PayPhone | Factura SRI | Notas |
|--------|---------------------|-------------|-------|
| **A** | `COMMERCE_TAX_ENABLED=true` (precio + IVA) | IVA alineado con orden | Cliente paga lo mismo que el fiscal |
| **B** | Precio con IVA incluido; desglose fiscal | Base = total/1.15 | Requiere validación contable |
| **C** | Sin IVA en factura (nota de venta / régimen) | Según `tax_regime` | Solo si aplica legalmente |

**Hasta decidir: no cambiar** totales históricos ni forzar tax en producción.

### Alcance (tras decisión)

| ID | Tarea | Detalle | Prioridad |
|----|-------|---------|-----------|
| A3-1 | Acta de decisión | Documento firmado/aprobado (opción A/B/C + fecha) | P0 |
| A3-2 | Checkout + totales | `commerce/tax.py` / `totals.py` según opción | P0 |
| A3-3 | PayPhone amount | Cobro = `order.total` coherente; tests de contraste de centavos | P0 |
| A3-4 | Emisión SRI | `_emit_factura` alineado; eliminar forzado 15% “divergente” si ya no aplica | P0 |
| A3-5 | UI checkout/orden | Mostrar desglose correcto (subtotal/IVA/total) | P0 |
| A3-6 | Tests de coherencia | Extender `test_tax_fiscal_consistency.py`; casos borde shipping | P0 |
| A3-7 | Migración de política | Solo hacia adelante; no reescribir órdenes pagadas salvo plan contable explícito | P1 |
| A3-8 | Admin config | Si aplica: flag/tax rate visibles y auditables | P2 |

### Fuera de alcance A3

Retenciones, crédito tributario avanzado, multi-tarifa IVA por producto (salvo que la decisión lo exija).

### DoD

1. Para una orden nueva de prueba: `order.total` == monto cobrado == total factura (o desglose B documentado y correcto).
2. Suite fiscal verde; smoke SRI ambiente pruebas con secuencial nuevo.
3. Informe `docs/audits/SPRINT_A3_FISCAL_ALIGNMENT.md` con opción elegida y evidencia numérica.

---

## A4 — Email durable & postventa

**Meta:** Correos no se pierden si el proceso muere; operación post-pago operable.

### Alcance

| ID | Tarea | Detalle | Prioridad |
|----|-------|---------|-----------|
| A4-1 | Outbox en misma TX | Insert `notification_dispatches` `pending` junto al cambio de orden (propuesta A1) | P0 |
| A4-2 | Worker/cron dispatch | `python -m app.scripts.dispatch_notifications` (+ compose/cron); backoff en `failed` | P0 |
| A4-3 | Idempotencia | Mantener unique `(order, event, channel)`; semántica `accepted` ≠ entregado | P0 |
| A4-4 | Política cancel/refund post-PAID | Decisión negocio + transiciones + restock; sin inventar reembolsos PayPhone sin API | P0 |
| A4-5 | UI/admin cancel post-pago | Flujo mínimo según política | P1 |
| A4-6 | Tracking mínimo | Campos `carrier` / `tracking_number` (o note estructurado) + email shipped | P1 |
| A4-7 | Alertas fallos SMTP | Log/métrica o email interno si `failed` supera umbral | P2 |

### Fuera de alcance A4

Celery/RQ a escala; marketing email; SMS.

### DoD

1. Matar el proceso tras commit comercial y antes del send → el worker recupera y envía.
2. Tests de outbox + reintento.
3. Política post-PAID escrita y reflejada en código (aunque sea “solo admin, sin refund automático”).
4. Informe `docs/audits/SPRINT_A4_EMAIL_POSTSALE.md`.

---

## A5 — Cutover producción

**Meta:** Primer entorno `production` con cobro real supervisado y rollback claro.

### Precondiciones (gate)

- [ ] A2 DoD completo  
- [ ] A3 DoD completo  
- [ ] A4-1..A4-3 hechos (outbox); A4-4 política al menos documentada y aplicada en código mínimo  
- [ ] Checklist `.env.example` sección Production cumplida  

### Alcance

| ID | Tarea | Detalle | Prioridad |
|----|-------|---------|-----------|
| A5-1 | Infra prod | Hosting, TLS, DNS, `CORS_ORIGINS`, `PUBLIC_APP_URL` | P0 |
| A5-2 | Secrets prod | Postgres, Redis, `INTERNAL_JOB_SECRET`, PayPhone, SMTP, SRI cert password | P0 |
| A5-3 | PayPhone producción | Token/storeId live; Notificación Externa URL prod; prueba monto bajo | P0 |
| A5-4 | SMTP producción | Proveedor real (SES/SendGrid/SMTP ISP); SPF/DKIM; `EMAIL_ENABLED=true` | P0 |
| A5-5 | SRI producción | Cert vigente, ambiente prod, secuenciales; 1 factura de prueba controlada | P0 |
| A5-6 | Backup/restore | `pg_dump` programado; restore ensayado en entorno aislado; RPO/RTO escritos | P0 |
| A5-7 | Observabilidad mínima | Logs sin secretos; alerta expire/webhook/SMTP/SRI; opcional Sentry | P1 |
| A5-8 | Gates prod | `OPENAPI` off; sin confirm manual; CORS sin localhost; cookie Secure | P0 |
| A5-9 | Go-live controlado | 1–3 pedidos reales supervisados; checklist smoke; plan rollback (feature flag provider / maintenance) | P0 |
| A5-10 | Runbook prod | Incidentes pago, SRI, email, expire; contactos; rotación secretos | P1 |

### Fuera de alcance A5

Marketing, SEO avanzado, app móvil, multi-almacén.

### DoD

1. `APP_ENV=production` arranca sin rechazos de Settings.
2. Pedido real: pago confirmado por webhook/sync → email → fulfillment → factura válida.
3. Backup restaurable demostrado al menos una vez.
4. Informe `docs/audits/SPRINT_A5_CUTOVER.md` con “APTO / NO APTO” explícito.

### Criterio “APTO para ventas”

Solo si el informe A5 declara **APTO** y no quedan P0 abiertos de A2–A5.

---

## A6 — Madurez cuenta & legal

**Meta:** Confianza del cliente y superficie legal mínima para tráfico público.

### Alcance

| ID | Tarea | Detalle | Prioridad |
|----|-------|---------|-----------|
| A6-1 | Reset password | Flujo email + token de un uso + rate limit | P1 |
| A6-2 | Verificación email | Exigir o incentivar `email_verified` según política | P1 |
| A6-3 | Anti-enumeración | Registro/login sin filtrar existencia de email (o respuesta uniforme) | P2 |
| A6-4 | Lockout por cuenta | Tras N fallos (además de RL por IP) | P2 |
| A6-5 | Términos / privacidad / cookies | Rutas storefront + enlace en registro/checkout | P1 |
| A6-6 | Session idle / renew | Renovar TTL en actividad o documentar TTL absoluto 7d | P2 |
| A6-7 | E2E crítico | Playwright/Cypress: browse → pay sandbox → orden | P2 |

### DoD

1. Usuario puede recuperar acceso sin admin.
2. Páginas legales enlazadas en checkout/registro.
3. Informe breve o actualización de `project-status-v1.md`.

---

## Backlog continuo (no bloquea A5 si se mitiga)

| Ítem | Notas |
|------|--------|
| Upload imágenes S3/CDN | Catálogo profesional |
| Test PG checkout concurrente (2 clientes, 1 unidad) | Cierra residual F17 Fase 0D |
| WAF / rate limit global API | Defensa en profundidad |
| Dashboard admin métricas | Operación, no venta |
| Actualizar `project-status-v1.md` / overview | Docs drift post A0–A5 |

---

## Orden de ejecución recomendado (calendario relativo)

Estimaciones en **semanas-equipo pequeño (1–2 devs)**; ajustar a realidad:

| Sprint | Duración sugerida | Hito visible |
|--------|-------------------|--------------|
| A2 | 1.5–2.5 semanas | Staging + CI + Docker |
| A3 | 0.5–1.5 semanas | Tras decisión contable; puede solaparse fin de A2 |
| A4 | 1–2 semanas | Outbox + política postventa |
| A5 | 1–2 semanas | Cutover + 1er cobro supervisado |
| A6 | 1–2 semanas | Post go-live o paralelo suave con A5 |

**Solapamiento seguro:** A3 puede empezar en cuanto exista acta fiscal (incluso durante A2). A6-5 (textos legales) puede redactarse en paralelo sin tocar backend crítico.

---

## Matriz de ownership

| Área | Owner sugerido | Bloquea |
|------|----------------|---------|
| Decisión IVA A/B/C | Negocio + contador | A3, A5 |
| Staging / DNS / TLS | Ops / DevOps | A2, A5 |
| PayPhone live | Negocio + backend | A5 |
| SMTP / DNS email | Ops | A4, A5 |
| SRI cert / RUC | Contabilidad + admin | A5 |
| Política refund | Negocio | A4-4 |
| Textos legales | Legal / negocio | A6 |

---

## Definition of Ready (para abrir cada sprint)

1. Sprint anterior con DoD o excepciones **escritas** (no verbales).  
2. Secrets/env del entorno destino disponibles (no inventar placeholders en staging/prod).  
3. Alcance “fuera de” respetado; no mezclar A5 cutover con features A6.  
4. Al cerrar: informe `docs/audits/SPRINT_A{n}_*.md` con pruebas ejecutadas y decisión APTO/NO.

---

## Resumen de bloqueos actuales → sprint

| Bloqueo (post A1) | Sprint |
|-------------------|--------|
| Decisión IVA | A3 |
| Redis sessions + staging HTTPS | A2 |
| Scheduler reservas en vivo | A2 |
| CI/CD + Dockerfiles | A2 |
| SMTP prod + outbox | A4 → A5 |
| Cancel/refund post-PAID | A4 |
| Backups / observabilidad | A5 |
| Reset password / legal | A6 |
| Cobro real | A5 (solo con gate) |

---

*Plan vivo: actualizar este archivo al cerrar cada sprint (fecha, desviaciones, nuevo head Alembic).*
