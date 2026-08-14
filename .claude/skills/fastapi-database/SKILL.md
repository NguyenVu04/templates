---
name: fastapi-database
description: Guidance for FastAPI database work — async SQLAlchemy 2.0 declarative models, the repository pattern, transaction-per-request session handling, and Alembic migrations. Use this skill whenever the user wants to connect a database, add or edit a SQLAlchemy model, write or review a migration, work with Alembic, fix N+1/lazy-loading issues, or design a repository/query layer.
---

# FastAPI Database: Async SQLAlchemy 2.0 + Alembic

Guidance for the database layer of a FastAPI service — engine/session setup, models, repositories, and migrations.

## Non-negotiable defaults

1. **SQLAlchemy 2.0 style** — `Mapped[...]` + `mapped_column()`, `select()` statements. Never legacy `Query` API.
2. **Async-first** — `AsyncSession`, async drivers. Sync only when a required library forces it (then run it via `run_in_threadpool`).
3. **Migrations are generated then reviewed by hand** — `alembic revision --autogenerate` misses renames and server defaults; never trust the output blindly.

## database.py

```python
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from myproject.config import settings

engine = create_async_engine(settings.database_url, pool_pre_ping=True)
SessionFactory = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_db() -> AsyncSession:
    async with SessionFactory() as session:
        async with session.begin():      # one transaction per request
            yield session                # commit on success, rollback on exception
```

- URL must use the async driver: `postgresql+asyncpg://...`, `sqlite+aiosqlite://...`.
- `expire_on_commit=False` — otherwise attribute access after commit triggers lazy loads that explode under async.
- The `session.begin()` pattern gives **transaction-per-request**: services never call `commit()`; they `flush()` when they need generated IDs mid-transaction. One place controls transactional boundaries.

## Models — 2.0 declarative style

```python
from datetime import datetime
from sqlalchemy import String, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from myproject.database import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    items: Mapped[list["Item"]] = relationship(back_populates="owner")
```

- `Mapped[...]` + `mapped_column()` only. `Column = Column(...)` is legacy.
- Timestamps via `server_default=func.now()` (DB-side), not Python-side `default=datetime.utcnow` (breaks on bulk inserts and is timezone-naive).
- **Lazy loading is a landmine in async** — accessing an unloaded relationship raises `MissingGreenlet`. Always eager-load explicitly in the query: `select(User).options(selectinload(User.items))`.

## Repository pattern

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_email(self, email: str) -> User | None:
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def add(self, user: User) -> User:
        self.db.add(user)
        await self.db.flush()      # get user.id; commit happens in get_db
        return user
```

Keep repositories query-shaped (get/list/add/delete + specific finders). If a method contains an `if` about business rules, it belongs in a service layer above the repository, not in the query code.

## Alembic

Setup once:

```bash
uv run alembic init -t async alembic
```

In `alembic/env.py` set `target_metadata = Base.metadata` (import all model modules first so they register) and read the URL from `Settings`, not a hardcoded ini value.

Workflow per schema change:

```bash
uv run alembic revision --autogenerate -m "add users table"
# 1. OPEN THE GENERATED FILE AND READ IT — autogenerate misses renames
#    (sees drop+create), server defaults, and some constraint changes.
# 2. Verify downgrade() actually reverses upgrade().
uv run alembic upgrade head
```

Hard rules:
- Never edit a migration that's already applied anywhere shared — write a new one.
- Production schema changes only via migrations; never `Base.metadata.create_all()` outside tests.
- For destructive changes (drop column), prefer two deployments: 1) stop writing/reading the column, 2) drop it — keeps rollback safe.

## Query gotchas checklist

- N+1: list endpoints must eager-load the relationships their Read schema serializes.
- Pagination on every list endpoint (`.offset().limit()` + a max cap) — unbounded lists are an outage waiting to happen.
- Uniqueness: enforce with a DB constraint AND catch `IntegrityError` → a conflict domain exception; check-then-insert alone is racy.
- Use `scalar_one_or_none()` (0-or-1 expected) vs `scalars().all()` (lists); avoid `.first()` masking bugs where duplicates exist.
