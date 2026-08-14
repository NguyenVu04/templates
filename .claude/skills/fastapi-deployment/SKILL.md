---
name: fastapi-deployment
description: Guidance for deploying FastAPI services — multi-stage Docker builds with uv, worker/process model sizing, running Alembic migrations safely during rollout, docker-compose for local dev, CI pipeline stages, and background job queues. Use this skill whenever the user wants to dockerize a FastAPI/Python web service, write a Dockerfile, set up CI/CD, configure a production server (uvicorn/gunicorn workers), design a deploy or migration rollout strategy, or add a background job queue.
---

# FastAPI Deployment: Docker, Servers, CI/CD

Guidance for shipping a FastAPI service to production: containers, process model, migrations, and CI.

## Non-negotiable defaults

1. **`uv` for everything Python** — Docker builds use `uv sync --frozen`; never pip/poetry.
2. **Migrations are generated then reviewed by hand**, and always run as a distinct deploy step, never implicitly at app startup.
3. **Secrets never appear in code, logs, or committed files** — injected from the platform's secret store, not baked into the image.

## Dockerfile — multi-stage with uv

```dockerfile
FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
# Dependencies first — cached layer, only invalidated when lockfile changes
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev
COPY . .
RUN uv sync --frozen --no-dev

FROM python:3.12-slim
RUN useradd -m appuser
WORKDIR /app
COPY --from=builder --chown=appuser:appuser /app /app
USER appuser
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["uvicorn", "myproject.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
```

Key points: `--frozen` (lockfile is law), two-step sync for layer caching, non-root user, `--proxy-headers` because there's always a proxy in front.

`.dockerignore`: `.venv`, `.git`, `tests`, `.env`, `__pycache__`, `*.pyc`.

## Workers & process model

- **Kubernetes / any orchestrator**: 1 uvicorn process per container, scale by replicas. Don't multi-worker inside a pod — it fights the scheduler and breaks per-pod metrics.
- **Single VM**: `uvicorn --workers N` (N ≈ CPU cores; async apps rarely need more) or gunicorn with `uvicorn.workers.UvicornWorker` if you want gunicorn's process management.
- Size the DB pool: `workers × pool_size ≤` Postgres `max_connections` minus headroom. Set `pool_size`/`max_overflow` in `create_async_engine` explicitly for prod.

## Migrations on deploy

Run `alembic upgrade head` as a **separate step before** the new app version receives traffic (init container / release phase / CI job) — never in app startup, or N replicas race each other.

Compatibility rule: every migration must be compatible with the *previous* app version, because old and new pods overlap during rollout (expand → migrate → contract).

## docker-compose for local dev

```yaml
services:
  db:
    image: postgres:16
    environment: { POSTGRES_PASSWORD: dev, POSTGRES_DB: myproject }
    ports: ["5432:5432"]
    healthcheck: { test: ["CMD-SHELL", "pg_isready -U postgres"], interval: 2s, retries: 10 }
  api:
    build: .
    env_file: .env
    ports: ["8000:8000"]
    depends_on:
      db: { condition: service_healthy }
```

## CI pipeline (GitHub Actions skeleton)

Stages, in order — fail fast:

```yaml
name: ci
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync --frozen
      - run: uv run ruff check . && uv run ruff format --check .
      - run: uv run mypy src
      - run: uv run pytest --cov=src
      - run: uv run alembic upgrade head && uv run alembic check   # migrations apply cleanly + models in sync
        env: { DATABASE_URL: "sqlite+aiosqlite:///ci.db" }
  build:
    needs: test
    # docker build + push, tag with git SHA
```

`alembic check` in CI catches the classic "changed the model, forgot the migration" drift.

## Background jobs

`BackgroundTasks` dies with the process — use it only for best-effort work (emails, cache warm). Anything that must not be lost goes to a real queue: **arq** (async, Redis, lightweight — good default), Celery (heavier, mature), or the DB-as-queue pattern for low volume. Workers are a separate container sharing the same image (`CMD ["arq", "myproject.worker.WorkerSettings"]`).

## Deploy checklist

- [ ] `debug=False`; docs exposure decided deliberately
- [ ] Secrets injected from the platform's secret store, not baked into the image
- [ ] Liveness (`/healthz`) and readiness (`/readyz`) endpoints wired to the orchestrator
- [ ] Migration step ordered before traffic shift
- [ ] Resource limits + pool sizing set
- [ ] Rollback plan: previous image tag deploys cleanly against current schema
