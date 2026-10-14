# GEMA API

Backend FastAPI de GEMA Technology.

## Requisitos

- Python 3.12+
- PostgreSQL (vía Docker Compose en la raíz del monorepo)

## Instalación

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Ejecución

```bash
uvicorn app.main:app --reload --port 8000
```

### Expiración de reservas (scheduler externo)

No corre dentro de uvicorn. Con la API arriba:

```bash
python -m app.scripts.expire_reservations          # one-shot (cron)
python -m app.scripts.expire_reservations --loop   # desarrollo
```

Variables: `INTERNAL_JOB_SECRET`, `API_ORIGIN`, `RESERVATION_EXPIRE_INTERVAL_SECONDS`, `RESERVATION_EXPIRE_ENABLED`.  
Ver `docs/architecture/reservation-scheduler-v1.md`.

## Calidad

```bash
ruff check .
ruff format --check .
pytest
```

## Migraciones

```bash
alembic upgrade head
```
