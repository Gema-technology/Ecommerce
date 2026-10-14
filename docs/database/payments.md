# Database — Payments

Migration: `008_payments`.

## `payments`

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| order_id | UUID FK → orders | RESTRICT |
| provider | VARCHAR(50) | e.g. `manual` |
| provider_payment_id | VARCHAR(120) | nullable |
| method | VARCHAR(30) | CARD / BANK_TRANSFER / CASH_ON_DELIVERY |
| status | VARCHAR(30) | PENDING, PROCESSING, SUCCEEDED, FAILED, CANCELLED, REFUNDED |
| amount | NUMERIC(14,4) | from Order.total |
| currency | CHAR(3) | USD |
| metadata | JSON/JSONB | non-sensitive |
| created_at / updated_at | timestamptz | |
| paid_at | timestamptz | nullable |

Multiple rows per order (payment attempts). Only one may be `SUCCEEDED`.

## `payment_events`

Webhook / confirm idempotency log.

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| provider | VARCHAR(50) | |
| provider_event_id | VARCHAR(120) | |
| event_type | VARCHAR(80) | |
| payload | JSON/JSONB | |
| payment_id | UUID FK → payments | SET NULL |
| processed_at | timestamptz | |
| created_at | timestamptz | |

**UNIQUE** `(provider, provider_event_id)`.
