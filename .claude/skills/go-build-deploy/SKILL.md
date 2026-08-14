---
name: go-build-deploy
description: Build, đóng gói và deploy ứng dụng Go (Golang) — Dockerfile multi-stage, static binary, cross-compile, ldflags nhúng version, GitHub Actions CI, GoReleaser. Luôn dùng skill này khi người dùng cần viết Dockerfile cho Go, setup CI/CD pipeline, giảm size image, build binary cho nhiều OS/arch, release CLI tool, hoặc chuẩn bị đưa service Go lên production/Kubernetes.
---

# Go Build & Deploy

Quy tắc đóng gói và deploy Go. Lợi thế lớn nhất của Go: **một static binary** — tận dụng tối đa.

## Dockerfile chuẩn (multi-stage, distroless)

```dockerfile
FROM golang:1.24-alpine AS build
WORKDIR /src

# Cache layer dependency — copy go.mod/go.sum TRƯỚC source
COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build \
    -ldflags="-s -w -X main.version=${VERSION:-dev}" \
    -o /app ./cmd/myservice

FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=build /app /app
EXPOSE 8080
USER nonroot:nonroot
ENTRYPOINT ["/app"]
```

Điểm mấu chốt:
- `CGO_ENABLED=0` → binary static, chạy được trên distroless/scratch (image ~10-15MB)
- `-ldflags "-s -w"` bỏ debug symbol, giảm ~30% size
- Copy `go.mod`/`go.sum` trước source → đổi code không phải tải lại dependency
- `distroless/static:nonroot` thay vì `scratch`: có sẵn CA certificates + user non-root. Cần timezone → `distroless/base`
- Cần CGO (sqlite...) → `distroless/base` hoặc alpine + `apk add libc6-compat`, không dùng static
- Build trong CI thêm cache mount: `RUN --mount=type=cache,target=/go/pkg/mod --mount=type=cache,target=/root/.cache/go-build go build ...`

## Nhúng version vào binary

```go
var (
    version = "dev"   // ghi đè bằng ldflags
    commit  = "none"
)
```
```bash
go build -ldflags "-X main.version=$(git describe --tags) -X main.commit=$(git rev-parse --short HEAD)"
```
Expose qua flag `--version` và endpoint `/healthz` — cứu mạng khi debug production.

## Cross-compile

```bash
GOOS=linux GOARCH=arm64 go build ./cmd/app   # không cần toolchain gì thêm (khi CGO_ENABLED=0)
```
Release CLI tool đa nền tảng → **GoReleaser**: một file `.goreleaser.yml` lo build matrix, archive, checksum, GitHub Release, Homebrew tap.

## GitHub Actions CI tối thiểu

```yaml
name: ci
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-go@v5
        with:
          go-version-file: go.mod
          cache: true
      - run: go vet ./...
      - uses: golangci/golangci-lint-action@v6
      - run: go test -race -coverprofile=coverage.out ./...
      - run: go build ./...
```
- `go-version-file: go.mod` — một nguồn version duy nhất
- `-race` trong CI là bắt buộc
- Bổ sung job `govulncheck ./...` quét lỗ hổng dependency

## Cấu hình runtime production

- Config qua **env var** (12-factor), fail-fast khi thiếu biến bắt buộc lúc khởi động
- Container/K8s: đặt `GOMEMLIMIT` (~90% memory limit) và `GOMAXPROCS` khớp CPU limit (`go.uber.org/automaxprocs`) — tránh GC thrashing và throttling
- Log ra stdout dạng JSON (`slog.NewJSONHandler`), để platform gom
- K8s probe: liveness → `/healthz`, readiness → `/readyz` (check DB); `terminationGracePeriodSeconds` > timeout shutdown của app

## Checklist trước khi lên production

- [ ] Image dưới 30MB, chạy non-root, không có shell (distroless)
- [ ] Binary có version/commit nhúng sẵn
- [ ] CI chạy vet + lint + test -race + govulncheck
- [ ] Graceful shutdown hoạt động (test bằng `docker stop`, phải thoát sạch trước 10s)
- [ ] `.dockerignore` có `.git`, `bin/`, file env
