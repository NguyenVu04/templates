# Project Init & Layout

## Initializing

```bash
go mod init github.com/<user>/<project>   # module path = repo URL
go mod tidy                                # after adding imports
```

Pin the Go version in `go.mod` (`go 1.24`) — it controls language features and toolchain selection.

## Layout: scale it to the project

**Small tool / single binary — flat is fine:**
```
myapp/
├── go.mod
├── main.go
├── server.go
├── server_test.go
└── README.md
```
Do NOT create `cmd/`, `internal/`, `pkg/` for a 500-line tool. Premature structure is a Go anti-pattern.

**Service / medium project — standard layout:**
```
myservice/
├── cmd/
│   └── myservice/main.go        # thin main: wire deps, call run()
├── internal/                    # private code, compiler-enforced
│   ├── config/config.go
│   ├── server/                  # HTTP layer: handlers, routes, middleware
│   ├── service/                 # business logic (no HTTP/DB types leak here)
│   ├── repository/              # data access
│   └── domain/                  # core types + interfaces
├── migrations/
├── api/                         # OpenAPI spec / proto files
├── Taskfile.yml
├── Dockerfile
├── .golangci.yml
├── go.mod
└── README.md
```

Rules:
- `internal/` for anything not meant to be imported by other modules. Default everything into `internal/`; only create `pkg/` when an external consumer actually exists.
- Multiple binaries → multiple dirs under `cmd/`.
- Package names: short, lowercase, singular, no underscores (`user`, not `user_utils`). Avoid `util`, `common`, `helpers` — name by what the package provides.
- Avoid circular imports by making `domain` the dependency-free center: it defines types and interfaces; outer layers implement them.

## main.go pattern

Keep `main` tiny and testable — delegate to `run()` which returns an error:

```go
func main() {
	if err := run(context.Background(), os.Args, os.Getenv); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func run(ctx context.Context, args []string, getenv func(string) string) error {
	ctx, stop := signal.NotifyContext(ctx, os.Interrupt, syscall.SIGTERM)
	defer stop()

	cfg, err := config.Load(getenv)
	if err != nil {
		return fmt.Errorf("load config: %w", err)
	}
	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))
	// wire db, server... then serve until ctx is done
	return nil
}
```

`run()` taking `getenv` as a parameter makes config fully testable without touching the real environment.

## Tooling setup (do this at init, not later)

**.golangci.yml** (v2 format, sane starter):
```yaml
version: "2"
linters:
  default: standard          # errcheck, govet, ineffassign, staticcheck, unused
  enable:
    - misspell
    - revive
    - gocritic
    - errorlint              # catches err == ErrX instead of errors.Is
    - copyloopvar
    - nilerr
    - bodyclose
    - sqlclosecheck
formatters:
  enable:
    - gofumpt
    - goimports
```

**Taskfile.yml:**
```yaml
version: '3'
tasks:
  run:    { cmds: ["go run ./cmd/myservice"] }
  test:   { cmds: ["go test -race -cover ./..."] }
  lint:   { cmds: ["golangci-lint run"] }
  tidy:   { cmds: ["go mod tidy"] }
  build:
    cmds:
      - go build -ldflags "-s -w -X main.version={{.VERSION}}" -o bin/myservice ./cmd/myservice
    vars:
      VERSION: { sh: git describe --tags --always --dirty }
```

**Tool dependencies** — Go 1.24+ tracks dev tools in go.mod:
```bash
go get -tool github.com/sqlc-dev/sqlc/cmd/sqlc
go tool sqlc generate
```

## Dependency hygiene

- `go mod tidy` before every commit; CI should fail if it produces a diff.
- Check a candidate dependency: last commit date, open issues, transitive deps (`go mod graph | grep <dep>`). Prefer zero-dep libraries.
- `go mod vendor` only if the org requires hermetic builds; otherwise skip.
- Upgrade deliberately: `go get -u ./... && go test ./...`, review CHANGELOG of major bumps.

## README minimum

Project purpose (1 paragraph), quickstart (`task run`), required env vars table, architecture sketch if non-trivial. Write it at init while intent is fresh.
