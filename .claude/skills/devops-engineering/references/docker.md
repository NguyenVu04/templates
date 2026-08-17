# Docker & Containers

## Dockerfile checklist (every production image)

1. **Pinned, minimal base image** — `python:3.12-slim-bookworm`, `golang:1.23-alpine` (build) → `gcr.io/distroless/static` or `scratch` (run), `node:22-slim`. Never bare `latest`.
2. **Multi-stage build** — build stage has compilers/dev deps; final stage has only the runtime artifact.
3. **Non-root user** — create and switch: `USER app` (or use distroless `nonroot`).
4. **Layer ordering for cache** — copy dependency manifests first, install deps, THEN copy source. Source changes shouldn't bust the dependency layer.
5. **`.dockerignore`** — always create one: `.git`, `node_modules`, `.venv`, `__pycache__`, `*.md`, test data, `.env`.
6. **One process per container**; logs to stdout/stderr; handle SIGTERM (use exec-form `CMD ["binary"]`, not shell form, so PID 1 receives signals — or `tini` if the app spawns children).
7. **HEALTHCHECK** for compose/standalone (K8s uses probes instead; a HEALTHCHECK there is ignored).
8. **Expose config via env vars**, defaults via `ENV`, never bake environment-specific values into the image. Same image runs in dev/staging/prod.

## Templates

### Python + uv (multi-stage)

```dockerfile
FROM python:3.12-slim-bookworm AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
# Deps layer — cached until lockfile changes
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

FROM python:3.12-slim-bookworm
RUN groupadd -r app && useradd -r -g app app
WORKDIR /app
COPY --from=builder --chown=app:app /app /app
ENV PATH="/app/.venv/bin:$PATH"
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Go (static binary → distroless)

```dockerfile
FROM golang:1.23-alpine AS builder
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o /out/server ./cmd/server

FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=builder /out/server /server
EXPOSE 8080
ENTRYPOINT ["/server"]
```

### Node.js (pnpm)

```dockerfile
FROM node:22-slim AS builder
RUN corepack enable
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY . .
RUN pnpm build && pnpm prune --prod

FROM node:22-slim
WORKDIR /app
COPY --from=builder --chown=node:node /app/dist ./dist
COPY --from=builder --chown=node:node /app/node_modules ./node_modules
COPY --chown=node:node package.json ./
USER node
EXPOSE 3000
CMD ["node", "dist/main.js"]
```

## docker-compose for local dev

Principles: compose is for **local development and small single-host deployments** — don't replicate production K8s in compose.

```yaml
services:
  api:
    build:
      context: .
      target: builder        # dev can stop at builder stage for hot reload tooling
    ports: ["8000:8000"]
    environment:
      DATABASE_URL: postgresql+asyncpg://app:app@db:5432/app
    env_file: .env           # gitignored; commit .env.example instead
    volumes:
      - ./src:/app/src       # hot reload in dev only
    depends_on:
      db:
        condition: service_healthy
    develop:
      watch:                 # `docker compose watch` — preferred over bind mounts for sync
        - action: sync
          path: ./src
          target: /app/src

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: app
      POSTGRES_PASSWORD: app
      POSTGRES_DB: app
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app"]
      interval: 5s
      timeout: 3s
      retries: 10

volumes:
  pgdata:
```

Key details:
- `depends_on` + `condition: service_healthy` — plain `depends_on` only waits for start, not readiness. This is the most common compose bug.
- Named volumes for data; bind mounts only for source code in dev.
- No `container_name` (breaks scaling), no `restart: always` in dev.

## Image size & build speed

- Order of impact: multi-stage > slim/alpine/distroless base > cache mounts (`RUN --mount=type=cache`) > combining RUN layers.
- Alpine caveat for Python: musl vs glibc wheel issues — prefer `-slim` (Debian) for Python; alpine is great for Go/static binaries.
- Check what's bloating an image: `docker history <image>` or `dive <image>`.
- In CI, use BuildKit with registry cache: `docker buildx build --cache-from type=registry,ref=IMG:cache --cache-to type=registry,ref=IMG:cache,mode=max`.

## Container security quick list

- `USER` non-root; `securityOpt: no-new-privileges` in compose.
- Scan in CI: `trivy image --exit-code 1 --severity CRITICAL,HIGH <image>`.
- Don't mount the Docker socket into containers unless the tool's entire purpose requires it — it's root on the host.
- Secrets: BuildKit secret mounts for build-time (`RUN --mount=type=secret,id=pip_token ...`), env/secret stores at runtime. Never `ARG` for secrets (persists in image history).

## Debugging containers

- `docker logs -f --tail 100 <c>` · `docker exec -it <c> sh` · `docker inspect <c>` (check `State.OOMKilled`, exit code).
- Exit code 137 = SIGKILL (usually OOM); 139 = segfault; 143 = SIGTERM (normal stop).
- Distroless has no shell — debug with `docker run --entrypoint`, an ephemeral debug variant, or `kubectl debug` in K8s.
