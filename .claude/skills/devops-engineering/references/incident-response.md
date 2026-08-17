# Incident Response & Production Debugging

## Prime directive

**Mitigate first, diagnose later.** Restore service with the fastest safe lever (rollback, scale up, failover, feature-flag off), THEN find root cause on your own schedule. Debugging a live outage to satisfy curiosity extends the outage.

## First 5 minutes checklist

1. **What changed?** 80% of incidents follow a change. Check: recent deploys (`kubectl rollout history`), config changes, infra applies, dependency/provider status pages, certificate expiries, traffic anomalies.
2. **Scope it**: one endpoint or all? One region/AZ? One customer or everyone? Error type (5xx vs timeout vs connection refused) narrows layers fast.
3. **If a deploy correlates → roll back immediately.** `kubectl rollout undo deployment/X`. Don't debate whether it's "really" the deploy; rollback is cheap and reversible.
4. Communicate early: a two-line status ("investigating elevated 5xx on API since 14:02, suspecting deploy 1.4.3, rolling back") beats silence.

## Diagnosis by symptom

**Sudden 5xx spike**
- Deploy? → rollback. Not a deploy? → check dependency health (DB connections, downstream services), then resource exhaustion (OOMKills: `kubectl get pods` restarts column; connection pool saturation in metrics).

**Latency creep (no errors)**
- p99 vs p50: p99 only = tail issue (GC, one slow node, noisy neighbor, lock contention). Both up = systemic (DB slow query, missing index after data growth, CPU throttling from limits, cache hit-rate drop).
- Check CPU throttling explicitly: `container_cpu_cfs_throttled_periods_total` — throttled pods look "healthy" while latency burns.

**Connection refused / timeouts**
- Work up the chain: pod ready? (`kubectl get endpoints` — empty means selector/readiness issue) → Service ports match? → NetworkPolicy? → Ingress/LB health checks passing? → DNS (`nslookup` from a debug pod)?

**Everything restarting**
- Liveness probes checking a dependency that blipped (restart storm — the classic self-inflicted outage). Node pressure evictions (`kubectl describe node`). OOM cascade after a traffic shift.

**Database incidents**
- Connection exhaustion (each pod × pool size vs `max_connections` — a scale-up event can DoS your own DB). Long-running transactions blocking (check `pg_stat_activity`). Disk full (WAL growth).

**It's always DNS / certs / disk space** — check the boring trio early: `df -h`, cert expiry (`openssl s_client -connect host:443 | openssl x509 -noout -dates`), DNS resolution.

## Mitigation levers (fastest → slowest)

1. Rollback deploy / revert config
2. Feature flag off the offending path
3. Scale horizontally (`kubectl scale`) — buys time for saturation issues
4. Restart (fixes leaks/wedged state; note it destroys evidence — grab logs/heap first if cheap)
5. Shed load: rate limit, disable expensive endpoints, serve degraded responses
6. Failover region/replica

## During the incident

- One person drives (incident commander), others investigate assigned threads — parallel uncoordinated kubectl-ing makes it worse.
- Keep a timestamped log of observations and actions (paste commands + outputs into the incident channel). This becomes the postmortem timeline for free.
- Resist multi-change fixes: change one thing, observe, then next. Simultaneous changes make cause attribution impossible.

## Postmortem (blameless, within a few days)

Structure:
1. **Impact** — duration, users/requests affected, revenue/SLO burn.
2. **Timeline** — detection → mitigation → resolution, with timestamps. Note detection gap (how long broken before anyone knew — this drives monitoring improvements).
3. **Root cause(s)** — technical chain, not "human error". If a human mistake caused it, the root cause is the system that allowed one mistake to become an outage (missing validation, no canary, no rate limit on the lever).
4. **Action items** — each with an owner and a date; distinguish "prevent recurrence" from "detect faster" from "mitigate faster". Cap at ~5; a 20-item list means zero get done.

The test of a good postmortem: would the action items have prevented, or materially shortened, this incident?

## Preparedness (recommend proactively when helping with deployments)

- Runbooks for every paging alert (symptoms → checks → levers).
- Practice rollback before you need it — an untested rollback path is a hypothesis.
- Backups are only real if restores are tested (schedule restore drills).
- Chaos-lite: kill a pod in staging and confirm zero user impact; expire a cert in a test env and confirm alerting catches it.
