# GEMA Technology — Sprint A3: Alineación fiscal (opción A)

**Fecha:** 2026-10-14  
**Decisión comercial:** **Opción A** — precio + IVA en checkout; `order.total` = cobro PayPhone = total factura SRI.  
**Fuera de alcance:** rewrite de órdenes históricas, outbox email (A4), cutover live.

---

## 1. Problema previo (A0)

Con `COMMERCE_TAX_ENABLED=false`, checkout cobraba p.ej. $999 y `_emit_factura` forzaba IVA 15% → factura $1148.85.

---

## 2. Comportamiento nuevo

| Entorno / flag | Checkout | FACTURA |
|----------------|----------|---------|
| `COMMERCE_TAX_ENABLED=true` | IVA sobre mercancía (subtotal − descuentos) | Totales = snapshot de la orden; rechazo 409 si tax/total incoherentes con la tasa |
| Tax off + staging/production | N/A para cobro real | **400** — no emitir FACTURA |
| Tax off + development | tax_total=0 | Factura alineada a la orden (sin inflar IVA) |

Envío: no forma parte de la base imponible en v1 (igual que `compute_order_totals`).

Plantillas staging/production: `COMMERCE_TAX_ENABLED=true`.

---

## 3. Archivos

- `apps/api/app/modules/sri/service.py` — alineación / bloqueos
- `apps/api/app/modules/commerce/tax.py` — docstring opción A
- `apps/api/tests/test_tax_fiscal_consistency.py` — tests A3
- UI: `CheckoutSummary`, `OrderTotalsBreakdown`, cart, payment, admin order
- `.env.example`, `.env.staging.example` (+ production en A5)

---

## 4. Evidencia numérica (tests)

Orden opción A: subtotal `999.0000` + IVA `149.8500` → total `1148.8500`.  
`pytest tests/test_tax_fiscal_consistency.py`: **6 passed** (incluye `test_option_a_checkout_total_matches_factura_total`).

---

## 5. Decisión

### **APTO para staging/sandbox con IVA A**

Activar `COMMERCE_TAX_ENABLED=true` en el entorno y no reescribir pedidos históricos.

### **NO APTO cobro real**

Pendiente empaquetado/host (A5), secretos live, y correo durable (A4, diferido).
