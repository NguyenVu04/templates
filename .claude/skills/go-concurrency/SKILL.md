---
name: go-concurrency
description: Viết code concurrent an toàn trong Go (Golang) — goroutine, channel, context, sync, errgroup, worker pool. Luôn dùng skill này khi code Go có từ khóa go/chan/select/sync/context, khi người dùng nhắc đến goroutine leak, race condition, deadlock, timeout, cancellation, xử lý song song, rate limiting, hoặc bất kỳ tác vụ nào chạy nhiều việc đồng thời (crawl, fan-out API call, pipeline xử lý dữ liệu).
---

# Go Concurrency

Quy tắc viết và review code concurrent trong Go. Mặc định: **đơn giản trước, concurrent sau khi đo thấy cần.**

## Quy tắc bắt buộc

1. **Mọi goroutine phải có đường thoát rõ ràng.** Trước khi viết `go func()`, trả lời được: goroutine này kết thúc khi nào, ai chờ nó? Nếu không trả lời được → goroutine leak.

2. **`context.Context` là tham số đầu tiên** của mọi hàm có I/O hoặc có thể chạy lâu. Không lưu context trong struct. Luôn `defer cancel()` ngay sau `context.WithTimeout/WithCancel`.

3. **Mặc định dùng `errgroup` thay vì WaitGroup thô** cho fan-out có lỗi:
   ```go
   g, ctx := errgroup.WithContext(ctx)
   g.SetLimit(10)                      // giới hạn concurrency, thay worker pool thủ công
   for _, url := range urls {
       g.Go(func() error {             // Go 1.22+: biến loop tự capture đúng
           return fetch(ctx, url)
       })
   }
   if err := g.Wait(); err != nil { ... }
   ```

4. **Chọn công cụ đúng việc:**
   - Bảo vệ state chia sẻ đơn giản → `sync.Mutex` (đừng cố dùng channel cho việc này)
   - Truyền dữ liệu / pipeline / signal → channel
   - Fan-out N việc + gom lỗi → `errgroup`
   - Khởi tạo một lần → `sync.Once` / `sync.OnceValue`
   - Counter đơn giản → `atomic.Int64`

5. **Bên gửi đóng channel, không bao giờ bên nhận.** Không đóng channel có nhiều sender (dùng done-channel hoặc context để báo dừng).

6. **`select` với context để không block vĩnh viễn:**
   ```go
   select {
   case out <- result:
   case <-ctx.Done():
       return ctx.Err()
   }
   ```

7. **Luôn chạy test với `-race`.** Mọi lệnh test trong Makefile/CI: `go test -race ./...`. Race detector không bắt được deadlock — review logic channel bằng tay.

## Pattern hay dùng

**Timeout cho một call:**
```go
ctx, cancel := context.WithTimeout(ctx, 3*time.Second)
defer cancel()
```

**Pipeline có cancellation:** mỗi stage nhận `ctx`, mọi send/receive đều nằm trong `select` với `ctx.Done()`.

**Rate limit:** `golang.org/x/time/rate` (`rate.NewLimiter`), không tự chế bằng `time.Sleep`.

**Graceful shutdown server:**
```go
ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
defer stop()
// ... <-ctx.Done() → srv.Shutdown(shutdownCtx)
```

## Anti-pattern cần bắt

- `go func()` không có cách nào dừng/chờ (fire-and-forget với I/O)
- Ghi map/slice chia sẻ từ nhiều goroutine không có mutex
- `time.Sleep` để "chờ goroutine xong" trong test hoặc code thật
- Buffered channel với size "đoán đại" để giấu deadlock
- Copy struct chứa Mutex (chạy `go vet` sẽ bắt — luôn dùng pointer receiver cho struct có lock)
- Dùng `sync.Map` mặc định — chỉ dùng cho case đọc nhiều/ghi ít với key ổn định; bình thường `map + RWMutex` nhanh và rõ hơn
