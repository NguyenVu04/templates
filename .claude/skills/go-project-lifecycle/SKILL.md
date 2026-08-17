---
name: go-project-lifecycle
description: End-to-end guidance for the full lifecycle of a Go project — from initializing a new repo, structuring packages, and writing idiomatic Go, to building HTTP/gRPC services, database access, concurrency, testing, Docker/CI-CD, Kubernetes deployment, and production observability. Use this skill whenever the user works on ANY Go codebase or mentions Go/Golang tasks, even small ones — e.g. "khởi tạo dự án Go", "tạo project Go mới", "viết service Go", "setup CI/CD cho Go", "viết test Go", "deploy Go lên Kubernetes", "tối ưu Go service", "review code Go", "go mod", "goroutine", "Gin", "chi", "sqlc", "golangci-lint". Also trigger when a repo contains go.mod or .go files, or when the user asks about Go conventions, project layout, error handling, or performance profiling.
---

# Go Project Lifecycle

A router skill covering the entire lifecycle of a Go project. Read the reference file matching the current phase of work — do not load everything at once.

## How to use this skill

1. Identify which lifecycle phase the user's task belongs to (table below).
2. Read the matching file in `references/` before writing code or config.
3. If a task spans phases (e.g. "tạo project mới có sẵn CI/CD"), read each relevant file in order of the workflow.
4. Apply the conventions consistently across the whole session — don't mix styles.

## Phase → reference map

| Phase | When | Read |
|---|---|---|
| **Init & layout** | New project, restructuring, go.mod, tooling setup, Taskfile/Makefile, golangci-lint | `references/project-init.md` |
| **Idiomatic Go** | Writing/reviewing any Go code: errors, interfaces, naming, package design, generics | `references/code-conventions.md` |
| **HTTP/API service** | REST/gRPC service, Gin/chi/net-http, middleware, config, graceful shutdown | `references/api-service.md` |
| **Database** | PostgreSQL/MySQL/Redis access, sqlc, pgx, migrations, transactions, repository pattern | `references/database.md` |
| **Concurrency** | Goroutines, channels, context, errgroup, worker pools, race conditions | `references/concurrency.md` |
| **Testing** | Unit/table tests, mocks, integration tests, testcontainers, benchmarks, fuzzing | `references/testing.md` |
| **Build & CI/CD** | Dockerfile, GitHub Actions, build flags, cross-compile, release, versioning | `references/build-cicd.md` |
| **Deploy & observability** | Kubernetes, health checks, slog logging, Prometheus metrics, tracing, pprof | `references/deploy-observability.md` |

## Core principles (always apply, regardless of phase)

- **Standard library first.** Reach for `net/http`, `log/slog`, `encoding/json`, `errors` before adding a dependency. Every dependency must justify itself.
- **Accept interfaces, return structs.** Define interfaces at the consumer side, keep them small (1–3 methods).
- **Errors are values.** Wrap with `fmt.Errorf("doing X: %w", err)`, check with `errors.Is/As`. Never ignore an error silently; if intentionally discarded, write `_ = f()` with a comment.
- **Context flows down.** Every blocking or I/O function takes `ctx context.Context` as its first parameter. Never store context in a struct.
- **No global mutable state.** Inject dependencies explicitly through constructors (`NewServer(db, logger, cfg)`).
- **Make the zero value useful** where practical (`var buf bytes.Buffer` works without init).
- **gofmt is law.** Run `gofmt`/`goimports`; never argue about formatting.
- **Target the latest stable Go version** in go.mod unless the user's project pins an older one — check `go.mod` before assuming.

## Default toolchain (unless the project already uses something else)

| Concern | Default |
|---|---|
| HTTP router | `net/http` (Go 1.22+ mux) for simple; `chi` for middleware-heavy; `gin` if project already uses it |
| DB Postgres | `pgx/v5` + `sqlc` (type-safe queries) |
| Migrations | `golang-migrate` |
| Logging | `log/slog` (stdlib) |
| Testing | stdlib `testing` + `testify/require`; `testcontainers-go` for integration |
| Lint | `golangci-lint` |
| Task runner | `Taskfile.yml` (or Makefile if repo already has one) |
| Config | env vars via `envconfig` or hand-rolled `os.Getenv` with a Config struct |

Always check what the existing repo uses first (`go.mod`, existing files) and follow it — consistency beats preference.

## Quick decision guide

- "Tạo project Go mới" → project-init.md, then code-conventions.md
- "Viết API/service" → api-service.md (+ database.md if it has storage)
- "Code bị race / chạy song song" → concurrency.md
- "Viết test / coverage thấp" → testing.md
- "Đóng Docker / setup pipeline" → build-cicd.md
- "Deploy / logging / metrics / chậm ở production" → deploy-observability.md
- "Review code Go" → code-conventions.md (+ the phase-specific file for the code under review)
