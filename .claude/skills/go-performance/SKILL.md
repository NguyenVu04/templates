---
name: go-performance
description: "Đo và tối ưu hiệu năng Go (Golang) — pprof, trace, benchmark, benchstat, memory allocation, GC tuning, escape analysis. Luôn dùng skill này khi người dùng nói code Go chậm, tốn RAM/CPU, memory leak, GC pressure, muốn profile/benchmark/tối ưu, hoặc hỏi làm sao biết bottleneck ở đâu. Nguyên tắc số 1 của skill: đo trước, sửa sau — không đoán."
---

# Go Performance

Quy trình tối ưu hiệu năng Go. **Không bao giờ tối ưu khi chưa đo.** Mọi đề xuất tối ưu phải kèm cách đo trước/sau.

## Quy trình chuẩn

1. Xác định triệu chứng: chậm ở latency, throughput, CPU, hay RAM?
2. Đo bằng công cụ phù hợp (bảng dưới)
3. Sửa **một thứ** ở điểm nóng nhất
4. Đo lại, so sánh bằng `benchstat`
5. Lặp — dừng khi đạt yêu cầu, không tối ưu tiếp "cho vui"

| Triệu chứng | Công cụ |
|---|---|
| CPU cao | `pprof` CPU profile |
| RAM cao / leak | `pprof` heap profile (so 2 thời điểm) |
| Latency thất thường, goroutine nghẽn | `pprof` goroutine/block/mutex, `go tool trace` |
| Hàm cụ thể chậm | benchmark + `-benchmem` |

## pprof

Service dài hạn — bật endpoint (chỉ expose nội bộ, không ra internet):
```go
import _ "net/http/pprof"
go http.ListenAndServe("localhost:6060", nil)
```

```bash
go tool pprof -http=:8081 http://localhost:6060/debug/pprof/profile?seconds=30  # CPU
go tool pprof -http=:8081 http://localhost:6060/debug/pprof/heap               # RAM
curl localhost:6060/debug/pprof/goroutine?debug=1                              # đếm goroutine (leak?)
```

Đọc flame graph: tìm khung **rộng nhất** (tự thân, không tính con). Trong heap profile: `inuse_space` cho leak, `alloc_space` cho GC pressure.

**Nghi memory leak:** chụp heap 2 lần cách nhau, so sánh:
```bash
go tool pprof -base heap1.out heap2.out
```
Goroutine tăng đều theo thời gian = goroutine leak (xem skill go-concurrency).

## Benchmark đúng cách

```go
func BenchmarkEncode(b *testing.B) {
    data := makeTestData()
    b.ResetTimer()
    for b.Loop() {
        Encode(data)
    }
}
```
```bash
go test -bench=Encode -benchmem -count=10 > old.txt
# ... sửa code ...
go test -bench=Encode -benchmem -count=10 > new.txt
benchstat old.txt new.txt   # chỉ tin kết quả có ý nghĩa thống kê (p < 0.05)
```
`-benchmem` bắt buộc: `allocs/op` thường quan trọng hơn `ns/op` cho service (GC pressure).

## Nguồn chậm phổ biến & cách sửa (sau khi đo xác nhận)

**Allocation:**
- `make([]T, 0, n)` / `make(map[K]V, n)` khi biết trước size
- `strings.Builder` thay `+=`; `[]byte` + `append` trong hot path
- `sync.Pool` cho buffer tái sử dụng ở tần suất rất cao (encode/decode) — đừng dùng sớm
- Escape analysis: `go build -gcflags='-m'` xem biến nào lên heap; giảm trả pointer không cần thiết trong hot path

**JSON:** `encoding/json` chậm với payload lớn tần suất cao → cân nhắc `goccy/go-json` (drop-in) hoặc đổi format (protobuf) nếu đo thấy JSON là bottleneck thật.

**Lock contention:** mutex profile chỉ ra → thu hẹp critical section, shard lock theo key, hoặc atomic.

**GC:** heap lớn ổn định + GC chạy nhiều → thử `GOGC=200` hoặc `GOMEMLIMIT` (Go 1.19+, đặt ~90% RAM limit của container). Chỉ tune sau khi đã giảm alloc.

**Database thường là thủ phạm thật:** trước khi tối ưu Go code, kiểm tra query chậm, thiếu index, N+1 (xem skill go-database). 80% case "Go chậm" là DB chậm.

## Anti-pattern

- Tối ưu theo cảm giác, không có profile chứng minh
- Micro-benchmark bị compiler loại bỏ dead code (dùng `b.Loop()` Go 1.24+ tự chống, hoặc gán kết quả ra biến package)
- Chạy benchmark 1 lần rồi kết luận (nhiễu máy — luôn `-count=10` + benchstat)
- `sync.Pool` / unsafe / cgo khi chưa vắt kiệt cách đơn giản
- Đánh đổi độ rõ ràng của code lấy 2% hiệu năng ở đường lạnh
