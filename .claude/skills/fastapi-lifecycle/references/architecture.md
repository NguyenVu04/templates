# Phase 2 — Architecture: routers, services, schemas, DI, errors

## Layer responsibilities

| Layer | Knows about | Never touches |
|---|---|---|
| Router (`api/v1/*.py`) | HTTP: status codes, path/query params, response_model | Business rules, SQL |
| Service (`services/`) | Business rules, orchestration, domain exceptions | Request/Response objects, HTTPException |
| Repository (`repositories/`) | SQLAlchemy queries | Business rules, HTTP |

The payoff: services are testable without HTTP, repositories are swappable, and HTTP concerns change in exactly one place.

## Schemas (Pydantic v2)

One module per resource with the Create/Update/Read triple:

```python
from pydantic import BaseModel, ConfigDict, EmailStr, Field

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)

class UserUpdate(BaseModel):
    email: EmailStr | None = None        # all-optional for PATCH

class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)   # enables ORM → schema
    id: int
    email: EmailStr
    # NOTE: no password field — Read schemas define the public surface
```

- v2 syntax only: `model_config = ConfigDict(...)`, `Model.model_validate(orm_obj)`, `@field_validator`. If you catch yourself writing `class Config` or `.from_orm()`, stop — that's v1.
- Never reuse a Create schema as a Read schema; that's how password hashes leak.

## Router pattern

```python
from fastapi import APIRouter, Depends, status
from myproject.api.deps import DbSession          # Annotated alias, see below
from myproject.schemas.user import UserCreate, UserRead
from myproject.services import user_service

router = APIRouter(prefix="/users", tags=["users"])

@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreate, db: DbSession):
    return await user_service.create_user(db, payload)
```

Routers are ~3 lines per endpoint: parse (automatic), delegate, return. If a router grows an `if`, that logic probably belongs in the service.

## Dependencies — `api/deps.py`

Use `Annotated` aliases so signatures stay clean:

```python
from typing import Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from myproject.database import get_db

DbSession = Annotated[AsyncSession, Depends(get_db)]

class Pagination(BaseModel):
    offset: int = Field(0, ge=0)
    limit: int = Field(50, ge=1, le=200)

PaginationDep = Annotated[Pagination, Depends()]
```

Dependencies are the seam for testing: anything you'll want to fake in tests (current user, clock, external clients) should be a dependency, not a module-level import inside the service.

## Error handling — one central translation point

`exceptions.py`:

```python
class DomainError(Exception):
    status_code = 500
    detail = "Internal error"

class NotFoundError(DomainError):
    status_code = 404
    def __init__(self, resource: str, ident):
        self.detail = f"{resource} {ident} not found"

class ConflictError(DomainError):
    status_code = 409
```

Register once in `create_app()`:

```python
from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
```

Services raise `NotFoundError("User", user_id)`; they never import `HTTPException`. This keeps services HTTP-agnostic and error shapes consistent across the whole API.

## Async correctness

- Any blocking call (sync DB driver, `requests`, heavy CPU, `time.sleep`) inside `async def` freezes the entire event loop for all requests. Use async libraries; when impossible, wrap with `fastapi.concurrency.run_in_threadpool`.
- Fire-and-forget work after the response: `BackgroundTasks` for small jobs; a real queue (see deployment.md) for anything that must survive a crash.

## Common review findings (check these when refactoring)

1. `HTTPException` raised deep in service/repository code → replace with domain exceptions.
2. Returning ORM objects without `response_model`/Read schema → leaks columns.
3. Business logic in routers → push down to services.
4. `dict` as request body instead of a schema → no validation, no docs.
5. Mutable default arguments or module-level state shared across requests.
