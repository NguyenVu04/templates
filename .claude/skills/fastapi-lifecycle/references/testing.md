# Phase 5 — Testing

## Stack

`pytest` + `pytest-asyncio` (mode `auto` — no decorators needed) + `httpx.AsyncClient` with `ASGITransport` (in-process, no server) + `aiosqlite` or a throwaway Postgres for the test DB.

## conftest.py — the canonical fixtures

```python
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from myproject.database import Base, get_db
from myproject.main import create_app

@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite://")     # in-memory
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()

@pytest.fixture
async def client(db_session):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
```

Notes:
- `dependency_overrides` is THE mechanism for faking anything in tests — DB, current user, external clients. This is why those things must be dependencies (architecture.md).
- SQLite is fine for most tests; switch to a real Postgres container when you rely on Postgres-specific behavior (JSONB ops, `ON CONFLICT`, constraint semantics).
- An authenticated client fixture: override `get_current_user` to return a factory-made user — don't go through the login flow in every test.

```python
@pytest.fixture
async def auth_client(client, db_session):
    user = await make_user(db_session)                     # test factory
    client._transport.app.dependency_overrides[get_current_user] = lambda: user
    return client
```

## What to test, per endpoint

Minimum set — this is the definition of "an endpoint has tests":

1. **Happy path** — correct status code AND response body shape.
2. **Validation failure** — bad payload → 422.
3. **Not found / conflict** — the domain-error paths → 404/409 with the standard error shape.
4. **Auth** — protected endpoint without token → 401; wrong role/other user's resource → 403 (the IDOR test).

Plus service-level unit tests for any non-trivial business rule (test them directly with a session, no HTTP).

Example shape:

```python
async def test_create_user_returns_201(client):
    resp = await client.post("/api/v1/users", json={"email": "a@b.com", "password": "secret123"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "a@b.com"
    assert "password" not in body and "hashed_password" not in body   # leak check

async def test_create_user_duplicate_email_409(client):
    payload = {"email": "a@b.com", "password": "secret123"}
    await client.post("/api/v1/users", json=payload)
    resp = await client.post("/api/v1/users", json=payload)
    assert resp.status_code == 409
```

## Test data — factories over fixtures-with-data

Write small factory functions (`make_user(db, **overrides)`) with sensible defaults. Avoid giant shared fixture objects — they couple tests together and make failures unreadable.

## Rules

- Tests never touch the dev/prod database. The test engine URL is constructed inside the fixture, never read from `.env`.
- Each test gets a fresh schema (the in-memory engine per fixture above guarantees this). Slow with Postgres? Create schema once per session, wrap each test in a rolled-back transaction.
- Mock at the boundary you own: fake the external-API *client dependency*, not `httpx` internals. For contract tests against the raw HTTP layer, use `respx`.
- Coverage: `uv add --dev pytest-cov`, run `uv run pytest --cov=src --cov-report=term-missing`. Treat uncovered service branches as the priority, not router boilerplate.
- Run `uv run pytest -x -q` after every implementation task; a task isn't done while tests are red.
