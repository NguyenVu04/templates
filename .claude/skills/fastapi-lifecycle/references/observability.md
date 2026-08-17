# Phase 7 — Observability: logs, metrics, health, debugging

## Health endpoints — two, not one

```python
@router.get("/healthz")                      # liveness: process is up
async def healthz():
    return {"status": "ok"}

@router.get("/readyz")                       # readiness: can serve traffic
async def readyz(db: DbSession):
    await db.execute(text("SELECT 1"))
    return {"status": "ready"}
```

Liveness must NOT check the DB (a DB blip would make the orchestrator restart healthy pods). Readiness should. Exclude both from access logs and auth.

## Structured logging

Use `structlog` (or stdlib logging with a JSON formatter). Log JSON in prod, pretty console in dev — switch on `settings.debug`.

Request-scoped context via middleware:

```python
import time, uuid, structlog
from starlette.middleware.base import BaseHTTPMiddleware

log = structlog.get_logger()

class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        structlog.contextvars.bind_contextvars(request_id=request_id)
        start = time.perf_counter()
        response = await call_next(request)
        log.info("request", method=request.method, path=request.url.path,
                 status=response.status_code,
                 duration_ms=round((time.perf_counter() - start) * 1000, 1))
        response.headers["x-request-id"] = request_id
        return response
```

Rules:
- Every log line carries `request_id`; return it in the response header so users can quote it in bug reports.
- Never log request bodies wholesale (passwords, tokens, PII). Log field names/IDs, not values.
- Unhandled exceptions: add a catch-all handler that logs the traceback with request_id and returns a generic 500 — never leak stack traces to clients.

## Metrics

`prometheus-fastapi-instrumentator` gives RED metrics (rate, errors, duration) per endpoint in three lines:

```python
from prometheus_fastapi_instrumentator import Instrumentator
Instrumentator().instrument(app).expose(app, endpoint="/metrics")
```

Watch: p95/p99 latency per route, 5xx rate, in-flight requests, and DB pool saturation (`engine.pool.checkedout()` exported as a gauge). Pool exhaustion is the most common "API suddenly slow" cause.

## Tracing (when there's more than one service)

OpenTelemetry auto-instrumentation: `opentelemetry-instrumentation-fastapi` + `-sqlalchemy` + `-httpx`, exporting OTLP. Propagate context on outgoing calls so traces cross service boundaries. Skip this complexity for a single-service deployment until logs+metrics prove insufficient.

## Debugging production issues — playbook

1. **Slow endpoint**: check p95 by route → if DB-bound, enable `create_async_engine(echo=...)` in staging or log queries >200ms; usual suspects are N+1 (missing `selectinload`) and missing indexes (`EXPLAIN ANALYZE`).
2. **Whole app slow / timeouts**: check event-loop blocking — a sync call snuck into an async path (ruff `ASYNC` rules catch most). Check pool saturation next.
3. **Sporadic 500s**: grep logs by `request_id` from the error report; the structured traceback tells you the rest.
4. **Memory creep**: usually unbounded caches or giant result sets — audit list endpoints for missing pagination.
