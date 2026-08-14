---
name: devops-cicd
description: >-
  Production-grade CI/CD pipeline engineering: GitHub Actions workflows, GitLab CI pipelines,
  build/test/deploy stages, dependency and Docker layer caching, OIDC auth to cloud providers,
  release automation, and gated/observable deployments. Use this skill whenever the user mentions
  CI, CD, CI/CD, pipelines, GitHub Actions, GitLab CI, workflows, build automation, release
  automation, or asks to "set up CI", "add a deploy pipeline", "cache dependencies in CI", or debug
  a failing or slow pipeline — even if they don't say "CI/CD" explicitly.
---

# CI/CD Pipelines

A skill for producing production-grade CI/CD pipelines and making sound automation decisions. The core theme: **boring, reproducible, observable, and reversible**. A clever pipeline is a liability; a predictable one is an asset.

## Before writing any pipeline

Establish (ask if not inferable):
- **Runtime & framework** — language, version, package manager (e.g., Python + `uv`, Go modules, pnpm) — determines the setup/cache actions to use.
- **Target environment** — where does this deploy to (K8s, a VM, serverless, a registry only)?
- **Existing conventions** — if the repo already has CI files, read them first and match their style/structure rather than imposing a new one.

## Pipeline design principles

1. **Fast feedback first** — lint + unit tests before build; fail in 2 minutes, not 20. Order stages by (likelihood of failure × speed).
2. **Build once, promote everywhere** — build the image ONCE, tag with the git SHA, deploy that exact artifact to staging then prod. Never rebuild per environment (you'd deploy something you never tested).
3. **Cache aggressively** — dependency caches (uv/pip, go mod, pnpm) and Docker layer caches. An uncached pipeline wastes minutes on every run.
4. **Least-privilege tokens** — explicit `permissions:` block; OIDC to cloud providers instead of long-lived keys. This is a security non-negotiable, not a nice-to-have: pipelines are one of the highest-value credential targets in most orgs.
5. **Deployments are gated and observable** — protected environments for prod, `rollout status`-style verification after apply, rollback path documented in the pipeline itself. Every deploy job needs an explicit rollback story — state it when delivering the pipeline.
6. **Everything is code, reviewable** — pipeline definitions live in version control and go through PR review, same as application code. They should be idempotent: re-running a job should not corrupt state.

## GitHub Actions — reference CI workflow

```yaml
name: ci
on:
  pull_request:
  push:
    branches: [main]

permissions:
  contents: read

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true          # kill superseded runs on PRs

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
        with: {enable-cache: true}
      - run: uv sync --frozen
      - run: uv run ruff check . && uv run ruff format --check .
      - run: uv run pytest --cov --cov-report=xml
      # For services needing a DB, prefer `services:` containers over mocks:
      # services:
      #   postgres:
      #     image: postgres:16-alpine
      #     env: {POSTGRES_PASSWORD: test}
      #     options: >-
      #       --health-cmd pg_isready --health-interval 5s --health-retries 10
      #     ports: ["5432:5432"]

  build-push:
    needs: test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write               # push to GHCR
      id-token: write               # OIDC if pushing to cloud registries
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: docker/metadata-action@v5
        id: meta
        with:
          images: ghcr.io/${{ github.repository }}
          tags: |
            type=sha,format=long
            type=ref,event=branch
      - uses: docker/build-push-action@v6
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

## Deploy job pattern (K8s)

```yaml
  deploy-prod:
    needs: build-push
    runs-on: ubuntu-latest
    environment: production          # requires approval if configured
    permissions: {contents: read, id-token: write}
    steps:
      - uses: actions/checkout@v4
      # OIDC auth to cloud (example: AWS) — no stored keys
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789:role/gha-deploy
          aws-region: ap-southeast-1
      - run: aws eks update-kubeconfig --name prod-cluster
      - run: |
          kubectl set image deployment/api api=ghcr.io/${{ github.repository }}:sha-${{ github.sha }}
          kubectl rollout status deployment/api --timeout=180s
```

The `rollout status` line is the difference between "CI green" and "actually deployed". If it fails, the job fails, and `kubectl rollout undo` is the documented rollback.

For GitOps setups (Argo CD/Flux): CI's deploy step instead commits the new image tag to the config repo (or updates Kustomize `newTag`) and lets the GitOps controller reconcile. Don't mix push-deploy and GitOps on the same cluster.

## GitLab CI equivalent skeleton

```yaml
stages: [test, build, deploy]
default:
  interruptible: true

test:
  stage: test
  image: ghcr.io/astral-sh/uv:python3.12-bookworm-slim
  cache:
    key: {files: [uv.lock]}
    paths: [.uv-cache]
  variables: {UV_CACHE_DIR: .uv-cache}
  script:
    - uv sync --frozen
    - uv run ruff check . && uv run pytest

build:
  stage: build
  image: docker:27
  services: [docker:27-dind]
  rules: [{if: $CI_COMMIT_BRANCH == "main"}]
  script:
    - docker login -u $CI_REGISTRY_USER -p $CI_REGISTRY_PASSWORD $CI_REGISTRY
    - docker build --cache-from $CI_REGISTRY_IMAGE:cache
        --tag $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA .
    - docker push $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA
```

## Security in pipelines

- Never hardcode secrets in workflow files. Use the platform's secret store (GitHub Actions secrets, GitLab CI/CD variables) injected as env vars, and flag any secret you see committed.
- Pin actions to major version minimum; SHA-pin (`actions/checkout@<sha>`) for sensitive repos. Pin third-party actions/images just like you'd pin a dependency.
- Never `pull_request_target` with checkout of PR code (classic RCE-on-your-secrets vector).
- Secrets only in protected environments for deploy jobs; never echo them; mask custom values.
- Add scanning where it pays: `trivy` on the built image, dependency audit (`pip-audit`, `pnpm audit`, `govulncheck`) as a non-blocking job first, blocking once the baseline is clean.

## Release automation

- Tag-driven releases: `on: push: tags: ['v*']` → build, push `vX.Y.Z` + `latest`, create GitHub Release with generated notes.
- Semantic versioning from conventional commits if the team already uses them (release-please) — don't impose the convention just for tooling.

## Output quality bar

- Deliver complete, runnable workflow files — not fragments with `# ... rest of config` placeholders. State the rollback path explicitly for any deploy job.
- Add brief comments explaining *why* for non-obvious choices (e.g., why `cancel-in-progress`, why OIDC over static keys) — not narrating YAML syntax.
- When multiple valid approaches exist (push-deploy vs GitOps), pick one, deliver it, and mention the main alternative in one sentence with the tradeoff.
- After generating, mentally dry-run the pipeline: does every job that needs a secret actually have permission to read it? Do image tags produced in `build` match what `deploy` references?

## Common pipeline smells to fix on sight

- No `concurrency` cancel → queue of stale PR runs.
- Building the image in the test job AND the build job.
- `docker build` without any cache strategy in CI (every run from scratch).
- Deploy steps with `kubectl apply` but no `rollout status` (silent failures).
- One giant job — split test/build/deploy so failures are legible and parallelism works.
- Storing cloud keys as long-lived secrets when OIDC federation is available.
- Copy-pasting a "kitchen sink" workflow with jobs/triggers the user didn't ask for and doesn't need.
