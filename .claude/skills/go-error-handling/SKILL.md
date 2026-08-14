---
name: go-error-handling
description: Xử lý lỗi idiomatic trong Go (Golang). Luôn dùng skill này khi viết BẤT KỲ code Go nào có trả về error, khi người dùng hỏi về error wrapping, errors.Is/As/Join, sentinel error, custom error type, panic vs error, xử lý lỗi trong HTTP handler/gRPC, hoặc khi review code Go có pattern xử lý lỗi kém (nuốt lỗi, if err != nil lồng nhau, log rồi return err trùng lặp).
---

# Go Error Handling

Quy tắc xử lý lỗi khi viết hoặc review code Go. Lỗi là giá trị (errors are values) — xử lý tường minh, không giấu.

## Quy tắc bắt buộc

1. **Wrap với ngữ cảnh, dùng `%w`:**
   ```go
   if err != nil {
       return fmt.Errorf("fetch user %d: %w", id, err)
   }
   ```
   - Message ngắn, mô tả *thao tác đang làm*, không viết hoa, không kết thúc bằng dấu chấm, KHÔNG lặp lại chữ "failed to" ở mọi tầng (chuỗi wrap sẽ thành "failed to X: failed to Y: failed to Z").
   - Dùng `%w` khi caller cần `errors.Is/As`; dùng `%v` khi muốn *cắt* chain (che giấu chi tiết implement).

2. **Log HOẶC return — không bao giờ cả hai.** Log-and-return gây log trùng ở mọi tầng. Chỉ tầng ngoài cùng (handler, main) log.

3. **So sánh lỗi bằng `errors.Is` / `errors.As`, không bao giờ `err ==` hoặc so sánh chuỗi:**
   ```go
   if errors.Is(err, sql.ErrNoRows) { ... }

   var pgErr *pgconn.PgError
   if errors.As(err, &pgErr) && pgErr.Code == "23505" { ... }
   ```

4. **Sentinel error cho điều kiện caller cần phân nhánh:**
   ```go
   var ErrNotFound = errors.New("user: not found")
   ```
   Custom error type khi cần mang dữ liệu:
   ```go
   type ValidationError struct{ Field, Reason string }
   func (e *ValidationError) Error() string { return e.Field + ": " + e.Reason }
   ```

5. **`panic` chỉ dành cho bug lập trình** (invariant vỡ, init không thể tiếp tục). Không panic cho lỗi runtime bình thường (input xấu, mạng, DB). Trong thư viện: không bao giờ để panic thoát ra khỏi API public — recover ở boundary nếu cần.

6. **`errors.Join`** khi gom nhiều lỗi (cleanup, validate nhiều field, đóng nhiều resource trong defer).

7. **Defer + close:** đừng nuốt lỗi Close của writer:
   ```go
   defer func() { err = errors.Join(err, f.Close()) }()
   ```

## Pattern theo tầng ứng dụng

- **Repository/storage:** dịch lỗi driver sang lỗi domain (`sql.ErrNoRows` → `ErrNotFound`) để tầng trên không import driver.
- **Service:** wrap thêm ngữ cảnh nghiệp vụ, quyết định retry/không.
- **HTTP handler:** map lỗi domain → status code một chỗ duy nhất:
  ```go
  switch {
  case errors.Is(err, user.ErrNotFound):
      http.Error(w, "not found", http.StatusNotFound)
  case errors.As(err, &vErr):
      http.Error(w, vErr.Error(), http.StatusBadRequest)
  default:
      logger.Error("handler", "err", err)   // log ở đây, duy nhất
      http.Error(w, "internal error", http.StatusInternalServerError)
  }
  ```
  Không bao giờ trả `err.Error()` thô cho client ở nhánh 500 (lộ nội bộ).

## Anti-pattern cần bắt khi review

- `_ = someFunc()` nuốt lỗi không có comment giải thích
- `if err != nil { return err }` trần trụi xuyên nhiều tầng (mất ngữ cảnh)
- So sánh `err.Error() == "..."` hoặc `strings.Contains(err.Error(), ...)`
- Dùng error cho control flow bình thường có thể biểu diễn bằng `(value, bool)`
- Khai báo sentinel bằng `fmt.Errorf` mỗi lần gọi thay vì `var Err... = errors.New` cấp package
