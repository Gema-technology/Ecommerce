# GEMA Technology — Sprint A0: Critical Remediation

**Fecha:** 2026-10-13  
**Alcance:** Verificación y remediación dirigida (TypeScript, PayPhone webhook, SRI error 65, coherencia fiscal, reservas).  
**Entorno verificado:** Desarrollo local (Windows). API `:8000`, web `:3000`, Postgres/Redis vía Docker Compose.  
**Fuera de alcance:** SMTP, reset password, fulfillment post-PAID, CI/CD, Dockerfiles de app, commits.

---

## 1. Estado inicial de hallazgos

| ID | Defecto | Evidencia actual (2026-10-13) | Estado inicial |
|----|---------|-------------------------------|----------------|
| A0-TS | `ApiError` mal invocado en `sri-api.ts` | Constructor real: `(status, message, options?)`. Uso actual: `new ApiError(response.status, message)`. `tsc --noEmit` exit 0 | **Corregido** (ya estaba en código; no reproducible) |
| A0-PP-EMPTY | Webhook PayPhone vacío → HTTP 200 | Live: `POST /payments/webhooks/payphone` body vacío → `200 {"Response":false,"ErrorCode":"222"}`. Pago/orden no cambian | **Confirmado** como aceptación HTTP sin efecto comercial |
| A0-PP-AUTH | Notificación no autenticada puede confirmar | Dev: secreto vacío permitido. Staging/prod: Settings exige `PAYPHONE_WEBHOOK_SECRET`; runtime fail-closed 503 si falta. Secret wrong → 401 | **Corregido** (código + tests previos; reforzado query `?token=`) |
| A0-PP-AMOUNT | Importe / orden / duplicados | `_assert_payphone_amount`; `PaymentEvent` idempotente; pending/failed no marcan PAID; sync consulta Sale API | **Corregido** (ya implementado) |
| A0-SRI-65 | Rechazo fecha emisión | Doc `001-001-000000001`, clave `13102026…`, XML `fechaEmision=13/10/2026`, `created_at=2026-10-13 04:52:23 UTC` (= **12/10** Ecuador). Mensaje SRI error 65 | **Confirmado** causa raíz; fix de zona horaria ya en código |
| A0-TAX | Orden $999 sin IVA vs factura $1148.85 | Orden `GEMA-20261013-000004`: `total=999`, `tax_total=0`. Factura: `subtotal=999`, `tax_total=149.85`, `total=1148.85`. `commerce_tax_enabled=false` | **Confirmado** divergencia documentada; decisión comercial pendiente |
| A0-RES | Reservas + expire + webhook tardío | Tests expire PG + late PayPhone; scheduler compose **no** corre en este host | **Parcial** — lógica OK; ops scheduler pendiente |

`docs/audits/SPRINT_A0_CRITICAL_REMEDIATION.md` no existía antes de este sprint. Referencias previas: `PHASE_0D_BACKEND_PRODUCTION_READINESS.md`, `payphone-ecuador-v1.md`.

---

## 2. Evidencia de código y pruebas

### TypeScript / ApiError

- Definición: `apps/web/src/lib/auth-api.ts` — `constructor(status, message, options?)`.
- `apps/web/src/lib/sri-api.ts` y `quotes-api.ts` alineados con esa firma.
- Validación: `npm run typecheck` → OK; `npm run lint` → 0 errors (2 warnings preexistentes); `npm run test` → **61 passed**; `npm run build --workspace=apps/web` → OK.

### PayPhone

- Auth webhook: `apps/api/app/modules/payments/router.py` — `?token=` / `X-GEMA-Payment-Secret` / `X-PayPhone-Webhook-Secret`; fail-closed staging/prod.
- Provider: StoreId, Amount obligatorio si approved, outcome por `StatusCode`.
- Service: contraste de centavos, idempotencia por `provider_event_id`, `_apply_success` solo si orden `PENDING_PAYMENT`.
- Frontend: «Ya pagué» llama `POST /payments/{id}/sync` (Sale API); la redirección del navegador no marca PAID.
- Auth oficial documentada en repo: secreto compartido configurado por el comercio (no firma HMAC de cuerpo inventada). Fuente: `payphone-ecuador-v1.md` + código.

