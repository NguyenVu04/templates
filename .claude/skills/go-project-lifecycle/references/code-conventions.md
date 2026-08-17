# Idiomatic Go — Code Conventions

Baseline: Effective Go + Google Go Style Guide. This file is the delta that matters most in practice.

## Errors

**Wrap with context, lowercase, no punctuation, describe the operation:**
```go
if err != nil {
	return fmt.Errorf("fetching user %d: %w", id, err)
}
```
- `%w` to allow `errors.Is/As` upstream; `%v` only when deliberately breaking the chain (e.g. at an API boundary to hide internals).
- Don't log AND return the same error — that duplicates log lines. Handle it exactly once: either log-and-recover or wrap-and-return.
- Sentinel errors for expected conditions: `var ErrNotFound = errors.New("not found")`, checked with `errors.Is(err, ErrNotFound)`.
- Custom error types when the caller needs data:
```go
type ValidationError struct{ Field, Reason string }
func (e *ValidationError) Error() string { return e.Field + ": " + e.Reason }
// caller: var ve *ValidationError; if errors.As(err, &ve) { ... }
```
- Never `panic` for expected failures. Panic only for programmer errors (impossible states); `recover` only at goroutine/request boundaries.
- Guard clause style — handle the error and return early; keep the happy path at minimal indentation.

## Interfaces

- **Define at the point of use (consumer side), not next to the implementation.** The `service` package declares the `UserStore` interface it needs; `repository` just happens to satisfy it.
- Keep them small. 1–3 methods. If an interface has 8 methods, it's a class in disguise — split it.
- Don't create an interface "for mocking" before there are two implementations or a real test need. Concrete types are fine.
- Return concrete types from constructors: `func NewServer(...) *Server`, not `func NewServer(...) ServerInterface`.

## Naming

- Short in small scopes (`i`, `r`, `buf`), descriptive in large scopes (`userRepository`).
- Getters without `Get`: `user.Name()`, not `user.GetName()`.
- No stutter: `user.New()` not `user.NewUser()`; `http.Server` not `http.HTTPServer`.
- Acronyms keep case: `userID`, `parseURL`, `httpClient`.
- Interface with one method → method name + `er`: `Reader`, `Notifier`.

## Structs & constructors

```go
type Server struct {
	db     *pgxpool.Pool
	logger *slog.Logger
	cfg    Config
}

func NewServer(db *pgxpool.Pool, logger *slog.Logger, cfg Config) *Server {
	return &Server{db: db, logger: logger, cfg: cfg}
}
```
- Dependencies as unexported fields, injected via constructor. No `init()` magic, no package-level singletons.
- Functional options only when there are genuinely many optional params; otherwise a `Config` struct argument is simpler.
- Pointer receivers when the method mutates or the struct is large; be consistent within a type (don't mix).

## Package design

- A package is a unit of API, not a folder of files. Its name should read well at call sites: `json.Marshal`, `user.Find`.
- No `models` package that everything imports — put types with their behavior (or in `domain`).
- Exported identifiers need doc comments starting with the name: `// Server handles HTTP requests for the user API.`

## Generics — use sparingly

Good uses: type-safe containers, `Map/Filter` utilities, constraints over numeric types. Bad use: replacing a small interface. If `interface{ ... }` reads fine, don't add type parameters. Rule of thumb: write it concretely first, generalize on the second duplication.

## Slices & maps gotchas

- `append` may or may not reallocate — never assume two slices stop sharing memory. Use `slices.Clone` when handing data out.
- Pre-size when length is known: `make([]T, 0, n)`.
- A nil map reads fine but panics on write; a nil slice appends fine. Return nil slices, not empty allocations.
- Use the `slices` and `maps` stdlib packages (`slices.Contains`, `slices.SortFunc`) instead of hand-rolled loops.

## Common review findings (check these when reviewing Go code)

1. Ignored errors (`json.Unmarshal(b, &v)` without checking).
2. `err == ErrX` instead of `errors.Is`.
3. Context stored in a struct or missing from I/O function signatures.
4. Goroutine leaks — a goroutine with no exit path when ctx is cancelled.
5. `defer f.Close()` in a loop (defers pile up until function returns).
6. Mutex copied by value (struct with `sync.Mutex` passed by value) — `go vet` catches it.
7. `time.After` inside a loop (leaks timers pre-1.23; still prefer `time.NewTimer`/`Ticker`).
8. Returning `interface{}`/`any` when a concrete type is known.
9. Huge functions — extract when a block needs a comment to explain "what", keep "why" comments.
10. Missing `-race` in test runs.
