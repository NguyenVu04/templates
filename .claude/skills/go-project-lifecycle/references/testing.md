# Testing

## Ground rules

- Test files live next to code (`server.go` / `server_test.go`).
- Same package for whitebox tests; `package foo_test` for blackbox tests of the public API (prefer blackbox — it tests what users see).
- Run with `-race -cover` always: `go test -race -cover ./...`.
- Prefer `testify/require` over `assert` — failing fast avoids cascading nil-pointer noise.
- Test behavior, not implementation. If refactoring internals breaks tests without changing behavior, the tests were too coupled.

## Table-driven tests (default pattern)

```go
func TestSlugify(t *testing.T) {
	tests := []struct {
		name string
		in   string
		want string
	}{
		{"simple", "Hello World", "hello-world"},
		{"unicode", "Xin Chào", "xin-chao"},
		{"empty", "", ""},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			require.Equal(t, tt.want, Slugify(tt.in))
		})
	}
}
```
- `t.Run` per case → runnable individually (`go test -run TestSlugify/unicode`).
- `t.Parallel()` where cases are independent — it also flushes out shared-state bugs.
- Add an `wantErr error` field and check with `require.ErrorIs` for error cases.

## Handler tests with httptest

```go
func TestGetUser_NotFound(t *testing.T) {
	store := &stubStore{err: domain.ErrNotFound}
	h := handleGetUser(slog.New(slog.DiscardHandler), store)

	req := httptest.NewRequest(http.MethodGet, "/users/42", nil)
	req.SetPathValue("id", "42")
	rec := httptest.NewRecorder()

	h.ServeHTTP(rec, req)

	require.Equal(t, http.StatusNotFound, rec.Code)
}
```
Because handlers take explicit deps (see api-service.md), a hand-written stub struct is usually enough — reach for `mockery`/`gomock` only when interfaces are large or numerous.

## Integration tests with testcontainers

```go
func TestUserRepo(t *testing.T) {
	if testing.Short() { t.Skip("integration test") }
	ctx := context.Background()

	pg, err := postgres.Run(ctx, "postgres:17-alpine",
		postgres.WithDatabase("test"),
		postgres.BasicWaitStrategies(),
	)
	require.NoError(t, err)
	testcontainers.CleanupContainer(t, pg)

	dsn, err := pg.ConnectionString(ctx, "sslmode=disable")
	require.NoError(t, err)
	// run migrations against dsn, construct repo, test real SQL
}
```
- Real Postgres beats sqlmock — sqlmock tests that you wrote the SQL you wrote, not that it works.
- Guard with `testing.Short()`; CI runs full suite, local quick loop runs `go test -short ./...`.
- Share one container per package via `TestMain` when startup cost matters; give each test its own schema or use transactions rolled back per test.

## Test helpers & fixtures

```go
func newTestServer(t *testing.T) *Server {
	t.Helper()
	// ...
	t.Cleanup(func() { /* teardown */ })
	return srv
}
```
- `t.Helper()` so failures point at the caller.
- `t.Cleanup` instead of manual defers — composes across helpers.
- `t.TempDir()`, `t.Setenv()` for filesystem/env isolation.
- Golden files for large outputs: store expected output in `testdata/`, add an `-update` flag to regenerate.

## Coverage — a compass, not a KPI

- `go test -coverprofile=cover.out ./... && go tool cover -html=cover.out` to find untested branches.
- Prioritize: business logic and error paths > handlers > wiring. 100% coverage of trivial getters is waste; 0% on error branches is risk.

## Benchmarks & fuzzing

```go
func BenchmarkSlugify(b *testing.B) {
	for b.Loop() {                 // Go 1.24+; older: for range b.N
		Slugify("Hello World Benchmark")
	}
}
```
Run `go test -bench=. -benchmem`; compare changes with `benchstat old.txt new.txt` — never eyeball two single runs.

```go
func FuzzSlugify(f *testing.F) {
	f.Add("Hello World")
	f.Fuzz(func(t *testing.T, s string) {
		out := Slugify(s)
		require.False(t, strings.Contains(out, " "))
	})
}
```
Fuzz parsers and anything consuming untrusted input: `go test -fuzz=FuzzSlugify -fuzztime=30s`.

## What NOT to test

- Third-party libraries, stdlib behavior, generated code (sqlc output).
- Private helpers already covered through the public API.
- Log message wording.