### SRI error 65

- Helper: `apps/api/app/modules/sri/timeutil.py` — `America/Guayaquil`.
- Emisión: `ecuador_emission_date()` en `_emit_factura`.
- Doc histórico **no modificado**.
- Retry bloqueado con 409 si mensajes contienen error 65 de fecha (evita reenviar XML incorrecto).

### Fiscal / comercial

- Checkout: `commerce/totals.py` + `commerce/tax.py` — IVA opcional vía `COMMERCE_TAX_ENABLED` (default false).
- Factura: si tax desactivado en checkout, `_emit_factura` fuerza IVA 15% sobre base (comentario de decisión pendiente en servicio).

### Reservas

- `InventoryService.expire_due_reservations` + script/compose sidecar.
- Test: expire → orden `CANCELLED` → webhook aprobado tardío **no** marca PAID.

---

## 3. Causas raíz

### A0-PP-EMPTY (HTTP 200 en body vacío)

El contrato PayPhone exige envelope HTTP 200 (`Response`/`ErrorCode`). El handler atrapa el 400 de JSON inválido y responde `Response: false` **sin** llamar a `_apply_success`. No es confirmación de pago; es ACK de protocolo.

### A0-SRI-65

En el momento de emisión (~04:52 UTC del 13-oct), la fecha civil en Ecuador era **12-oct**. La clave/XML usaron **13-oct** (calendario UTC). El SRI rechazó por fecha futura / fuera de tolerancia:

> `ERROR — 65 — FECHA EMISIÓN EXTEMPORANEA — … o es mayor a la fecha del servidor`

**No se re-emitió** contra el SRI en este sprint (el doc histórico queda como evidencia). La corrección preventiva (`ecuador_emission_date`) está cubierta por tests unitarios/regresión.

### A0-TAX ($999 vs $1148.85)

Dos modelos coexisten a propósito hasta decisión comercial:

1. **Checkout/pago:** con `commerce_tax_enabled=false`, `order.total = subtotal (+ shipping)` sin IVA → cobro PayPhone = $999.
2. **Factura SRI:** aplica IVA 15% sobre base → total fiscal $1148.85.

No se reescribieron órdenes ni comprobantes históricos.

---

## 4. Correcciones realizadas en este sprint

| Cambio | Archivo |
|--------|---------|
| Bloqueo de retry en error 65 (sin reescribir XML) | `apps/api/app/modules/sri/service.py` |
| Test query `?token=` PayPhone | `apps/api/tests/test_payphone.py` |
| Tests SRI: borde UTC + retry 65 | `apps/api/tests/test_sri.py` |
| Test integración orden $999 vs factura $1148.85 | `apps/api/tests/test_tax_fiscal_consistency.py` |
| Este informe | `docs/audits/SPRINT_A0_CRITICAL_REMEDIATION.md` |

TypeScript / PayPhone core / `ecuador_emission_date` ya estaban remediados; se verificaron y se añadieron pruebas de regresión.

---

## 5. Resultados de pruebas

| Comando | Resultado |
|---------|-----------|
| `npm run typecheck` | exit 0 |
| `npm run lint` | exit 0 — 0 errors, 2 warnings (employees unused Link; select aria) |
| `npm run test` (vitest) | **61 passed**, 11 files |
| `npm run build --workspace=apps/web` | exit 0 |
| `pytest tests/test_payphone.py tests/test_tax_fiscal_consistency.py tests/test_sri.py tests/test_reservation_lifecycle.py tests/test_expire_reservations_script.py -q` | **58 passed** |
| `pytest tests/test_reservation_expire_postgres.py -q` | **3 passed** |
| `pytest -q` (suite completa API) | **243 passed, 5 skipped** |
| `ruff check` (archivos tocados) | All checks passed |
| Live `POST` webhook vacío | `200 {"Response":false,"ErrorCode":"222"}` |
| Re-emisión real SRI pruebas | **No ejecutada** (evita consumir secuencial / certificado en esta sesión) |

