# GEMA Technology Web (Next.js) — build from monorepo root:
#   docker build -f apps/web/Dockerfile -t gema-web .
# Runtime needs API_ORIGIN (server-side rewrite target), e.g. http://api:8000

FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
COPY apps/web/package.json ./apps/web/
RUN npm ci --workspace=apps/web

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY --from=deps /app/apps/web/node_modules ./apps/web/node_modules
COPY package.json package-lock.json ./
COPY apps/web ./apps/web
# Standalone output for slim runtime image
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build --workspace=apps/web

FROM node:20-alpine AS runtime
WORKDIR /app

RUN addgroup -S -g 10001 gema \
    && adduser -S -u 10001 -G gema gema

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# Next.js standalone layout (workspaces → apps/web/server.js)
COPY --from=builder --chown=gema:gema /app/apps/web/public ./apps/web/public
COPY --from=builder --chown=gema:gema /app/apps/web/.next/standalone ./
COPY --from=builder --chown=gema:gema /app/apps/web/.next/static ./apps/web/.next/static

USER gema
EXPOSE 3000

HEALTHCHECK --interval=15s --timeout=5s --start-period=40s --retries=3 \
    CMD wget -qO- http://127.0.0.1:3000/ >/dev/null || exit 1

CMD ["node", "apps/web/server.js"]
