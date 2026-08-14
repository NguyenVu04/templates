---
name: fastapi-scaffold
description: Guidance for bootstrapping a new FastAPI project from scratch — `uv init`, project/folder layout, `main.py` app factory with lifespan, `pydantic-settings` configuration, `.env` handling, and ruff/pytest tooling config. Use this skill whenever the user wants to start a new FastAPI project, set up folder structure, scaffold a Python backend/API, initialize config/env vars, or asks for a generic "build me a backend/API in Python" (FastAPI is the default choice here).
---

# FastAPI Project Scaffolding

A playbook for standing up a new FastAPI service from `uv init` through a running `/docs` page.

## Non-negotiable defaults

These apply to every new project unless the user's existing codebase or explicit request says otherwise:

1. **`uv` for everything Python** — `uv init`, `uv add`, `uv run`. Never pip/poetry in new projects.
2. **Async-first** — `async def` endpoints, `AsyncSession`, `httpx.AsyncClient`. Sync only when a required library forces it (then run it via `run_in_threadpool`).
3. **Pydantic v2 syntax** — `model_config = ConfigDict(...)`, `model_validate()`, `field_validator`. Never v1 patterns (`class Config`, `.from_orm()`, `@validator`).
4. **Layered structure** — routers (HTTP concerns) → services (business logic) → repositories (DB access). Routers never touch the session directly beyond passing it down.
5. **Settings via `pydantic-settings`** — one `Settings` class, loaded from env, injected where needed. No `os.getenv` scattered around.
6. **Type hints everywhere** — FastAPI's DI and docs depend on them; untyped code is broken code here.

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
│   │   └── v1/                # one router module per resource
│   ├── models/                # SQLAlchemy models
│   ├── schemas/                # Pydantic request/response models
│   ├── services/                # business logic
│   └── repositories/            # DB queries
└── tests/
    ├── conftest.py
    └── api/ | services/ ...
```

Small projects (< ~5 endpoints) may collapse services+repositories into one layer, but keep routers thin regardless.

## Bootstrap commands

```bash
uv init myproject --package && cd myproject
uv add fastapi "uvicorn[standard]" pydantic-settings
uv add sqlalchemy[asyncio] alembic asyncpg          # if using Postgres
uv add --dev pytest pytest-asyncio httpx ruff mypy aiosqlite
```

`--package` gives the `src/` layout, which prevents accidental imports of the working directory and matches the standard layout above.

## main.py — app factory + lifespan

Keep `main.py` minimal: create the app, wire routers, register exception handlers, manage startup/shutdown via lifespan. Nothing else.

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from myproject.api.v1 import users, items
from myproject.config import settings
from myproject.database import engine

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield                      # startup above, shutdown below
    await engine.dispose()

def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.include_router(users.router, prefix="/api/v1")
    app.include_router(items.router, prefix="/api/v1")
    return app

app = create_app()
```

Use the factory pattern (`create_app`) — tests need to build fresh apps with overridden dependencies.

**Never** use `@app.on_event("startup")` — deprecated; lifespan replaces it.

## config.py — settings

```python
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "myproject"
    debug: bool = False
    database_url: str                    # no default → fails fast if missing
    secret_key: str
    access_token_expire_minutes: int = 30

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
```

Rules:
- Required secrets get **no default** so misconfiguration fails at boot, not at request time.
- Mirror every field into `.env.example` with placeholder values; commit `.env.example`, gitignore `.env`.
- For values needed in tests with overrides, inject `Settings` as a dependency (`Depends(get_settings)`) instead of importing the module-level singleton.
- Secrets never appear in code, logs, or committed files — `.env` is gitignored, `.env.example` is committed with dummy values only.

## Tooling config in pyproject.toml

```toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "ASYNC"]   # ASYNC catches blocking calls in async defs

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

The `ASYNC` ruff ruleset is important: it flags `time.sleep`, sync `requests`, and blocking file IO inside `async def` — the most common FastAPI performance bug.

## Run

```bash
uv run uvicorn myproject.main:app --reload   # dev
```

## Checklist before moving on

- [ ] `uv run uvicorn ...` boots and `/docs` renders
- [ ] `.env.example` committed, `.env` gitignored
- [ ] `uv run ruff check .` clean
- [ ] Git initialized with a sensible `.gitignore` (uv template already includes `.venv`)
