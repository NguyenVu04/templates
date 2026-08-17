---
name: devops-engineering
description: >-
  Production-grade DevOps engineering across the full delivery lifecycle: writing Dockerfiles and
  docker-compose stacks, Kubernetes manifests/Helm/Kustomize, CI/CD pipelines (GitHub Actions,
  GitLab CI), Terraform/IaC, observability (Prometheus, Grafana, logging, tracing), secrets
  management, and incident response. Use this skill whenever the user mentions Docker, containers,
  Kubernetes, k8s, Helm, deployment, CI/CD, pipelines, GitHub Actions, Terraform, infrastructure,
  monitoring, alerting, SRE, rollback, zero-downtime, or asks to "deploy", "containerize",
  "set up CI", "provision infra", or debug production issues — even if they don't say "DevOps".
---

# DevOps Engineering

A skill for producing production-grade DevOps artifacts and making sound operational decisions. The core theme across every domain: **boring, reproducible, observable, and reversible**. Clever infra is a liability; predictable infra is an asset.

## How to use this skill

1. Identify which domain(s) the task touches (often more than one — e.g., "deploy my FastAPI app" = Docker + K8s/compose + CI/CD).
2. Read ONLY the relevant reference file(s) below before writing any config.
3. Apply the universal principles in this file regardless of domain.
4. Deliver working, complete artifacts — not fragments with `# ... rest of config` placeholders.

## Reference files — read before writing configs

| Task involves | Read |
|---|---|
| Dockerfile, docker-compose, image size, build speed, container security | `references/docker.md` |
| K8s manifests, Deployments, Services, Ingress, Helm, Kustomize, probes, HPA, resource limits | `references/kubernetes.md` |
| GitHub Actions, GitLab CI, build/test/deploy pipelines, caching, release automation | `references/cicd.md` |
| Terraform, provisioning cloud resources, state management, modules | `references/terraform.md` |
| Prometheus, Grafana, metrics, logs, tracing, alerting, SLOs | `references/observability.md` |
| Production incidents, debugging live systems, rollbacks, postmortems | `references/incident-response.md` |

## Universal principles (apply always)

### 1. Interrogate the context before generating

Before writing configs, establish (ask if not inferable):
- **Runtime & framework** — language, version, package manager (e.g., Python + `uv`, Go modules, pnpm).
- **Target environment** — local compose? single VM? managed K8s (EKS/GKE/DOKS)? serverless?
- **Scale reality** — a 3-person startup does not need a service mesh. Match complexity to actual need; recommend the simplest thing that works and note the upgrade path.
- **Existing conventions** — if the repo has existing CI files, Dockerfiles, or Terraform, read them first and match their style/structure rather than imposing a new one.

### 2. Security is not optional garnish

Non-negotiable defaults in every artifact:
- Never hardcode secrets. Use env vars injected from a secret store (K8s Secrets + external-secrets, GitHub Actions secrets, Vault, cloud secret managers). Flag any secret you see committed.
- Containers run as non-root, with pinned base image versions (never `latest` in production).
- Least privilege everywhere: minimal IAM roles, minimal K8s RBAC, minimal token scopes in CI (`permissions:` block in GitHub Actions).
- Pin action/module/chart versions (`actions/checkout@v4` at minimum; SHA-pin for high-security contexts).

### 3. Everything is code, everything is reviewable

- All infra changes go through version control and PR review — no console-clicking that leaves no trail.
- Configs must be idempotent: running twice yields the same result.
- Prefer declarative over imperative (manifests over `kubectl run`, Terraform over CLI scripts).

### 4. Design for failure

- Every deployment strategy must have a rollback story. State it explicitly when delivering a pipeline or deployment config.
- Health checks (liveness/readiness) are mandatory for anything serving traffic.
- Graceful shutdown: handle SIGTERM, drain connections, set sensible `terminationGracePeriodSeconds`.

### 5. Observability from day one

Any service you help deploy should answer three questions: Is it up? Is it slow? Why?
- Structured logs (JSON) to stdout/stderr — never log files inside containers.
- Expose basic metrics (request rate, errors, duration — the RED method).
- Alert on symptoms (user-facing error rate, latency) not causes (CPU%), and only on actionable conditions.

### 6. Output quality bar

- Deliver complete, runnable files. Include the commands to apply/verify them (`docker build ...`, `kubectl apply ... && kubectl rollout status ...`).
- Add brief comments explaining *why* for non-obvious choices (e.g., why a multi-stage build, why a specific probe delay) — not narrating what the syntax does.
- When multiple valid approaches exist, pick one, deliver it, and mention the main alternative in one sentence with the tradeoff.
- After generating, mentally dry-run the artifact: does the build context include what's COPYed? Do label selectors match? Do port numbers line up across Dockerfile → Service → Ingress? Mismatched selectors/ports are the #1 class of generated-config bugs.

## Anti-patterns to actively avoid

- `latest` tags, `privileged: true`, `runAsUser: 0` without stated justification.
- CI pipelines that build the image twice or don't cache dependencies.
- Terraform without remote state + locking for any team context.
- K8s Deployments without resource requests/limits (breaks scheduling and autoscaling).
- Alerting on everything (alert fatigue) or health checks that always return 200.
- Copy-pasting a "kitchen sink" config with features the user didn't ask for and doesn't need.
