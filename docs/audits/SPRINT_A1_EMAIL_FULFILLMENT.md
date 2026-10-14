# GEMA Technology — Sprint A1: Correo transaccional y fulfillment

**Fecha:** 2026-10-13  
**Alcance:** Transiciones admin `PAID → PROCESSING → SHIPPED → DELIVERED`, historial mínimo, correo SMTP desacoplado, UI admin de órdenes.  
**Fuera de alcance:** IVA/fiscal, PayPhone nuevo, SMTP de producción real, Celery/colas, password reset, CI/CD, commits.

---

## 1. Estado previo y código reutilizado

| Área | Antes de A1 |
|------|-------------|
| `OrderStatus` | Enum ya incluía PROCESSING/SHIPPED/DELIVERED (sin uso runtime) |
| Cancelación | Solo `PENDING_PAYMENT` → `CANCELLED` (cliente/admin) |
| Pago → PAID | `PaymentService._apply_success` |
| Email / SMTP | No existía |
| Historial de
| Admin UI | Listado, de estado | No existía |talle, cancelar pendiente, SRI |
| Colas / Celery | No existen (solo cron HTTP de reservas) |

**Reutilizado:** `OrderService`, `RequireAdmin`, `PaymentService._apply_success`, checkout commit, patrones de tests `_checkout_order` / `_pay_manual`.

### Decisiones de arquitectura (Fase 0)

1. **Fulfillment:** `PATCH /api/v1/admin/orders/{id}/status` con máquina forward-only. No se usa para marcar PAID ni alterar pagos.
2. **Cancelación post-pago:** no implementada (política TBD). Se mantiene solo cancelación en `PENDING_PAYMENT`.
3. **Historial mínimo:** tabla `order_status_events` (from/to/actor/note/created_at) — migración `021_fulfillment_notify`.
4. **Email:** SMTP stdlib (`smtplib`), sin Celery. Claim/dedupe en `notification_dispatches` (unique order+event+channel). Fallo de SMTP no revierte la transacción comercial.
5. **Outbox durable / reintentos:** no implementados. Limitación documentada; propuesta mínima abajo.

---

## 2. Diseño de transiciones

```text
PENDING_PAYMENT ──pago confirmado──► PAID ──admin──► PROCESSING ──► SHIPPED ──► DELIVERED
       │
       └──cancel / expire──► CANCELLED
```

| Regla | Comportamiento |
|-------|----------------|
| Actor fulfillment | Solo `RequireAdmin` |
| Cliente | 403 en endpoint admin; no hay endpoint customer de status |
| Inválida | HTTP 409 con detalle de transición |
| Idempotente | Mismo `status` objetivo → 200 sin nuevo evento ni email |
| Pago | Intocable desde fulfillment |
| PAID vía fulfillment | Schema rechaza `PAID` (422); desde PENDING → PROCESSING = 409 |

---

## 3. Archivos modificados / creados

### Backend
- `apps/api/alembic/versions/021_order_fulfillment_notifications.py` (rev `021_fulfillment_notify`)
- `apps/api/app/modules/orders/models.py` — `OrderStatusEvent`
- `apps/api/app/modules/orders/transitions.py`
- `apps/api/app/modules/orders/schemas.py` — update request, history, `allowed_transitions`
- `apps/api/app/modules/orders/service.py` — `admin_update_status`, historial, cancel audit
- `apps/api/app/modules/orders/router.py` — `PATCH .../status`
- `apps/api/app/modules/notifications/*` — models, smtp, templates, service
- `apps/api/app/modules/checkout/service.py` — hook `order.created`
- `apps/api/app/modules/payments/service.py` — hook `order.paid` + evento PAID
- `apps/api/app/core/config.py` — SMTP / EMAIL_* / PUBLIC_APP_URL
- `apps/api/app/main.py`, `alembic/env.py` — registro de modelos
- `apps/api/tests/test_order_fulfillment.py`, `tests/test_notifications.py`

### Frontend
- `apps/web/src/lib/orders-api.ts` — `adminUpdateStatus`, labels
- `apps/web/src/app/admin/orders/[id]/page.tsx` — acciones + historial

