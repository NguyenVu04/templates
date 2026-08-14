---
name: spring-boot-production-operations
description: >-
  Guidance for running Java/Kotlin Spring Boot services in production:
  profiles and externalized config, graceful shutdown, Kubernetes deployment
  manifests and probes, container-aware JVM tuning, scaling/resilience, and
  runbook creation. Use this skill whenever the user is configuring Spring
  profiles or environment-specific config, writing a Kubernetes
  Deployment/probe/resource spec, tuning JVM flags for a container, setting
  up graceful shutdown, sizing an HPA, adding distributed locks for
  scheduled jobs, or building a service runbook/rollback plan — including
  when the codebase clearly uses Spring Boot (pom.xml/build.gradle with
  spring-boot-starter, @SpringBootApplication, application.yml) even if the
  user doesn't say "Spring Boot" explicitly.
---

# Spring Boot Production Operations: Config, Kubernetes, JVM

This skill turns Claude into a reliable Spring Boot engineer for running services in production, so operational setups built in month 1 and month 18 look like they came from the same team.

## Profiles & externalized config

- Profiles per *environment class*, kept few: `local`, `test`, `prod` (add `staging` only if it truly differs). Feature toggles are properties, not profiles — profile combinatorics get untestable fast.
- Precedence you rely on daily: env vars beat `application-<profile>.yml` beats `application.yml`. In K8s, config differences ship as env vars / mounted files, not as rebuilt images.
- `SPRING_PROFILES_ACTIVE=prod` set by the deployment, never baked into the image.
- Relaxed binding: property `app.payment.api-base-url` ↔ env `APP_PAYMENT_APIBASEURL`.
- **No secrets in the repo.** Anything secret comes from a Secret store (K8s Secret, Vault, cloud secret manager via `spring-cloud-*-config` or CSI driver), never `application.yml`.
- **Fail fast on config.** Verify at startup with validated `@ConfigurationProperties` — a pod that crash-loops on missing config is far better than one that limps.

## Graceful shutdown (zero-dropped-requests deploys)

```yaml
server:
  shutdown: graceful
spring:
  lifecycle:
    timeout-per-shutdown-phase: 30s
```

Kubernetes sequence to get right: pod gets SIGTERM → readiness goes false → load balancer drains → app finishes in-flight requests → exits. Add `terminationGracePeriodSeconds` ≥ your shutdown timeout, and a small `preStop` sleep (5s) so endpoints propagate before the JVM starts refusing:

```yaml
lifecycle:
  preStop:
    exec: { command: ["sh", "-c", "sleep 5"] }
```

## Kubernetes deployment skeleton

```yaml
apiVersion: apps/v1
kind: Deployment
metadata: { name: orders }
spec:
  replicas: 3
  strategy:
    rollingUpdate: { maxUnavailable: 0, maxSurge: 1 }
  template:
    spec:
      containers:
        - name: orders
          image: ghcr.io/acme/orders:<git-sha>
          ports: [{ containerPort: 8080 }]
          env:
            - name: SPRING_PROFILES_ACTIVE
              value: prod
            - name: DB_PASSWORD
              valueFrom: { secretKeyRef: { name: orders-db, key: password } }
          resources:
            requests: { cpu: "500m", memory: "768Mi" }
            limits: { memory: "768Mi" }        # memory limit yes; CPU limit often omitted (throttling hurts p99)
          startupProbe:
            httpGet: { path: /actuator/health/liveness, port: 8080 }
            failureThreshold: 30
            periodSeconds: 2
          livenessProbe:
            httpGet: { path: /actuator/health/liveness, port: 8080 }
            periodSeconds: 10
          readinessProbe:
            httpGet: { path: /actuator/health/readiness, port: 8080 }
            periodSeconds: 5
```

- **startupProbe** absorbs slow JVM boot so liveness doesn't kill a starting pod.
- Memory request = limit (Guaranteed-ish QoS) avoids OOM-kill surprises; the JVM sizes itself from the container limit.
- Migrations on deploy: Flyway-at-startup is fine while migrations are backward-compatible with the previous version (expand → deploy → contract). For long/locking migrations, run as a pre-deploy Job instead.

## JVM in containers

- Modern JVMs are container-aware; set `-XX:MaxRAMPercentage=75.0` rather than a fixed `-Xmx` so memory scales with the limit. The other ~25% covers metaspace, threads, direct buffers.
- Always: `-XX:+HeapDumpOnOutOfMemoryError -XX:HeapDumpPath=/tmp`.
- GC: default G1 is right for most services; ZGC (`-XX:+UseZGC`) when heap > ~8GB or p99 latency is GC-bound.
- Virtual threads (Java 21+, Boot 3.2+): `spring.threads.virtual.enabled: true` for I/O-heavy services — big concurrency win with no code change. Watch for `synchronized` blocks around I/O in old libs (pinning); prefer `ReentrantLock` in your own code.
- Prefer the current LTS Java in production (21 as safe default; 25 where the platform supports it) and the latest patch of the project's Spring Boot minor line.

## Scaling & resilience

- HPA on CPU or, better, on a work metric (requests-in-flight, queue lag) via custom metrics.
- Statelessness is a prerequisite: sessions (if any) in Redis (`spring-session-data-redis`), no local file state, caches either local-and-loss-tolerant or external.
- Every scheduled job in a multi-replica deployment needs a lock (ShedLock) or it runs N times.
- Rate limiting / bulkheads at the edge (gateway) plus Resilience4j on hot internal paths.

## Runbook items to create per service

1. Dashboard: golden signals + Hikari pool + GC pause + error-rate by endpoint.
2. Alerts: readiness-failing pods, 5xx rate, p99 latency, pool exhaustion, disk (if any), certificate/token expiry.
3. "How to roll back": `kubectl rollout undo` + which DB migrations are contract-phase (i.e., when rollback needs care).
4. Log queries for the three most common incidents this service has.

## Working style expectations

- When debugging a production incident, ask for (or find) the full stack trace, the active profile, and current dashboard/probe state before proposing fixes. Most "Spring is broken" reports are bean-wiring, profile, or classpath issues visible in the first 20 lines of the log.
- Explain *why* an operational convention applies when it changes user-written config — the user should learn the reasoning, not just accept edits.
