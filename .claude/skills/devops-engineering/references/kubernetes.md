# Kubernetes

## Mandatory elements for any workload serving traffic

Every Deployment you write must include ALL of these — omitting any one causes real production incidents:

1. **Resource requests AND limits** — requests drive scheduling and HPA; missing them makes autoscaling meaningless. Rule of thumb: set memory limit = memory request (avoid OOM surprises from overcommit); set CPU request but consider omitting CPU limit (throttling hurts latency; CPU is compressible).
2. **Liveness + readiness probes** — readiness gates traffic; liveness restarts hung processes. They must hit DIFFERENT semantics: readiness = "can I serve?" (checks dependencies), liveness = "am I alive?" (must NOT check dependencies, or a DB blip restarts your whole fleet).
3. **Labels + matching selectors** — selector mismatch = zero endpoints = silent outage. Verify `spec.selector.matchLabels` == `template.metadata.labels`, and Service `selector` matches too.
4. **Pinned image tag** (digest or semver, never `latest` — `latest` + `IfNotPresent` means nodes silently run different code).
5. **securityContext** — `runAsNonRoot: true`, `allowPrivilegeEscalation: false`, `readOnlyRootFilesystem: true` where possible, drop all capabilities.
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

Companion Service + Ingress: Service `port: 80, targetPort: http`; Ingress with `ingressClassName`, TLS via cert-manager annotation. Verify the port chain: containerPort → Service targetPort → Ingress backend port.

## Config & secrets

- ConfigMap for non-sensitive config; Secret for credentials. Both mounted via `envFrom` or files.
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

## Deployment strategies & rollback

- Default: RollingUpdate with `maxUnavailable: 0` (zero-downtime, needs readiness probes to actually work).
- Rollback: `kubectl rollout undo deployment/api` (fast, built-in). Always run `kubectl rollout status deployment/api --timeout=120s` in CI after apply — an apply that "succeeds" can still be a crashlooping rollout.
- Blue/green and canary need extra machinery (Argo Rollouts, Flagger, or ingress weight shifting) — recommend only when the team's scale justifies it.
- Database migrations: run as a Job or initContainer BEFORE the rollout, and keep migrations backward-compatible one version (expand → migrate → contract) so rollback stays safe.

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
