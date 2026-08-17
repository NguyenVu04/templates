# Build & CI/CD

## Build flags

```bash
CGO_ENABLED=0 GOOS=linux GOARCH=amd64 \
go build -trimpath -ldflags "-s -w -X main.version=$(git describe --tags --always)" \
  -o bin/myservice ./cmd/myservice
```
- `CGO_ENABLED=0` → fully static binary, runs on scratch/distroless.
- `-s -w` strips symbol/debug tables (~30% smaller). Keep symbols in a debug build variant if you need server-side stack symbolization.
- `-trimpath` removes local paths → reproducible builds.
- `-X` injects version; expose it via a `/version` endpoint or `--version` flag:
```go
var version = "dev" // overridden by ldflags
```

## Dockerfile (multi-stage, the standard shape)

```dockerfile
# syntax=docker/dockerfile:1
FROM golang:1.24-alpine AS build
WORKDIR /src

# cache deps separately from source
COPY go.mod go.sum ./
RUN --mount=type=cache,target=/go/pkg/mod go mod download

COPY . .
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    CGO_ENABLED=0 go build -trimpath -ldflags "-s -w" -o /out/app ./cmd/myservice

FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=build /out/app /app
USER nonroot
EXPOSE 8080
ENTRYPOINT ["/app"]
```
- `distroless/static` over `scratch`: includes CA certs + tzdata + nonroot user. Final image ≈ binary size + ~2MB.
- The two `--mount=type=cache` lines make rebuilds seconds instead of minutes.
- Need `alpine` only if the container must have a shell for debugging (prefer `kubectl debug` ephemeral containers instead).

## GitHub Actions

`.github/workflows/ci.yml`:
```yaml
name: ci
on:
  push: { branches: [main] }
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-go@v5
        with:
          go-version-file: go.mod
          cache: true
      - run: go mod tidy && git diff --exit-code go.mod go.sum
      - run: go vet ./...
      - run: go build ./...
      - run: go test -race -coverprofile=cover.out ./...

  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-go@v5
        with: { go-version-file: go.mod }
      - uses: golangci/golangci-lint-action@v8
```
- `go-version-file: go.mod` → one source of truth for the Go version.
- The `git diff --exit-code` step fails PRs with an untidy go.mod.
- Integration tests with testcontainers work on ubuntu runners out of the box (Docker preinstalled).

**Build & push image** (on tag or main):
```yaml
  release:
    needs: [test, lint]
    if: startsWith(github.ref, 'refs/tags/v')
    runs-on: ubuntu-latest
    permissions: { contents: read, packages: write }
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: docker/build-push-action@v6
        with:
          push: true
          tags: ghcr.io/${{ github.repository }}:${{ github.ref_name }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

## Versioning & release

- SemVer git tags: `v1.2.3`. Go modules require the `v` prefix.
- `v2+` of a library needs `/v2` in the module path — for internal services, staying on `v0`/`v1` forever is fine and common.
- CLI/binary releases → `goreleaser` (cross-compiles, changelog, GitHub release, homebrew tap in one config).

## Pre-commit local loop

Mirror CI locally so pushes don't fail: `task lint && task test` (or a `lefthook`/`pre-commit` hook running gofumpt + golangci-lint on staged files). CI should never be the first place formatting errors appear.

## Supply chain hygiene

- `govulncheck ./...` in CI (only flags vulnerable code paths you actually call).
- Dependabot/Renovate for go.mod updates, weekly, grouped.
- Pin action versions; for high-security repos pin to SHAs.
