---
name: go-http-api
description: Xây dựng HTTP/REST API bằng Go (Golang) — net/http router 1.22+, chi, middleware, JSON encode/decode, validation, timeout, CORS, auth, versioning. Luôn dùng skill này khi người dùng viết web server, REST API, endpoint, handler, middleware bằng Go, hỏi nên dùng framework nào (Gin/Echo/chi/net/http), hoặc khi thiết kế request/response cho service Go.
---

# Go HTTP API

Quy tắc xây REST API bằng Go. Mặc định: **`net/http` chuẩn (Go 1.22+) hoặc chi** — đủ cho đa số service; chỉ dùng Gin/Echo khi project đã có sẵn.

## Router: net/http 1.22+ đã đủ

```go
mux := http.NewServeMux()
mux.HandleFunc("GET /users/{id}", h.getUser)
mux.HandleFunc("POST /users", h.createUser)

id := r.PathValue("id")   // lấy path param
```
Cần middleware chaining + route group tiện hơn → `chi` (tương thích 100% net/http).

## Server: luôn set timeout

```go
srv := &http.Server{
    Addr:              ":8080",
    Handler:           mux,
    ReadHeaderTimeout: 5 * time.Second,
    ReadTimeout:       10 * time.Second,
    WriteTimeout:      30 * time.Second,
    IdleTimeout:       120 * time.Second,
}
```
`http.ListenAndServe(":8080", mux)` trần trụi không có timeout — cấm ở production (slowloris). Graceful shutdown: xem skill go-concurrency.

## Handler pattern

Handler là method của struct chứa dependency, không dùng global:

```go
type UserHandler struct {
    svc    *user.Service
    logger *slog.Logger
}

func (h *UserHandler) createUser(w http.ResponseWriter, r *http.Request) {
    var req CreateUserRequest
    if err := decodeJSON(r, &req); err != nil {
        respondError(w, http.StatusBadRequest, err.Error())
        return
    }
    u, err := h.svc.Create(r.Context(), req.toInput())
    if err != nil {
        h.respondDomainError(w, err)   // map lỗi domain → status, một chỗ duy nhất
        return
    }
    respondJSON(w, http.StatusCreated, toUserResponse(u))
}
```

Quy tắc:
- **DTO riêng cho request/response** — không expose struct domain/DB trực tiếp qua JSON
- Luôn dùng `r.Context()` truyền xuống service
- Decode JSON có giới hạn và chặt chẽ:
  ```go
  r.Body = http.MaxBytesReader(w, r.Body, 1<<20) // 1MB
  dec := json.NewDecoder(r.Body)
  dec.DisallowUnknownFields()
  ```
- Validation: check tay cho case đơn giản, `go-playground/validator` khi nhiều rule; trả lỗi theo field:
  ```json
  {"error": "validation failed", "fields": {"email": "invalid format"}}
  ```

## Response helper — viết một lần

```go
func respondJSON(w http.ResponseWriter, status int, v any) {
    w.Header().Set("Content-Type", "application/json")
    w.WriteHeader(status)
    if err := json.NewEncoder(w).Encode(v); err != nil {
        slog.Error("encode response", "err", err)
    }
}
```
Format lỗi thống nhất toàn API (cân nhắc RFC 9457 problem+json cho API public).

## Middleware

Thứ tự chuẩn (ngoài → trong): RequestID → Logging → Recover(panic→500) → CORS → Auth → RateLimit → Handler.

```go
func Recover(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        defer func() {
            if rec := recover(); rec != nil {
                slog.Error("panic", "err", rec, "stack", string(debug.Stack()))
                http.Error(w, "internal error", http.StatusInternalServerError)
            }
        }()
        next.ServeHTTP(w, r)
    })
}
```

- Auth: truyền user/claims xuống qua `context.WithValue` với key type riêng (unexported type), viết helper `UserFromContext(ctx)`
- CORS: dùng `rs/cors`, không tự viết; không bao giờ `Access-Control-Allow-Origin: *` kèm credentials

## Checklist API production

- [ ] Mọi endpoint trả JSON lỗi thống nhất, không lộ `err.Error()` nội bộ ở 500
- [ ] `GET /healthz` (liveness) và `/readyz` (check DB) tách riêng
- [ ] Status code đúng nghĩa: 201 create, 204 delete, 400 input, 401/403 phân biệt rõ, 404, 409 conflict, 422 validation (chọn 400 hoặc 422 và nhất quán)
- [ ] Pagination cho list endpoint (limit/offset hoặc cursor) ngay từ đầu
- [ ] Version qua path `/api/v1/` cho API public
- [ ] Request logging có method, path, status, duration, request_id
