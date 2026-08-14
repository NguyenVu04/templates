---
name: go-idiomatic-review
description: Review, refactor và lint code Go (Golang) theo chuẩn idiomatic — Effective Go, Google Go Style Guide, golangci-lint. Luôn dùng skill này khi người dùng gửi code Go và nhờ review, hỏi "code này ổn chưa", "refactor giúp", "tối ưu code Go", muốn setup linter/CI, hoặc TRƯỚC KHI hoàn tất bất kỳ đoạn code Go nào bạn tự viết để tự kiểm tra lại theo checklist trong skill.
---

# Go Idiomatic Review

Checklist review/refactor code Go. Dùng để review code người dùng gửi VÀ tự soát code Go do chính mình sinh ra trước khi trả lời.

## Tooling — chạy trước khi đánh giá bằng mắt

```bash
gofmt -l .            # phải rỗng
go vet ./...
staticcheck ./...     # hoặc golangci-lint run
```

Cấu hình `golangci-lint` khởi điểm (`.golangci.yml`):
```yaml
linters:
  enable:
    - errcheck
    - govet
    - staticcheck
    - revive
    - gosec
    - errorlint      # bắt err == thay vì errors.Is
    - copyloopvar
    - unconvert
    - misspell
```

## Checklist review theo thứ tự ưu tiên

### 1. Đúng đắn
- Lỗi bị nuốt (`_ = f()`, err bị ghi đè trước khi check)
- Race: state chia sẻ giữa goroutine không có bảo vệ (yêu cầu chạy `-race`)
- Resource leak: thiếu `defer Close()` cho file/rows/resp.Body; thiếu `cancel()` cho context
- Nil dereference: nhận pointer/map/interface không check; ghi vào nil map
- Slice aliasing: append vào slice được truyền vào rồi trả về (caller bất ngờ bị sửa data)

### 2. API design
- "Accept interfaces, return structs" — tham số nhận interface hẹp, trả về type cụ thể
- Interface khai báo ở consumer, giữ nhỏ (1–3 method); interface 5+ method là red flag
- Zero value hữu dụng khi có thể (`var buf bytes.Buffer` dùng được ngay)
- Constructor `New...` chỉ khi cần validate/khởi tạo; functional options chỉ khi >3 tham số tùy chọn
- Context là tham số đầu, không nằm trong struct
- Không trả về type từ package `internal` qua API public

### 3. Idiom & style
- Early return / guard clause thay vì `else` lồng nhau; happy path ít thụt lề nhất
- Tên: ngắn trong scope hẹp (`i`, `r`, `buf`), mô tả trong scope rộng; KHÔNG stutter (`user.UserService` → `user.Service`); acronym viết đúng (`userID`, `parseURL`, không `userId`)
- Receiver: nhất quán pointer hoặc value cho cả type; pointer nếu có mutation hoặc struct lớn
- `any` thay `interface{}`; generics chỉ khi thật sự giảm lặp code, không phô diễn
- Dùng `log/slog` structured logging thay `fmt.Println`/`log.Printf` trong service
- Comment doc bắt đầu bằng tên symbol: `// ParseAmount parses...`; giải thích *why*, không diễn dịch code
- Struct tag json/db đầy đủ và đúng case khi có serialize

### 4. Hiệu năng (chỉ khi có dấu hiệu)
- Preallocate: `make([]T, 0, n)` khi biết size
- `strings.Builder` thay `+=` trong loop
- Tránh alloc trong hot path (kiểm bằng `-benchmem`, `pprof`) — KHÔNG tối ưu mù khi chưa đo
- Truyền struct lớn bằng pointer; struct nhỏ (<= vài word) bằng value là ổn

## Cách trình bày kết quả review

1. Tóm tắt 1–2 câu về tình trạng chung
2. Vấn đề nhóm theo mức: **Bug/Correctness** → **Design** → **Style** — mỗi vấn đề kèm đoạn code sửa cụ thể
3. Không liệt kê nitpick style nếu đang có bug nghiêm trọng hơn
4. Nêu rõ điều làm tốt để giữ lại
