# Observability: Metrics, Logs, Traces, Alerts

## The mental model

Three signals, three jobs:
- **Metrics** (Prometheus) — cheap, aggregated, answer "is something wrong and how wrong?" Drive alerts and dashboards.
- **Logs** (Loki/ELK/cloud) — discrete events with context, answer "what exactly happened?"
- **Traces** (OpenTelemetry → Tempo/Jaeger) — request-scoped causality across services, answer "where in the chain is it slow/failing?" Only worth the setup cost once you have >2–3 services in a request path.

Instrument with **OpenTelemetry SDKs** by default — vendor-neutral, covers all three signals, auto-instrumentation exists for FastAPI/Express/Spring/Gin.

## Metrics: the RED method (for every service)

Expose per-service:
- **R**ate — requests/sec
- **E**rrors — failed requests/sec
- **D**uration — latency histogram (so you can compute p50/p95/p99)

For infrastructure, USE method: Utilization, Saturation, Errors per resource.

Prometheus specifics:
- Histograms over summaries (aggregatable across pods).
- Label cardinality discipline: never label by user ID, request ID, or full URL path — each unique combo is a new time series. Route templates (`/users/{id}`) not raw paths.
- App exposes `/metrics`; scraped via ServiceMonitor (kube-prometheus-stack) or pod annotations.

Key PromQL patterns:
```promql
# request rate
sum(rate(http_requests_total[5m])) by (service)
# error ratio
sum(rate(http_requests_total{code=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))
# p99 latency from a histogram
histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))
```

## Logging rules

- **Structured JSON to stdout/stderr.** The platform (K8s + agent: Promtail/Fluent Bit/vector) handles shipping. Apps never write log files or ship logs themselves.
- Every log line: timestamp, level, message, service, and **trace_id/request_id** for correlation — this join key is what makes logs actually useful during incidents.
- Levels mean something: ERROR = someone may need to act; WARN = degraded but handled; INFO = state changes (started, config loaded, job done); DEBUG = off in prod by default.
- Never log secrets, tokens, passwords, full card numbers. Redact at the logging-config layer, not by hoping.
- Log volume is a cost — a chatty INFO log in a hot path can dwarf your compute bill. Sample or demote.

## Alerting philosophy (this is where most teams fail)

- **Alert on symptoms, not causes.** Page on "error rate > 2% for 5m" or "p99 > 1s", not "CPU > 80%" (CPU at 90% with fine latency is just good utilization).
- **Every page must be actionable and urgent.** If the response is "look at it Monday", it's a ticket, not a page. Alert fatigue is how real incidents get ignored.
- Two severities are enough to start: `page` (wake someone) and `ticket` (async).
- Use `for:` durations to avoid flapping; route via Alertmanager with inhibition (don't page 40 times when a node dies).

Example rule:
```yaml
groups:
  - name: api-slo
    rules:
      - alert: HighErrorRate
        expr: |
          sum(rate(http_requests_total{job="api",code=~"5.."}[5m]))
            / sum(rate(http_requests_total{job="api"}[5m])) > 0.02
        for: 5m
        labels: {severity: page}
        annotations:
          summary: "API error rate {{ $value | humanizePercentage }} over 5m"
          runbook_url: https://wiki.example.com/runbooks/api-errors
```
Every paging alert links a runbook. No runbook, no page.

## SLOs (when the team is ready)

- Pick 1–2 SLIs per service (availability, latency), set a target from actual current performance minus a little slack (99.9% only if you can staff it).
- Error budget = 1 − SLO. Burn-rate alerts (fast burn 14.4× over 1h = page; slow burn 3× over 6h = ticket) replace threshold-guessing.
- SLO dashboards make "should we ship features or fix reliability" a data question instead of a fight.

## Standard stack recommendation

Self-hosted on K8s: **kube-prometheus-stack** Helm chart (Prometheus + Alertmanager + Grafana + node/kube metrics preconfigured) + **Loki** (+ Promtail/Alloy) for logs + **Tempo** for traces when needed. Managed alternatives (Grafana Cloud, Datadog, CloudWatch) trade money for operational burden — reasonable for small teams; state the tradeoff rather than defaulting either way.

## Dashboard hygiene

- One overview dashboard per service: RED metrics top row, saturation (CPU/mem vs limits, restarts) second row, dependencies third.
- Dashboards answer questions, they aren't art. Every panel should map to a decision or diagnosis step.
- Use Grafana provisioning (dashboards as JSON/Jsonnet in git), not hand-edited dashboards that die with the pod.
