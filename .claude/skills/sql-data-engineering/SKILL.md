---
name: sql-data-engineering
description: Analytical SQL and data engineering — window functions, CTEs, query optimization, schema design, and pandas/SQL data pipelines (PostgreSQL, DuckDB, SQLite). Use this skill whenever the user needs to write or debug SQL queries, aggregate/join/deduplicate data in a database, compute rolling metrics, cohorts, retention, funnels, or top-N per group, optimize a slow query, design tables for analytics, or move data between files/pandas and a database ("truy vấn", "viết SQL", "query chậm", ETL, data pipeline).
---

# SQL & Data Engineering

Most analytical work is data retrieval and shaping. Write SQL that is correct first (joins and NULLs are where correctness dies), readable second (CTEs), fast third (only optimize measured bottlenecks).

## Query structure: CTE pipeline style

Structure every non-trivial query as named steps, each independently testable:

```sql
WITH base AS (              -- filter early, select only needed columns
  SELECT user_id, event_time, amount
  FROM orders
  WHERE event_time >= DATE '2026-01-01' AND status = 'completed'
),
daily AS (
  SELECT user_id, DATE_TRUNC('day', event_time) AS d, SUM(amount) AS rev
  FROM base GROUP BY 1, 2
)
SELECT * FROM daily ORDER BY d;
```

Debug by `SELECT * FROM <cte> LIMIT 20` at each stage. Prefer CTEs over nested subqueries always; prefer CTEs over temp tables until performance says otherwise.

## Window functions (the analyst's power tools)

```sql
-- Top-N per group (dedupe: keep latest record per entity)
SELECT * FROM (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY updated_at DESC) AS rn
  FROM users_raw
) t WHERE rn = 1;

-- Rolling 7-day average
AVG(rev) OVER (PARTITION BY user_id ORDER BY d
               ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)

-- Change vs previous row / cumulative
rev - LAG(rev) OVER (PARTITION BY user_id ORDER BY d)
SUM(rev) OVER (PARTITION BY user_id ORDER BY d)  -- running total

-- Sessionization: new session if gap > 30 min
SUM(CASE WHEN ts - LAG(ts) OVER w > INTERVAL '30 min' THEN 1 ELSE 0 END)
    OVER w AS session_id  -- WINDOW w AS (PARTITION BY user_id ORDER BY ts)
```

`ROW_NUMBER` (unique) vs `RANK` (gaps on ties) vs `DENSE_RANK` (no gaps) — choose deliberately. Know the default frame trap: with ORDER BY, the frame is `RANGE ... CURRENT ROW`, which groups tied ORDER BY values — specify `ROWS` explicitly for running aggregates.

## Joins and NULL correctness

- Start from the table whose grain you want to keep; LEFT JOIN lookups onto it. **A WHERE condition on a LEFT-JOINed table's column silently converts it to INNER JOIN** — move the condition into the ON clause.
- Fan-out check: if the right side has duplicates on the join key, rows multiply and sums inflate. Verify grain before joining: `SELECT key, COUNT(*) FROM t GROUP BY 1 HAVING COUNT(*) > 1`. Aggregate-then-join beats join-then-aggregate.
- NULL is not a value: `col != 'x'` excludes NULLs; use `IS DISTINCT FROM`. `NOT IN (subquery)` returns nothing if the subquery contains any NULL — use `NOT EXISTS`. `COUNT(col)` skips NULLs, `COUNT(*)` doesn't. Aggregates ignore NULLs (usually what you want, but know it).
- Anti-join pattern (rows in A missing from B): `LEFT JOIN ... WHERE b.key IS NULL` or `NOT EXISTS`.

## Common analytical patterns

- **Cohort retention**: assign cohort = first activity month per user; join activity back; pivot `months_since_cohort`.
- **Funnel**: one CTE per step with the step timestamp; LEFT JOIN steps sequentially on user + time ordering; count survivors per step.
- **Conditional aggregation / pivot**: `SUM(CASE WHEN status='paid' THEN amount END) AS paid_rev` — one pass instead of many self-joins.
- **Gaps & islands** (consecutive-day streaks): `d - ROW_NUMBER() OVER (ORDER BY d) * INTERVAL '1 day'` is constant within a streak; group by it.

## Query optimization

Only after measuring: `EXPLAIN ANALYZE` (Postgres). Read for: Seq Scan on large tables where an index should apply, row-estimate vs actual mismatches (stale stats → `ANALYZE`), nested-loop joins over huge inputs, sorts spilling to disk.

Levers in order: (1) filter earlier / select fewer columns; (2) index the WHERE/JOIN columns — composite index column order matters: equality columns first, then range; (3) avoid wrapping indexed columns in functions (`WHERE DATE(ts) = ...` kills the index — use range predicates: `ts >= d AND ts < d + 1`); (4) pre-aggregate with materialized views for repeated heavy queries; (5) LIMIT during development, always.

## Schema design for analytics

- Star-ish layout: fact tables (events, tall/narrow, one row per event with FK ids) + dimension tables (entities, wide). Avoid one giant wide table maintained by hand.
- Types: timestamps as `timestamptz` (store UTC), money as `NUMERIC` never float, categorical text is fine (Postgres) — premature integer-coding costs more than it saves.
- Layered pipeline: `raw` (immutable, as-ingested) → `staging` (cleaned, typed, deduped) → `marts` (business-level aggregates). Never transform raw in place; reproducibility requires being able to rebuild downstream from raw.
- Idempotent loads: `INSERT ... ON CONFLICT (key) DO UPDATE` or delete-partition-then-insert, so reruns don't duplicate.

## Python ↔ SQL

- **DuckDB is the default for local analytics**: query parquet/CSV/pandas directly, `duckdb.sql("SELECT ... FROM 'data/*.parquet'").df()` — orders of magnitude faster than pandas for joins/aggregations on large files, zero setup.
- pandas `read_sql` with SQLAlchemy for warehouse pulls; chunked reads (`chunksize=`) for large results; parameterized queries ALWAYS (`text("... WHERE id = :id")`, never f-strings — SQL injection and quoting bugs).
- Rule of thumb: aggregate/join/filter in SQL (data lives there, engines are built for it); model/plot in Python. Don't pull 10M rows to pandas to group them.
- Writes: `df.to_sql(..., method="multi", chunksize=5000)` or DuckDB/`COPY` for bulk — row-by-row inserts are 100× slower.
