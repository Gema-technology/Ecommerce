# GEMA Technology API — production/staging image (no secrets baked in).
# Build: docker build -f apps/api/Dockerfile -t gema-api apps/api
# Run migrations separately (never from every replica):
#   docker compose -f docker-compose.staging.yml run --rm migrate

FROM python:3.12-slim-bookworm AS builder

WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libffi-dev \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libgdk-pixbuf-2.0-0 \
        shared-mime-info \
    && rm -rf /var/lib/apt/lists/* \
    && python -m venv /venv

ENV PATH="/venv/bin:$PATH"

COPY pyproject.toml README.md ./
COPY app ./app

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

# -----------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS runtime

WORKDIR /app

# Runtime libs for WeasyPrint / PDF generation (quotes)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libgdk-pixbuf-2.0-0 \
        libffi8 \
        shared-mime-info \
        fonts-dejavu-core \
        curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 gema \
    && useradd --system --uid 10001 --gid gema --home-dir /app --shell /usr/sbin/nologin gema \
    && mkdir -p /app/data/sri/certs /app/data/sri/pdfs \
    && chown -R gema:gema /app

COPY --from=builder /venv /venv
ENV PATH="/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_HOME=/app

COPY --chown=gema:gema pyproject.toml README.md alembic.ini ./
COPY --chown=gema:gema app ./app
COPY --chown=gema:gema alembic ./alembic
COPY --chown=gema:gema docker/entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh \
    && chown gema:gema /entrypoint.sh

USER gema

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/api/v1/health || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
