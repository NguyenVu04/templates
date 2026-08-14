---
name: devops-kubernetes
description: >-
  Production-grade Kubernetes engineering: Deployments, Services, Ingress, Helm charts, Kustomize
  overlays, probes, HPA/autoscaling, resource requests/limits, ConfigMaps/Secrets, rollout
  strategies, and debugging cluster workloads. Use this skill whenever the user mentions Kubernetes,
  k8s, kubectl, Helm, Kustomize, pods, Deployments, Ingress, HPA, CrashLoopBackOff, ImagePullBackOff,
  or asks to "deploy to k8s", write a manifest, set up autoscaling, or debug a pod that's crashing
  or not receiving traffic — even if they don't say "Kubernetes" explicitly.
---

# Kubernetes

A skill for producing production-grade Kubernetes manifests and making sound operational decisions on a cluster. The core theme: **boring, reproducible, observable, and reversible**. Clever YAML is a liability; predictable YAML is an asset.

## Before writing any manifest

Establish (ask if not inferable):
- **Target cluster** — managed K8s (EKS/GKE/DOKS/AKS)? on-prem? Affects storage classes, ingress controller, LB annotations.
- **Scale reality** — a 3-person startup does not need a service mesh or canary tooling. Match complexity to actual need; recommend the simplest thing that works and note the upgrade path.
- **Existing conventions** — if the repo already has manifests, Helm charts, or Kustomize overlays, read them first and match their style/structure rather than imposing a new one.

## Mandatory elements for any workload serving traffic

Every Deployment you write must include ALL of these — omitting any one causes real production incidents:

1. **Resource requests AND limits** — requests drive scheduling and HPA; missing them makes autoscaling meaningless and breaks the scheduler's bin-packing. Rule of thumb: set memory limit = memory request (avoid OOM surprises from overcommit); set CPU request but consider omitting CPU limit (throttling hurts latency; CPU is compressible).
2. **Liveness + readiness probes** — readiness gates traffic; liveness restarts hung processes. They must hit DIFFERENT semantics: readiness = "can I serve?" (checks dependencies), liveness = "am I alive?" (must NOT check dependencies, or a DB blip restarts your whole fleet).
3. **Labels + matching selectors** — selector mismatch = zero endpoints = silent outage. Verify `spec.selector.matchLabels` == `template.metadata.labels`, and Service `selector` matches too.
4. **Pinned image tag** (digest or semver, never `latest` — `latest` + `IfNotPresent` means nodes silently run different code).
5. **securityContext** — `runAsNonRoot: true`, `allowPrivilegeEscalation: false`, `readOnlyRootFilesystem: true` where possible, drop all capabilities. Never `runAsUser: 0` or `privileged: true` without stated justification. Least-privilege RBAC for any ServiceAccount the workload uses.
6. **Graceful shutdown** — app handles SIGTERM; `terminationGracePeriodSeconds` ≥ longest request; optionally `preStop: sleep 5` to let endpoint removal propagate before shutdown (avoids 502s during rollout).

## Reference Deployment template

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
  labels: {app: api}
spec:
  replicas: 3
  strategy:
    rollingUpdate: {maxSurge: 1, maxUnavailable: 0}   # zero-downtime
  selector:
    matchLabels: {app: api}
  template:
    metadata:
      labels: {app: api}
    spec:
      terminationGracePeriodSeconds: 30
      securityContext:
        runAsNonRoot: true
        runAsUser: 10001
        seccompProfile: {type: RuntimeDefault}
      containers:
        - name: api
          image: registry.example.com/api:1.4.2
          ports: [{containerPort: 8000, name: http}]
          envFrom:
            - configMapRef: {name: api-config}
            - secretRef: {name: api-secrets}
          resources:
            requests: {cpu: 250m, memory: 256Mi}
            limits: {memory: 256Mi}
          readinessProbe:
            httpGet: {path: /healthz/ready, port: http}
            initialDelaySeconds: 5
            periodSeconds: 5
            failureThreshold: 3
          livenessProbe:
            httpGet: {path: /healthz/live, port: http}
            initialDelaySeconds: 15
            periodSeconds: 10
            failureThreshold: 3
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities: {drop: [ALL]}
          lifecycle:
            preStop:
              exec: {command: [sh, -c, "sleep 5"]}
      affinity:
        podAntiAffinity:            # spread replicas across nodes
          preferredDuringSchedulingIgnoredDuringExecution:
            - weight: 100
              podAffinityTerm:
                labelSelector: {matchLabels: {app: api}}
                topologyKey: kubernetes.io/hostname