### Docs / env
- `.env.example` — variables SMTP
- `docs/audits/SPRINT_A1_EMAIL_FULFILLMENT.md` (este archivo)

---

## 4. Migraciones

| Revision | Contenido |
|----------|-----------|
| `021_fulfillment_notify` | `order_status_events`, `notification_dispatches` (+ unique dedupe) |

Aplicada en el entorno local de verificación: `alembic upgrade head`.

---

## 5. Notificaciones y deduplicación

| Evento | Trigger | Plantilla |
|--------|---------|-----------|
| `order.created` | Tras `commit` de checkout | Pedido recibido / pendiente de pago |
| `order.paid` | Tras `commit` cuando `_apply_success` marca PAID (webhook/sync/admin confirm) | Pago confirmado |
| `order.shipped` | Tras transición admin a SHIPPED | Pedido enviado |

**No** se envía correo de pago por redirección del navegador PayPhone.

Flujo: insert claim → si unique viola, skip → si `EMAIL_ENABLED=false` o sin `SMTP_HOST`, `skipped` → send SMTP → `accepted` (MTA aceptó) o `failed`.  
**Semántica:** `accepted` ≠ entregado al buzón del destinatario.

### Limitación / propuesta outbox (para aprobación)

No hay cola durable. Si el proceso muere tras el commit comercial y antes del claim, el email puede perderse. Propuesta mínima futura:

1. Insertar fila `notification_dispatches` (`pending`) **en la misma transacción** que el cambio de orden.
2. Worker/cron `python -m app.scripts.dispatch_notifications` (mismo patrón que expire-reservations) que envía `pending`/`failed` con backoff.
3. Sin Celery hasta que el volumen lo justifique.

---

## 6. Pruebas ejecutadas

| Comando | Resultado |
|---------|-----------|
| `pytest tests/test_order_fulfillment.py tests/test_notifications.py -q` | **14 passed** |
| `pytest -q` (suite API) | **257 passed, 5 skipped** |
| `ruff check` (archivos A1) | All checks passed (tras fixes) |
| `npm run typecheck` | OK |
| `npm run lint` | 0 errors, 2 warnings preexistentes |
| `npm run test` | **61 passed** |
| `npm run build --workspace=apps/web` | OK |

Correos: solo `MemoryTransport` en tests — **ningún SMTP real / destinatario real**.

---

## 7. Variables de entorno

| Variable | Obligatoria | Notas |
|----------|-------------|-------|
| `EMAIL_ENABLED` | No (default `false`) | Debe ser `true` para intentar envío |
| `SMTP_HOST` | Si email enabled | Sin host → dispatch `skipped` |
| `SMTP_PORT` | No (587) | |
| `SMTP_USER` / `SMTP_PASSWORD` | Según proveedor | Nunca loguear |
| `SMTP_FROM` | Recomendada | Fallback `BUSINESS_EMAIL` |
| `SMTP_USE_TLS` | No (`true`) | |
| `SMTP_TIMEOUT_SECONDS` | No (`10`) | |
| `PUBLIC_APP_URL` | No | Links en plantillas |

---

## 8. Riesgos pendientes

- Política IVA (Sprint A0) sin cambio.
- Scheduler de reservas aún debe activarse en ops.
- Email sin reintentos durables (ver propuesta outbox).
- Cancelación/reembolso post-PAID no definida.
- Tracking number / carrier no modelados (solo `note` opcional en transición).
- Staging necesita SMTP real (sandbox Mailpit/Mailhog/SES) para validación integral de bandeja.

---

## 9. Decisión

### **Listo para validación integral en sandbox** (flujo fulfillment + hooks de correo)

Condiciones:
1. Aplicar migración `021_fulfillment_notify`.
2. Para ver correos: configurar SMTP de prueba + `EMAIL_ENABLED=true` (p. ej. Mailpit local).
3. Probar admin: PAID → PROCESSING → SHIPPED → DELIVERED y revisar historial.
4. Confirmar que un pago PayPhone sync/webhook dispara `order.paid` (no el return URL).

### **No listo para producción**

Faltan: SMTP productivo verificado, outbox/reintentos, decisión fiscal, sessions Redis, scheduler reservas en el entorno, CI/CD y cobros reales.
