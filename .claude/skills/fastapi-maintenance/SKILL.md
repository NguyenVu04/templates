---
name: fastapi-maintenance
description: Guidance for the long-term maintenance of a FastAPI codebase — API versioning and deprecation cycles, routine and major-version dependency upgrades (Pydantic v1→v2, SQLAlchemy 1.4→2.0), and an incremental order-of-operations for refactoring a legacy FastAPI codebase toward a layered structure. Use this skill whenever the user wants to upgrade dependencies, version or deprecate an API endpoint, refactor a legacy/messy FastAPI codebase, or plan a migration off old framework patterns.
---

# FastAPI Maintenance: Versioning, Deprecation, Upgrades, Legacy Refactoring

Guidance for evolving a FastAPI service safely once it's in production and has real users.

## API versioning & breaking changes

- Version lives in the path prefix (`/api/v1`) wired at `include_router` time — so a `v2` is a new router package reusing the same services.
- **Non-breaking** (ship freely): adding optional request fields, adding response fields, new endpoints.
- **Breaking** (needs v2 or a deprecation cycle): removing/renaming fields, changing types/semantics, tightening validation, changing status codes.
- Deprecation flow: mark `deprecated=True` on the route (shows in OpenAPI) → add a `Deprecation` response header with the sunset date → log usage per consumer → remove after the window. Never delete a used endpoint silently.

```python
@router.get("/old-endpoint", deprecated=True)
```

## Dependency upgrades

Routine (do monthly, or via Dependabot/Renovate):

```bash
uv lock --upgrade            # upgrade within pyproject constraints
uv run pytest && uv run ruff check .
```

Major-version upgrades (FastAPI, Pydantic, SQLAlchemy): one library per PR, read its migration guide first, upgrade the lockfile, run the full test suite. A thorough test suite (happy path, validation, not-found/conflict, and auth cases for every endpoint) is what makes this safe — if coverage is thin, invest there *before* upgrading.

Known big ones if you meet an old codebase:
- **Pydantic v1 → v2**: run `bump-pydantic` (automated codemod), then fix the remainder: `class Config`→`ConfigDict`, `@validator`→`@field_validator`, `.dict()`→`.model_dump()`, `.from_orm()`→`model_validate` with `from_attributes=True`.
- **SQLAlchemy 1.4 → 2.0**: enable `future=True` first, fix all `RemovedIn20Warning`s, then bump. `Query` API → `select()`.
- **`@app.on_event` → lifespan**: replace `@app.on_event("startup")`/`"shutdown"` with an `@asynccontextmanager` lifespan function passed to `FastAPI(lifespan=...)`.

## Refactoring a legacy FastAPI codebase — order of operations

Refactor toward a layered routers → services → repositories structure incrementally; never big-bang:

1. **Safety net first**: characterization tests on the endpoints you're about to touch — assert current behavior, even if odd, before changing anything.
2. **Extract Settings** — replace scattered `os.getenv` with one `pydantic-settings` `Settings` class. Low risk, high leverage.
3. **Introduce the layers one resource at a time**: pick the messiest router, extract its service, then its repository. Ship. Repeat.
4. **Centralize errors** — introduce domain exceptions + a single exception handler that translates them to HTTP; migrate `HTTPException` call sites gradually.
5. **Schema hygiene** — replace `dict` bodies/returns with proper Pydantic Create/Read schemas (watch for accidental field exposure when you do — a Read schema should never leak `hashed_password` or other internal fields).
6. Only then chase framework upgrades and async conversion.

## Recurring hygiene tasks

- `uv run pip-audit` for CVEs in dependencies (or Dependabot alerts).
- Prune dead endpoints: anything with zero traffic in metrics for 90 days is a deprecation candidate.
- Keep `.env.example` in sync whenever `Settings` grows a field — stale examples are the #1 onboarding papercut.
- Alembic history: if migration count grows unwieldy (100s) and all environments are past a point, squash to a new base — carefully, and only with team agreement.
- Re-run a full security review (CORS, secrets, SQL injection, rate limiting, response schemas, upload handling) after any auth-adjacent change.

## When the project grows

- Endpoint count > ~30 or multiple teams: split routers into feature packages (`src/myproject/features/users/{router,service,repository,schemas}.py`) — vertical slices scale better than fat horizontal layers.
- Heavy read traffic: add caching at the service layer (Redis) with explicit invalidation; never cache in routers.
- Long-running work creeping into requests (>2s): move it to a background job queue and return 202 + a status endpoint.