```

Companion Service + Ingress: Service `port: 80, targetPort: http`; Ingress with `ingressClassName`, TLS via cert-manager annotation. Verify the port chain: containerPort → Service targetPort → Ingress backend port — mismatched ports are the #1 class of generated K8s config bugs.

## Config & secrets

- ConfigMap for non-sensitive config; Secret for credentials — never hardcode secrets or credentials directly into a manifest.
- K8s Secrets are only base64 — for real security use External Secrets Operator / Sealed Secrets / cloud secret manager CSI, and enable encryption-at-rest on etcd.
- Changing a ConfigMap does NOT restart pods. Use a checksum annotation on the pod template (Helm: `checksum/config`), or Reloader, or rename the ConfigMap per version (Kustomize `configMapGenerator` does this automatically).

## Autoscaling (HPA)

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata: {name: api}
spec:
  scaleTargetRef: {apiVersion: apps/v1, kind: Deployment, name: api}
  minReplicas: 3
  maxReplicas: 12
  metrics:
    - type: Resource
      resource: {name: cpu, target: {type: Utilization, averageUtilization: 70}}
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300   # avoid flapping
```
HPA percentage is relative to **requests** — no requests, no HPA. Don't set `replicas:` in the Deployment manifest when HPA manages it (GitOps will fight the HPA).

## Helm vs Kustomize — how to choose

- **Kustomize**: same app, few environment variants (dev/staging/prod overlays), no templating logic needed. Simpler, built into kubectl. Default choice for your own apps.
- **Helm**: distributing to others, complex conditionals, dependency charts, or installing third-party software (ingress-nginx, Prometheus stack — always Helm).
- Either way, render and diff before applying: `helm template ... | kubectl diff -f -` or `kubectl diff -k overlays/prod`.
- All manifests belong in version control with PR review — no console-clicking or ad hoc `kubectl run`/`kubectl edit` that leaves no trail. Prefer declarative manifests over imperative commands; they must be idempotent (applying twice yields the same result).

## Deployment strategies & rollback

- Default: RollingUpdate with `maxUnavailable: 0` (zero-downtime, needs readiness probes to actually work).
- Every deployment strategy must have a rollback story stated explicitly. Rollback: `kubectl rollout undo deployment/api` (fast, built-in). Always run `kubectl rollout status deployment/api --timeout=120s` after apply — an apply that "succeeds" can still be a crashlooping rollout.
- Blue/green and canary need extra machinery (Argo Rollouts, Flagger, or ingress weight shifting) — recommend only when the team's scale justifies it.
- Database migrations: run as a Job or initContainer BEFORE the rollout, and keep migrations backward-compatible one version (expand → migrate → contract) so rollback stays safe.

## Observability baseline

Any workload you help deploy should answer: Is it up? Is it slow? Why?
- Structured logs (JSON) to stdout/stderr — never log files inside containers; let the platform's log agent ship them.
- Expose basic metrics (request rate, errors, duration — the RED method) via a `/metrics` endpoint scraped by Prometheus.
- Health checks (probes) are mandatory for anything serving traffic — see above.

## Debugging flow (in order)

```
kubectl get pods -o wide                     # status, restarts, node
kubectl describe pod <p>                     # Events section = 80% of answers
kubectl logs <p> [-c container] [--previous] # --previous for crashloops
kubectl get events --sort-by=.lastTimestamp
kubectl exec -it <p> -- sh                   # or kubectl debug for distroless
kubectl get endpoints <svc>                  # empty? selector mismatch
```

Common states → causes:
- `ImagePullBackOff` — typo in image, missing imagePullSecret, tag doesn't exist.
- `CrashLoopBackOff` — app exits: check `logs --previous`; often bad env/config or failed dependency at startup.
- `Pending` — unschedulable: insufficient resources (requests too high), node selectors/taints, PVC unbound. `describe` tells you.
- `OOMKilled` (exit 137) — raise memory limit or fix leak; check `kubectl top pod`.
- Service not reachable but pods Ready — selector/port mismatch, NetworkPolicy, or wrong `targetPort`.
- Readiness failing fleet-wide after deploy — probe checks a dependency that's down; that's what readiness is for, but if it's liveness doing it, you've caused a restart storm.

## Output quality bar

- Deliver complete, runnable manifests — not fragments with `# ... rest of config` placeholders. Include the apply/verify commands (`kubectl apply -f ... && kubectl rollout status ...`).
- Add brief comments explaining *why* for non-obvious choices (e.g., why a specific probe delay, why anti-affinity) — not narrating syntax.
- When multiple valid approaches exist (Helm vs Kustomize, RollingUpdate vs canary), pick one, deliver it, and mention the main alternative with its tradeoff in one sentence.

## Anti-patterns to actively avoid

- `latest` tags, `privileged: true`, `runAsUser: 0` without stated justification.
- Deployments without resource requests/limits (breaks scheduling and autoscaling).
- Health/readiness checks that always return 200 regardless of actual state.
- Copy-pasting a "kitchen sink" manifest with features (service mesh, canary, complex affinity) the user didn't ask for and doesn't need.
