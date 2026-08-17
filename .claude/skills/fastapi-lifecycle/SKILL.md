---
name: fastapi-lifecycle
description: End-to-end guidance for the full lifecycle of a FastAPI project — scaffolding a new project with uv, layered architecture (routers/services/repositories), async SQLAlchemy 2.0 + Alembic migrations, Pydantic v2 schemas, JWT auth & security hardening, pytest testing, Docker deployment, CI/CD, observability, and long-term maintenance/upgrades. Use this skill WHENEVER the user mentions FastAPI in any capacity — creating a new API, adding endpoints, fixing structure, writing tests for an API, dockerizing a Python web service, database migrations, "REST API bằng Python", or reviewing/refactoring an existing FastAPI codebase. Also trigger for generic "build me a backend/API in Python" requests, since FastAPI is the default choice here.
---

# FastAPI Project Lifecycle

A complete playbook for building and operating FastAPI services, from `uv init` to production maintenance. This SKILL.md is the router: identify which lifecycle phase(s) the task touches, then read ONLY the relevant reference files before writing code.

## Phase routing table

| The user wants to... | Read |
|---|---|
| Start a new project, set up folder structure, config, env vars | `references/scaffold.md` |
| Add endpoints, organize routers/services, DI, Pydantic schemas, error handling | `references/architecture.md` |
| Connect a database, write models, migrations, transactions | `references/database.md` |
| Login/JWT/OAuth2, permissions, CORS, rate limiting, security review | `references/auth-security.md` |
| Write or fix tests, fixtures, coverage, test DB | `references/testing.md` |
| Dockerize, deploy, CI/CD, workers, production server config | `references/deployment.md` |
| Logging, metrics, tracing, health checks, debugging prod issues | `references/observability.md` |
| Upgrade dependencies, API versioning, deprecate endpoints, refactor legacy | `references/maintenance.md` |

Tasks often span phases — e.g., "add a user registration endpoint" touches architecture + database + auth-security + testing. Read all the relevant files; they are short.

## Non-negotiable defaults

These apply to ALL phases unless the user's existing codebase or explicit request says otherwise:

1. **`uv` for everything Python** — `uv init`, `uv add`, `uv run`. Never pip/poetry in new projects.
2. **Async-first** — `async def` endpoints, `AsyncSession`, `httpx.AsyncClient`. Sync only when a required library forces it (then run it via `run_in_threadpool`).
3. **Pydantic v2 syntax** — `model_config = ConfigDict(...)`, `model_validate()`, `field_validator`. Never v1 patterns (`class Config`, `.from_orm()`, `@validator`).
4. **SQLAlchemy 2.0 style** — `Mapped[...]` + `mapped_column()`, `select()` statements. Never legacy `Query` API.
5. **Layered structure** — routers (HTTP concerns) → services (business logic) → repositories (DB access). Routers never touch the session directly beyond passing it down.
6. **Settings via `pydantic-settings`** — one `Settings` class, loaded from env, injected where needed. No `os.getenv` scattered around.
7. **Every new endpoint ships with a test.** Not optional. If you add an endpoint and no test, the task is incomplete.
8. **Type hints everywhere** — FastAPI's DI and docs depend on them; untyped code is broken code here.

## Standard project layout

Reproduce this shape for new projects; use it as the target when refactoring old ones:

```
myproject/
├── pyproject.toml            # uv-managed
├── .env.example              # every var Settings reads, with dummy values
├── alembic/                  # migrations
├── src/myproject/
│   ├── main.py               # app factory + lifespan only
│   ├── config.py             # Settings (pydantic-settings)
│   ├── database.py           # engine, session factory, get_db dependency
│   ├── exceptions.py         # domain exceptions + handlers
│   ├── api/
│   │   ├── deps.py           # shared dependencies (auth, pagination…)
│   │   └── v1/               # one router module per resource
│   ├── models/               # SQLAlchemy models
│   ├── schemas/              # Pydantic request/response models
│   ├── services/             # business logic
│   └── repositories/         # DB queries
└── tests/
    ├── conftest.py
    └── api/ | services/ ...
```

Small projects (< ~5 endpoints) may collapse services+repositories into one layer, but keep routers thin regardless.

## Workflow

1. **Classify the task** against the routing table; read the relevant reference file(s).
2. **Inspect before writing** — if a codebase exists, check its Python version, FastAPI/Pydantic/SQLAlchemy versions in `pyproject.toml`/lockfile, and follow its conventions where they don't conflict with the non-negotiables. Flag conflicts to the user instead of silently rewriting.
3. **Implement in dependency order** — model → migration → schema → repository → service → router → test.
4. **Verify** — run `uv run pytest` and `uv run ruff check .` before declaring done. If the environment can't run them, say so explicitly and list what the user should run.

## Quality bar (applies to every phase)

- Response models are always explicit (`response_model=` or return-type annotation) — never return raw ORM objects.
- Errors are raised as domain exceptions and translated to HTTP in one central handler, not `HTTPException` sprinkled through services.
- No business logic in routers; no HTTP objects (Request/Response) below the router layer.
- Secrets never appear in code, logs, or committed files — `.env` is gitignored, `.env.example` is committed.
- Migrations are generated (`alembic revision --autogenerate`) then **reviewed by hand** — autogenerate misses renames and server defaults.