---

## 6. Riesgos y decisiones pendientes

### Decisión comercial/fiscal requerida (antes de cambiar lógica)

Elegir **una** política y aplicar de forma consistente en checkout + PayPhone + factura:

| Opción | Checkout `total` | Factura | Notas |
|--------|------------------|---------|-------|
| **A.** Precio + IVA | Activar `COMMERCE_TAX_ENABLED=true` | IVA alineado con orden | Cliente paga $1148.85; cobro = fiscal |
| **B.** Precio con IVA incluido | Mantener tax off en checkout; factura con base = total/1.15 | Requiere desglose fiscal distinto | No implementar sin validación contable |
| **C.** Nota de venta / RIMPE sin IVA en factura electrónica | Factura no aplica o usa nota de venta | Depende del régimen (`tax_regime`) | Revisar con contador |

**Hasta decidir: no cambiar** totales de órdenes existentes ni forzar `commerce_tax_enabled` en producción.

### Ops pendientes (no bloquean sandbox controlado)

1. Activar profile `scheduler` o `python -m app.scripts.expire_reservations --loop` en el entorno que acepte pagos.
2. Staging: `SESSION_BACKEND=redis`, `PAYPHONE_WEBHOOK_SECRET` fuerte, HTTPS para Notificacion Externa.
3. Doc histórico error 65: emitir **nueva** FACTURA (nuevo secuencial) en ambiente pruebas; no usar retry.
4. Plan de reconciliación no destructivo si aparecen reservas huérfanas históricas (listar ACTIVE vencidas + órdenes PENDING/CANCELLED; no liberar a ciegas).

### Auth PayPhone

Mecanismo soportado por GEMA (evidencia en docs del repo): secreto compartido en query/header. No se inventó firma de cuerpo. Si PayPhone exige otro esquema oficial adicional, falta evidencia externa; el secreto compartido sigue siendo el control implementado.

---

## 7. Estado final por bloqueador

| ID | Estado final |
|----|--------------|
| A0-TS | **Cerrado** — typecheck/tests/build OK |
| A0-PP-EMPTY | **Cerrado** — HTTP 200 envelope sin efecto comercial; test dedicado |
| A0-PP-AUTH | **Cerrado** para staging/prod fail-closed; query token + header cubiertos |
| A0-PP-AMOUNT / idempotencia / pending | **Cerrado** — tests verdes |
| A0-SRI-65 | **Causa raíz demostrada**; preventivo en código + tests; doc histórico no reescrito; nueva emisión pendiente ops |
| A0-TAX | **Documentado + testeado**; lógica no cambiada — **decisión pendiente** |
| A0-RES | **Lógica cerrada** en tests; scheduler en vivo **pendiente ops** |

---

## 8. Decisión

### **APTO para continuar en sandbox** (con condiciones)

Se puede avanzar el MVP comercial en **sandbox** PayPhone + SRI ambiente pruebas, siempre que:

1. El scheduler de reservas esté activo en ese entorno.
2. No se cobre dinero real hasta resolver la decisión fiscal A/B/C.
3. Las facturas nuevas usen el código actual (`America/Guayaquil`); el comprobante con error 65 no se reintente.
4. Staging/prod mantengan `PAYPHONE_WEBHOOK_SECRET` y credenciales PayPhone.

### **NO APTO para producción / cobro real**

Bloqueos restantes: decisión IVA, email transaccional, fulfillment, sessions Redis en el host actual (`memory`), CI/CD, packaging, y Notificacion Externa con HTTPS público.

---

## Resumen ejecutivo

Sprint A0 verificó el runtime vivo, cerró huecos de prueba (PayPhone `?token=`, SRI borde UTC, mismatch $999/$1148.85, bloqueo retry error 65) y dejó evidencia reproducible. La meta de “evidencia confiable para sandbox” se cumple; la meta de “listo para producción” no.
