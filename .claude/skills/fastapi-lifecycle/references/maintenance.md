# Phase 8 — Maintenance: versioning, deprecation, upgrades, refactoring legacy

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

Major-version upgrades (FastAPI, Pydantic, SQLAlchemy): one library per PR, read its migration guide first, upgrade the lockfile, run the full suite. The test suite from testing.md is what makes this safe — if coverage is thin, invest there *before* upgrading.

Known big ones if you meet an old codebase:
- **Pydantic v1 → v2**: run `bump-pydantic` (automated codemod), then fix the remainder: `class Config`→`ConfigDict`, `@validator`→`@field_validator`, `.dict()`→`.model_dump()`, `.from_orm()`→`model_validate` with `from_attributes=True`.
- **SQLAlchemy 1.4 → 2.0**: enable `future=True` first, fix all `RemovedIn20Warning`s, then bump. `Query` API → `select()`.
- **`@app.on_event` → lifespan** (see scaffold.md).

## Refactoring a legacy FastAPI codebase — order of operations

Refactor toward the standard layout incrementally; never big-bang:

1. **Safety net first**: characterization tests on the endpoints you're about to touch (testing.md patterns) — assert current behavior, even if odd.
2. **Extract Settings** — replace scattered `os.getenv` with one `Settings` class. Low risk, high leverage.
3. **Introduce the layers one resource at a time**: pick the messiest router, extract its service, then its repository. Ship. Repeat.
4. **Centralize errors** — introduce domain exceptions + the single handler; migrate `HTTPException` call sites gradually.
5. **Schema hygiene** — replace `dict` bodies/returns with proper Create/Read schemas (watch for accidental field exposure when you do).
6. Only then chase framework upgrades and async conversion.

## Recurring hygiene tasks

- `uv run pip-audit` for CVEs in dependencies (or Dependabot alerts).
- Prune dead endpoints: anything with zero traffic in metrics for 90 days is a deprecation candidate.
- Keep `.env.example` in sync whenever `Settings` grows a field — stale examples are the #1 onboarding papercut.
- Alembic history: if migration count grows unwieldy (100s) and all environments are past a point, squash to a new base — carefully, and only with team agreement.
- Re-run the security checklist (auth-security.md) after any auth-adjacent change.

## When the project grows

- Endpoint count > ~30 or multiple teams: split routers into feature packages (`src/myproject/features/users/{router,service,repository,schemas}.py`) — vertical slices scale better than fat horizontal layers.
- Heavy read traffic: add caching at the service layer (Redis) with explicit invalidation; never cache in routers.
- Long-running work creeping into requests (>2s): move to the queue (deployment.md) and return 202 + status endpoint.
