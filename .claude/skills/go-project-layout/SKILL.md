---
name: go-project-layout
description: Chuẩn hóa cách khởi tạo và tổ chức dự án Go (Golang). Luôn dùng skill này khi người dùng muốn tạo project Go mới, refactor cấu trúc thư mục, thiết lập go.mod, tổ chức package, thêm Makefile/CI, hoặc hỏi "cấu trúc dự án Go thế nào cho chuẩn", "project layout", "monorepo Go", "internal package". Áp dụng cả khi người dùng chỉ nói "tạo cho tôi một service Go" mà không nhắc đến layout.
---

# Go Project Layout

Hướng dẫn khởi tạo và tổ chức dự án Go theo chuẩn cộng đồng (golang-standards/project-layout, Google Go Style Guide) — nhưng KHÔNG over-engineer.

## Nguyên tắc cốt lõi

1. **Bắt đầu phẳng, tách dần khi cần.** Dự án nhỏ chỉ cần `main.go` + vài file cùng package. Đừng tạo sẵn 10 thư mục rỗng.
2. **`internal/` là hàng rào import.** Code không muốn bị module khác import → đặt trong `internal/`. Compiler tự chặn.
3. **Package đặt tên theo *chức năng cung cấp*, không theo *loại code*.** Dùng `user`, `billing`, `httpserver` — tránh `utils`, `helpers`, `common`, `models` (dấu hiệu thiết kế kém).
4. **Không dùng `pkg/` trừ khi thật sự publish thư viện.** Đây là convention gây tranh cãi; mặc định bỏ qua.

## Layout chuẩn cho service backend

```
myservice/
├── go.mod
├── go.sum
├── Makefile
├── cmd/
│   └── myservice/
│       └── main.go        # chỉ wire dependencies + start, < 100 dòng
├── internal/
│   ├── config/            # load env/flags (dùng envconfig hoặc koanf)
│   ├── server/            # HTTP/gRPC handlers, routing, middleware
│   ├── user/              # domain package: service + repository interface
│   ├── storage/
│   │   └── postgres/      # implement repository interfaces
│   └── platform/          # logger, metrics, tracing setup
├── api/                   # OpenAPI spec, .proto files
├── migrations/            # SQL migrations (golang-migrate)
└── deployments/           # Dockerfile, k8s manifests, compose
```

Thư viện đơn thuần: để package chính ở root (`go-redis`, `chi` đều làm vậy), example trong `examples/`.

## Quy trình khởi tạo

```bash
go mod init github.com/<user>/<repo>   # LUÔN dùng full module path
mkdir -p cmd/<app> internal
```

- `main.go` trong `cmd/<app>/` chỉ làm: parse config → khởi tạo deps → inject → run → graceful shutdown (bắt SIGINT/SIGTERM với `signal.NotifyContext`).
- Dependency injection thủ công qua constructor (`NewUserService(repo, logger)`). Không dùng DI framework trừ khi user yêu cầu (wire/fx).
- Interface khai báo ở **phía consumer**, không phải phía implementer ("accept interfaces, return structs").

## Makefile tối thiểu

```makefile
.PHONY: build test lint run

build:
	go build -o bin/app ./cmd/myservice

test:
	go test -race -cover ./...

lint:
	go vet ./... && staticcheck ./...

run:
	go run ./cmd/myservice
```

## Checklist khi tạo project mới

- [ ] `go.mod` với module path đầy đủ, Go version mới nhất ổn định
- [ ] `.gitignore` có `bin/`, `*.out`, `.env`
- [ ] `main.go` có graceful shutdown với context
- [ ] Không có package `utils`/`common`
- [ ] README ghi lệnh build/test/run
- [ ] Nếu là service: health check endpoint (`/healthz`), structured logging (`log/slog`) ngay từ đầu
