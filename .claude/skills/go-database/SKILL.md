---
name: go-database
description: Làm việc với database trong Go (Golang) — database/sql, pgx, sqlc, GORM, transaction, connection pool, migration, tránh SQL injection và N+1. Luôn dùng skill này khi code Go có truy vấn SQL/Postgres/MySQL/SQLite, khi người dùng hỏi nên dùng ORM hay raw SQL, cách quản lý transaction, setup migration, repository pattern, hoặc khi viết bất kỳ tầng storage/repository nào cho service Go.
---

# Go Database

Quy tắc viết tầng truy cập dữ liệu trong Go. Postgres là mặc định trừ khi nói khác.

## Chọn công cụ

| Tình huống | Chọn |
|---|---|
| Postgres, muốn hiệu năng + type-safe | **pgx** (driver) + **sqlc** (sinh code từ SQL) — mặc định khuyên dùng |
| Cần đổi DB dễ, query đơn giản | `database/sql` + driver tương ứng |
| Team quen ORM, CRUD nhiều bảng nhanh | GORM — nhưng cấm dùng cho query phức tạp (viết raw) |
| Query build động nhiều điều kiện | `squirrel` hoặc sqlc + điều kiện trong SQL |

sqlc: viết SQL thật trong file `.sql`, sinh Go code type-safe — được cả hiệu năng lẫn an toàn, không học DSL của ORM.

## Quy tắc bắt buộc

1. **Không bao giờ nối chuỗi vào SQL.** Luôn placeholder (`$1` với pgx, `?` với MySQL). Kể cả tên bảng/cột động → whitelist từ hằng số, không lấy từ input.

2. **Luôn nhận `ctx` và truyền xuống:** `QueryContext`, `ExecContext`, `pool.Query(ctx, ...)`. Query không có context là query không hủy được.

3. **`defer rows.Close()` và check `rows.Err()` sau vòng lặp:**
   ```go
   rows, err := db.QueryContext(ctx, q, id)
   if err != nil { return nil, fmt.Errorf("query users: %w", err) }
   defer rows.Close()
   for rows.Next() { ... }
   if err := rows.Err(); err != nil { return nil, fmt.Errorf("iterate users: %w", err) }
   ```

4. **Transaction: helper một chỗ, rollback an toàn:**
   ```go
   func (s *Store) withTx(ctx context.Context, fn func(pgx.Tx) error) error {
       tx, err := s.pool.Begin(ctx)
       if err != nil { return err }
       defer tx.Rollback(ctx) // no-op nếu đã commit
       if err := fn(tx); err != nil { return err }
       return tx.Commit(ctx)
   }
   ```
   Không truyền `*sql.Tx` xuyên qua nhiều tầng service — transaction là chi tiết của tầng storage.

5. **Connection pool cấu hình tường minh:**
   ```go
   db.SetMaxOpenConns(25)
   db.SetMaxIdleConns(25)
   db.SetConnMaxLifetime(5 * time.Minute)
   ```
   (pgxpool: `MaxConns`, `MaxConnLifetime`). Mặc định unlimited → cạn kết nối DB khi tải cao.

6. **Dịch lỗi driver → lỗi domain ngay tại repository:**
   ```go
   if errors.Is(err, pgx.ErrNoRows) { return nil, user.ErrNotFound }
   var pgErr *pgconn.PgError
   if errors.As(err, &pgErr) && pgErr.Code == "23505" { return nil, user.ErrDuplicate }
   ```
   Tầng service không được import driver.

7. **NULL:** dùng pointer (`*string`) hoặc `sql.Null*`; với sqlc cấu hình `emit_pointers_for_null_types`. Không lưu chuỗi rỗng giả làm NULL.

## Migration

- Dùng `golang-migrate` hoặc `goose`, file SQL đánh số trong `migrations/`, có cả `up` và `down`.
- Migration chạy như bước deploy riêng (hoặc khi khởi động với lock), không auto-migrate bằng GORM ở production.
- Không bao giờ sửa migration đã chạy — luôn thêm file mới.

## Anti-pattern cần bắt

- N+1: query trong vòng lặp → đổi sang JOIN hoặc `WHERE id = ANY($1)`
- `SELECT *` trong code (schema đổi là struct scan vỡ ngầm)
- Mở transaction rồi gọi API/network bên ngoài trong lúc giữ transaction
- Bỏ qua lỗi `Scan`
- Test repository bằng mock SQL string — dùng testcontainers với DB thật (xem skill go-testing)
