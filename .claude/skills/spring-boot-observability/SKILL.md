---
name: spring-boot-observability
description: >-
  Guidance for logging, metrics, tracing, and health checks in Java/Kotlin
  Spring Boot services: SLF4J logging conventions, structured JSON logs,
  MDC correlation, Micrometer metrics and tagging, OpenTelemetry tracing,
  Actuator health/readiness/liveness groups, and runtime diagnosis (thread
  dumps, heap dumps, slow SQL). Use this skill whenever the user is adding
  or reviewing logging statements, wiring Micrometer/Prometheus metrics,
  setting up distributed tracing, configuring Actuator health groups for
  Kubernetes, debugging a "service is stuck"/OOM/connection-leak incident,
  or asking for a stack trace / thread dump — including when the codebase
  clearly uses Spring Boot (pom.xml/build.gradle with spring-boot-starter,
  @SpringBootApplication, application.yml) even if the user doesn't say
  "Spring Boot" explicitly.
---

# Spring Boot Observability: Logging, Metrics, Tracing, Health

This skill turns Claude into a reliable Spring Boot engineer for observability, so a production incident can be diagnosed from logs/metrics/traces alone.

## Logging

- SLF4J API everywhere (`private static final Logger log = LoggerFactory.getLogger(X.class)` or Lombok `@Slf4j`). Never `System.out`.
- Parameterized messages: `log.info("Order {} cancelled by {}", orderId, user)` — no string concatenation (cost paid even when the level is off).
- Levels: ERROR = someone may need to act; WARN = degraded but handled; INFO = business-significant events (order created, payment captured), sparse enough to read; DEBUG = developer flow detail. Request/response body logging only at DEBUG and always redacted.
- **Structured JSON logs in production**: Boot 3.4+ has it built in (`logging.structured.format.console: ecs` or `logstash`); older versions use `logstash-logback-encoder`. Keep human-readable console in `local` profile.
- **MDC for correlation**: put `traceId`, and business keys like `orderId`, into MDC so every downstream log line carries them. Micrometer Tracing populates trace/span ids into MDC automatically.
- **No secrets in logs, ever.** Never log passwords, tokens, full card/PII fields. Add a logback mask pattern or dedicated serializer for anything sensitive that must appear.

## Metrics (Micrometer)

- Actuator + `micrometer-registry-prometheus` → scrapeable `/actuator/prometheus`. HTTP server, JVM, Hikari, and datasource metrics come free.
- Custom business metrics through injected `MeterRegistry`:

```java
Counter.builder("orders.created").tag("channel", channel).register(registry).increment();
Timer.builder("payment.capture").publishPercentileHistogram().register(registry);
```

- Use `@Timed`/`@Counted` on service methods for cheap instrumentation (needs `TimedAspect` bean + AOP).
- Tag discipline: low-cardinality tags only (status, type, channel). A user-id or order-id tag creates one time series per value and takes down your metrics backend.
- Define per-service SLO signals up front: request rate, error rate, p95/p99 latency, saturation (pool usage, queue depth) — the four golden signals.

## Tracing

- `micrometer-tracing-bridge-otel` + `opentelemetry-exporter-otlp` (or zipkin bridge) — Boot autoconfigures propagation (W3C traceparent) across `RestClient`/`WebClient`/Kafka when instrumented.
- Set `management.tracing.sampling.probability` (1.0 in dev, sampled in prod).
- Custom spans around interesting internal work via `Observation` API — one instrumentation, metrics + traces both:

```java
Observation.createNotStarted("order.pricing", observationRegistry)
    .observe(() -> pricingEngine.price(order));
```

## Health & readiness

- Kubernetes wiring: `management.endpoint.health.probes.enabled: true` → `/actuator/health/liveness` and `/actuator/health/readiness`.
- **Liveness must not include external dependencies.** If the DB blips and liveness fails, K8s restarts every pod and turns a blip into an outage. DB/broker checks belong in *readiness* (stop traffic, don't kill the process).
- Custom `HealthIndicator` for critical dependencies not auto-detected; mark strictly-required ones into the readiness group:

```yaml
management:
  endpoint:
    health:
      group:
        readiness:
          include: readinessState,db
```

- `/actuator/info`: expose build info (`spring-boot-maven-plugin` `build-info` goal) + git commit (`git-commit-id-plugin`) so "what version is running?" is answerable in one curl.
- Actuator exposure elsewhere stays minimal: only `health,info,metrics,prometheus`; everything else locked down or on a separate management port.

## Runtime diagnosis quick reference

- Thread dump: `jcmd <pid> Thread.print` (or `/actuator/threaddump`) — first tool for "service is stuck".
- Heap: `jcmd <pid> GC.heap_info`, `-XX:+HeapDumpOnOutOfMemoryError` always on in prod.
- Slow SQL: enable Hikari leak detection (`spring.datasource.hikari.leak-detection-threshold: 10000`) when hunting connection leaks.

## Working style expectations

- When debugging, ask for (or find) the full stack trace and the active profile before proposing fixes. Most "Spring is broken" reports are bean-wiring, profile, or classpath issues visible in the first 20 lines of the log.
- Reach for the runtime diagnosis tools above (thread dump, heap dump, slow-query logging) before speculating about root cause.
- Explain *why* an observability convention applies when it changes user-written code — the user should learn the reasoning, not just accept edits.
