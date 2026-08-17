# Phase 1 — Scaffold a new FastAPI project

## Bootstrap commands

```bash
uv init myproject --package && cd myproject
uv add fastapi "uvicorn[standard]" pydantic-settings
uv add sqlalchemy[asyncio] alembic asyncpg          # if using Postgres
uv add --dev pytest pytest-asyncio httpx ruff mypy aiosqlite
```

`--package` gives the `src/` layout, which prevents accidental imports of the working directory and matches the standard layout in SKILL.md.

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
