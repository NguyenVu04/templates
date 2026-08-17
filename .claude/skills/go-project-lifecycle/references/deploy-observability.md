# Deploy & Observability

## Health endpoints

Two distinct endpoints — they answer different questions:
- `/healthz` (**liveness**): "is the process alive?" Return 200 unconditionally. Never check dependencies here — a DB blip would make Kubernetes restart healthy pods.
- `/readyz` (**readiness**): "can I serve traffic?" Check critical deps with a short timeout:

```go
func handleReadyz(pool *pgxpool.Pool) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		ctx, cancel := context.WithTimeout(r.Context(), 2*time.Second)
		defer cancel()
		if err := pool.Ping(ctx); err != nil {
			http.Error(w, "db unavailable", http.StatusServiceUnavailable)
			return
		}
		w.WriteHeader(http.StatusOK)
	}
}
```

## Kubernetes deployment essentials

```yaml
apiVersion: apps/v1
kind: Deployment
spec:
  replicas: 2
  template:
    spec:
      containers:
        - name: myservice
          image: ghcr.io/org/myservice:v1.2.3   # never :latest
          ports: [{ containerPort: 8080 }]
          envFrom:
            - secretRef: { name: myservice-secrets }
          resources:
            requests: { cpu: 100m, memory: 128Mi }
            limits: { memory: 256Mi }            # memory limit yes; CPU limit usually no (throttling)
          livenessProbe:
            httpGet: { path: /healthz, port: 8080 }
            periodSeconds: 10
          readinessProbe:
            httpGet: { path: /readyz, port: 8080 }
            periodSeconds: 5
          securityContext:
            runAsNonRoot: true
            readOnlyRootFilesystem: true
            allowPrivilegeEscalation: false
```

Go runtime awareness in containers:
```go
import _ "go.uber.org/automaxprocs" // GOMAXPROCS = CPU limit, not node cores
```
(Go 1.25+ does this automatically; the import is for older versions.) Set `GOMEMLIMIT` to ~90% of the memory limit to avoid OOMKills:
```yaml
env:
  - name: GOMEMLIMIT
    value: "230MiB"
```

Graceful rollout: Kubernetes sends SIGTERM → `signal.NotifyContext` triggers `srv.Shutdown` (see api-service.md) → in-flight requests finish within `terminationGracePeriodSeconds` (default 30s, keep shutdown timeout below it).

## Structured logging with slog

```go
logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{
	Level: cfg.LogLevel,
}))
slog.SetDefault(logger)

logger.Info("request completed",
	"method", r.Method, "path", r.URL.Path,
	"status", status, "duration_ms", dur.Milliseconds(),
	"request_id", reqID)
```
- JSON to stdout; the platform (K8s + collector) handles shipping. Never write log files from the app.
- Attach request-scoped fields once: `logger.With("request_id", id)` in middleware, pass via context.
- Levels: `Debug` dev detail, `Info` state changes worth seeing in prod, `Warn` degraded-but-handled, `Error` needs human attention. Log an error at exactly one layer.
- Never log secrets, tokens, passwords, full request bodies.

## Prometheus metrics

```go
var httpDuration = prometheus.NewHistogramVec(
	prometheus.HistogramOpts{
		Name:    "http_request_duration_seconds",
		Buckets: prometheus.DefBuckets,
	},
	[]string{"method", "route", "status"},
)
// middleware observes it; expose with:
mux.Handle("GET /metrics", promhttp.Handler())
```
- Label with the route **pattern** (`/users/{id}`), never raw paths — raw paths explode cardinality.
- The four signals for any service: request rate, error rate, duration (histogram), saturation (goroutines `go_goroutines`, memory — free from the default Go collector).
- Business metrics as counters (`orders_created_total`) are cheap and often more useful than infra ones.

## Tracing (OpenTelemetry)

Worth adding when >2 services participate in a request. Instrument at the edges: `otelhttp.NewHandler` for the server, `otelhttp.NewTransport` for outgoing clients, `otelpgx` for DB. Propagate context everywhere (already required by convention) and traces work automatically.

## pprof — production profiling

```go
import "net/http/pprof" // registers on DefaultServeMux
// serve on an INTERNAL-ONLY port, never the public listener:
go http.ListenAndServe("localhost:6060", nil)
```
Playbook:
- CPU cao: `go tool pprof http://localhost:6060/debug/pprof/profile?seconds=30` → `top`, `web`.
- Memory tăng: heap profile, so sánh 2 lần chụp: `pprof -base heap1.out heap2.out`.
- Goroutine leak: `/debug/pprof/goroutine?debug=1`, diff counts theo stack.
- Hang: full goroutine dump, tìm goroutine block lâu.
- Kết luận hiệu năng luôn dựa trên profile/benchstat, không dựa trên cảm giác.

## Deployment checklist (before first prod release)

1. Liveness + readiness probes wired and distinct
2. Graceful shutdown verified (`kill -TERM`, watch in-flight requests finish)
3. Resource requests/limits + GOMEMLIMIT set
4. JSON logs with request IDs; no secrets in logs
5. `/metrics` scraped; basic dashboard + alert on error rate & p99 latency
6. Image pinned by tag/digest, runs as nonroot
7. Migrations run as a deploy step, backwards-compatible with the previous version
8. Rollback plan: previous image tag deployable in one command
