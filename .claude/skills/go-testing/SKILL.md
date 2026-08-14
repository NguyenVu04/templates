---
name: go-testing
description: Viết test cho code Go (Golang) — table-driven test, subtests, mock qua interface, httptest, testcontainers, benchmark, fuzzing, coverage. Luôn dùng skill này khi người dùng yêu cầu viết test, unit test, integration test cho code Go, hỏi cách mock dependency, test HTTP handler/database, đo coverage, hoặc khi vừa viết xong một hàm Go quan trọng mà chưa có test đi kèm.
---

# Go Testing

Quy tắc viết test Go. Mục tiêu: test đọc như tài liệu đặc tả, chạy nhanh, không flaky.

## Table-driven test — dạng mặc định

```go
func TestParseAmount(t *testing.T) {
    tests := []struct {
        name    string
        input   string
        want    int64
        wantErr error
    }{
        {name: "valid", input: "10.50", want: 1050},
        {name: "negative", input: "-1", wantErr: ErrNegative},
        {name: "empty", input: "", wantErr: ErrEmpty},
    }
    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            got, err := ParseAmount(tt.input)
            if !errors.Is(err, tt.wantErr) {
                t.Fatalf("err = %v, want %v", err, tt.wantErr)
            }
            if got != tt.want {
                t.Errorf("got %d, want %d", got, tt.want)
            }
        })
    }
}
```

Quy ước:
- Tên case mô tả *hành vi*, không đánh số ("expired token rejected" thay vì "case 3")
- `t.Fatal` khi không thể tiếp tục, `t.Error` khi có thể check tiếp
- Test song song an toàn → thêm `t.Parallel()` trong subtest
- So sánh struct/slice phức tạp: `github.com/google/go-cmp/cmp` với `cmp.Diff` (in diff dễ đọc). Nếu project đã dùng `testify` thì theo convention sẵn có của project.

## Mock: interface nhỏ + fake viết tay

Không dùng mock framework nặng khi chưa cần. Khai báo interface ở phía consumer, viết fake trong file test:

```go
type stubRepo struct {
    user *User
    err  error
}
func (s *stubRepo) Get(ctx context.Context, id int64) (*User, error) { return s.user, s.err }
```

Chỉ dùng `gomock`/`mockery` khi interface lớn và project đã có sẵn.

## Test HTTP

```go
req := httptest.NewRequest(http.MethodGet, "/users/1", nil)
rec := httptest.NewRecorder()
handler.ServeHTTP(rec, req)
if rec.Code != http.StatusOK { ... }
```

Test client gọi ra ngoài: `httptest.NewServer` với handler giả — không bao giờ gọi mạng thật trong unit test.

## Integration test

- Database thật: `testcontainers-go` (Postgres/Redis container) hoặc docker-compose + build tag:
  ```go
  //go:build integration
  ```
  chạy riêng bằng `go test -tags=integration ./...`
- Dọn dẹp bằng `t.Cleanup(func(){...})` thay vì defer — chạy đúng thứ tự cả trong subtest.
- File test đặt `TestMain` nếu cần setup/teardown chung cho cả package.

## Benchmark & fuzz (khi liên quan hiệu năng / parser)

```go
func BenchmarkParse(b *testing.B) {
    for b.Loop() {          // Go 1.24+; bản cũ: for range b.N
        Parse(input)
    }
}
```
Chạy: `go test -bench=. -benchmem`. So sánh trước/sau bằng `benchstat`.

Fuzz cho hàm parse input không tin cậy: `func FuzzParse(f *testing.F)` + `go test -fuzz=FuzzParse -fuzztime=30s`.

## Checklist chất lượng test

- [ ] Chạy được với `go test -race ./...` — không flaky
- [ ] Không `time.Sleep` để đồng bộ; dùng channel/`synctest` (Go 1.24+) hoặc inject clock
- [ ] Không phụ thuộc thứ tự chạy, không dùng global state giữa các test
- [ ] Coverage: `go test -coverprofile=c.out ./... && go tool cover -html=c.out` — nhắm hành vi quan trọng, không chạy theo con số %
- [ ] Test lỗi (nhánh err) chứ không chỉ happy path
