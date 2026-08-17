# Concurrency

## First rule

Don't add concurrency until a measurement says you need it. Sequential code is easier to reason about; goroutines are cheap but bugs from them are not.

## Every goroutine needs an exit plan

Before writing `go func()`, answer: **when does this goroutine stop, and who waits for it?** If there's no answer, it's a leak.

```go
// LEAK: if no one reads ch, this goroutine blocks forever
go func() { ch <- compute() }()

// FIXED: ctx gives it an exit path
go func() {
	select {
	case ch <- compute():
	case <-ctx.Done():
	}
}()
```

## errgroup — the default tool for "run N things, fail together"

```go
g, ctx := errgroup.WithContext(ctx)

for _, url := range urls {
	g.Go(func() error {          // Go 1.22+: loop var is per-iteration, no capture bug
		res, err := fetch(ctx, url)
		if err != nil {
			return fmt.Errorf("fetch %s: %w", url, err)
		}
		return process(res)
	})
}
if err := g.Wait(); err != nil {
	return err
}
```
- First error cancels `ctx` → siblings can abort early.
- Bounded parallelism: `g.SetLimit(10)` replaces hand-rolled semaphores/worker pools in most cases.
- Collecting results: write to a pre-sized slice by index (`results[i] = ...`) — no mutex needed since each goroutine owns its slot.

## Channels

- Use channels to transfer **ownership** of data; use mutexes to protect **shared state**. Don't force channels where a `sync.Mutex` around a map is clearer.
- The **sender** closes the channel, never the receiver. Close to signal "no more values", not to "clean up" (channels are GC'd fine unclosed).
- Unbuffered = synchronization point; buffered = decouple bursts. A buffer size other than 0, 1, or "known count" needs a justifying comment.
- `select` with `default` = non-blocking attempt; `select` with `<-ctx.Done()` = cancellable wait.

Pipeline stage shape:
```go
func stage(ctx context.Context, in <-chan Item) <-chan Result {
	out := make(chan Result)
	go func() {
		defer close(out)
		for item := range in {
			select {
			case out <- transform(item):
			case <-ctx.Done():
				return
			}
		}
	}()
	return out
}
```

## Context rules

- First param of every blocking/I/O function: `func Do(ctx context.Context, ...)`.
- Derive, don't create: `context.WithTimeout(parent, 5*time.Second)`; `context.Background()` only at the top (main, tests).
- Always `defer cancel()` immediately after creating a cancellable context.
- `context.WithValue` for request-scoped metadata only (request ID, auth) — never for passing function parameters.
- Honor cancellation in loops: check `ctx.Err()` in long CPU-bound loops.

## Mutex & sync

- Keep critical sections tiny; never do I/O while holding a lock.
- `sync.RWMutex` only when profiling shows read contention; plain `Mutex` is usually enough and less error-prone.
- Document what a mutex protects: `mu sync.Mutex // guards cache`.
- `sync.Once` for lazy init; `sync.WaitGroup` when you just need "wait for all" without errors (Go 1.25+: `wg.Go(f)`).
- `atomic` types (`atomic.Int64`) for simple counters — cheaper than mutex.

## Timers

- `time.Ticker` for repeat work; always `defer ticker.Stop()`.
- Periodic background job shape:
```go
func runCleaner(ctx context.Context, every time.Duration) {
	t := time.NewTicker(every)
	defer t.Stop()
	for {
		select {
		case <-t.C:
			clean(ctx)
		case <-ctx.Done():
			return
		}
	}
}
```

## Race detection — non-negotiable

- `go test -race ./...` in CI always.
- A race detected is a bug, full stop — "it seems to work" is not a defense; racy programs have undefined behavior.
- Common races: writing a map from multiple goroutines, capturing a shared variable, lazily initializing without `sync.Once`, reading a struct field while another goroutine writes it.

## Debugging stuck concurrency

- Deadlock/hang: `kill -QUIT <pid>` or pprof `goroutine` profile → read the stacks, find who's blocked on what.
- Goroutine count creeping up in metrics = leak; diff two goroutine profiles to locate it.
