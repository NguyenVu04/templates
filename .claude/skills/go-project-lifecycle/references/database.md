# Database Access

## Stack choice (Postgres)

- **pgx/v5 + sqlc** — default. Write real SQL, get type-safe generated Go. Best performance, no ORM magic.
- **database/sql + sqlc** — if the project must stay driver-agnostic.
- **GORM** — only if the project already uses it. Don't introduce it into new code; hidden queries and reflection costs outweigh convenience at service scale.
- Redis → `redis/go-redis/v9`. MySQL → `go-sql-driver/mysql` + sqlc.

## sqlc setup

`sqlc.yaml`:
```yaml
version: "2"
sql:
  - engine: "postgresql"
    queries: "internal/repository/queries"
    schema: "migrations"
    gen:
      go:
        package: "sqlcgen"
        out: "internal/repository/sqlcgen"
        sql_package: "pgx/v5"
        emit_pointers_for_null_types: true
```

Query file (`queries/users.sql`):
```sql
-- name: GetUser :one
SELECT * FROM users WHERE id = $1;

-- name: CreateUser :one
INSERT INTO users (email, name) VALUES ($1, $2) RETURNING *;

-- name: ListUsers :many
SELECT * FROM users ORDER BY created_at DESC LIMIT $1 OFFSET $2;
```
`go tool sqlc generate` after every schema/query change; add a CI check that the generated code is committed and current.

## Connection pool

```go
poolCfg, err := pgxpool.ParseConfig(cfg.DatabaseURL)
if err != nil { return fmt.Errorf("parse db url: %w", err) }
poolCfg.MaxConns = 20
poolCfg.MaxConnLifetime = time.Hour
poolCfg.MaxConnIdleTime = 15 * time.Minute

pool, err := pgxpool.NewWithConfig(ctx, poolCfg)
if err != nil { return fmt.Errorf("connect db: %w", err) }
defer pool.Close()

if err := pool.Ping(ctx); err != nil { return fmt.Errorf("ping db: %w", err) }
```
Size MaxConns relative to Postgres `max_connections` divided by replica count — the default (4×CPU) can exhaust the server when you scale pods.

## Repository pattern

The service layer defines the interface it needs; the repository implements it and translates driver errors to domain errors:

```go
// internal/service — consumer defines the interface
type UserStore interface {
	Find(ctx context.Context, id string) (domain.User, error)
	Create(ctx context.Context, u domain.NewUser) (domain.User, error)
}

// internal/repository — implementation
func (r *UserRepo) Find(ctx context.Context, id string) (domain.User, error) {
	row, err := r.q.GetUser(ctx, id)
	if errors.Is(err, pgx.ErrNoRows) {
		return domain.User{}, domain.ErrNotFound
	}
	if err != nil {
		return domain.User{}, fmt.Errorf("get user %s: %w", id, err)
	}
	return toDomainUser(row), nil
}
```
`pgx.ErrNoRows` must never leak above the repository — upper layers only know `domain.ErrNotFound`.

## Transactions

Keep transaction control in the service layer via a small helper:

```go
func (r *Repo) WithTx(ctx context.Context, fn func(q *sqlcgen.Queries) error) error {
	tx, err := r.pool.Begin(ctx)
	if err != nil {
		return fmt.Errorf("begin tx: %w", err)
	}
	defer tx.Rollback(ctx) // no-op after successful Commit

	if err := fn(r.q.WithTx(tx)); err != nil {
		return err
	}
	return tx.Commit(ctx)
}
```
Rules: transactions must be short (no network calls inside), always rolled back via defer, and never held across user interaction.

## Migrations (golang-migrate)

```
migrations/
├── 000001_create_users.up.sql
├── 000001_create_users.down.sql
```
- Every migration has a working `down`.
- Migrations are append-only once merged — never edit an applied one; write a new migration to fix.
- Run in CI/CD before rollout (init container or deploy step), not inside app startup for multi-replica services (race between pods).
- Backwards-compatible pattern for zero-downtime: add column → deploy code writing both → backfill → deploy code reading new → drop old (separate release).

## Query gotchas

- Always pass `ctx` so cancelled requests cancel their queries.
- N+1: batch with `WHERE id = ANY($1)` (pgx supports slice params) instead of looping queries.
- Pagination: prefer keyset (`WHERE created_at < $1 ORDER BY created_at DESC LIMIT $2`) over OFFSET for large tables.
- Add indexes with the migration that introduces the query pattern, not after the incident. `CREATE INDEX CONCURRENTLY` in production.
- `NULL` columns → pointer types or `sql.Null*`; decide once per project and stay consistent (sqlc's `emit_pointers_for_null_types` handles it).
