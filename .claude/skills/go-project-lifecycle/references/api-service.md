# HTTP / API Service

## Router choice

- **Go 1.22+ `net/http`**: has method + path params routing (`mux.HandleFunc("GET /users/{id}", h)`). Default for new services — zero deps.
- **chi**: when you want a middleware ecosystem and route grouping, stays 100% `net/http` compatible.
- **gin**: use if the project already uses it (its `gin.Context` couples handlers to the framework — don't introduce it into fresh code without reason).
- **gRPC**: internal service-to-service with strong contracts; use `buf` for proto management, `connect-go` if you also need HTTP/JSON from the same handlers.

## Handler pattern — closures over dependencies

```go
func handleGetUser(logger *slog.Logger, store UserStore) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id := r.PathValue("id")
		user, err := store.Find(r.Context(), id)
		switch {
		case errors.Is(err, domain.ErrNotFound):
			writeError(w, http.StatusNotFound, "user not found")
		case err != nil:
			logger.Error("find user", "id", id, "err", err)
			writeError(w, http.StatusInternalServerError, "internal error")
		default:
			writeJSON(w, http.StatusOK, toUserResponse(user))
		}
	}
}
```

- Explicit deps per handler → each handler is unit-testable with `httptest`.
- Map domain errors → status codes at this layer only. Never leak `err.Error()` from internals to the client for 5xx.
- Request/response DTOs are separate from domain types (`toUserResponse`), so the API contract doesn't shift when the domain changes.

**JSON helpers (write once per project):**
```go
func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

func decodeJSON[T any](r *http.Request) (T, error) {
	var v T
	dec := json.NewDecoder(http.MaxBytesReader(nil, r.Body, 1<<20)) // 1MB cap
	dec.DisallowUnknownFields()
	if err := dec.Decode(&v); err != nil {
		return v, fmt.Errorf("decode json: %w", err)
	}
	return v, nil
}
```

## Routes in one place

```go
func addRoutes(mux *http.ServeMux, logger *slog.Logger, store UserStore) {
	mux.Handle("GET /healthz", handleHealthz())
	mux.Handle("GET /api/v1/users/{id}", handleGetUser(logger, store))
	mux.Handle("POST /api/v1/users", handleCreateUser(logger, store))
}
```
One file listing every route = the API's table of contents.

## Middleware

Standard signature `func(http.Handler) http.Handler`; compose outermost-first: recover → requestID → logging → auth → handler.

```go
func withRecover(logger *slog.Logger) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			defer func() {
				if rec := recover(); rec != nil {
					logger.Error("panic", "err", rec, "stack", string(debug.Stack()))
					writeError(w, http.StatusInternalServerError, "internal error")
				}
			}()
			next.ServeHTTP(w, r)
		})
	}
}
```

Pass request-scoped values (request ID, auth user) via `context.WithValue` with an unexported key type:
```go
type ctxKey int
const userKey ctxKey = iota
```

## Server lifecycle & graceful shutdown

```go
srv := &http.Server{
	Addr:              net.JoinHostPort(cfg.Host, cfg.Port),
	Handler:           handler,
	ReadHeaderTimeout: 5 * time.Second,   // slowloris protection
	ReadTimeout:       10 * time.Second,
	WriteTimeout:      30 * time.Second,
	IdleTimeout:       time.Minute,
}

errCh := make(chan error, 1)
go func() { errCh <- srv.ListenAndServe() }()

select {
case err := <-errCh:
	return fmt.Errorf("server: %w", err)
case <-ctx.Done(): // SIGINT/SIGTERM via signal.NotifyContext
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	return srv.Shutdown(shutdownCtx)
}
```
Never ship a server without timeouts — the zero-value `http.Server` has none.

## Config

```go
type Config struct {
	Host        string
	Port        string
	DatabaseURL string
	LogLevel    slog.Level
}

func Load(getenv func(string) string) (Config, error) {
	cfg := Config{
		Host: cmp.Or(getenv("HOST"), "0.0.0.0"),
		Port: cmp.Or(getenv("PORT"), "8080"),
	}
	cfg.DatabaseURL = getenv("DATABASE_URL")
	if cfg.DatabaseURL == "" {
		return cfg, errors.New("DATABASE_URL is required")
	}
	return cfg, nil
}
```
Fail fast at startup on missing config — never at first request. Secrets only via env/secret manager, never in code or flags.

## Validation

Validate at the edge (handler layer), return 400 with field-level details. For a few fields, hand-rolled checks beat a library; `go-playground/validator` is fine for large DTOs. Business-rule validation ("email already taken") lives in the service layer, not the handler.

## API versioning & docs

- Version in path (`/api/v1/`) from day one — retrofitting hurts.
- Keep an OpenAPI spec in `api/openapi.yaml`; consider `oapi-codegen` to generate server stubs + types from the spec so docs can't drift from code.
