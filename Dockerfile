FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/pnpm-lock.yaml web/pnpm-workspace.yaml ./
RUN corepack enable && corepack use pnpm@12.18.0 && pnpm install --frozen-lockfile
COPY web/ ./
RUN pnpm run build

FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir .
COPY --from=web /web/demo ./web/demo

ENV PORT=8001
EXPOSE 8001
# Serves the operator UI from web/demo and runs the fleet inline. Needs git at build
# time only, to install countersigned-actions straight from its repo.
CMD ["sh", "-c", "uvicorn glasscockpit.api:create_app_from_env --factory --host 0.0.0.0 --port ${PORT}"]
