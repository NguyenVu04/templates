# Data & Persistence (JPA + Flyway)

## Flyway migrations

- Location: `src/main/resources/db/migration`, named `V<version>__<description>.sql` (e.g., `V7__add_order_status_index.sql`). Use timestamps (`V20260708120000__...`) on teams with parallel branches to avoid version collisions.
- Migrations are **immutable once merged** — never edit an applied migration (checksum mismatch will brick deploys); fix forward with a new one.
- Every entity change ships with its migration in the same PR. Reviewer checks SQL, not just Java.
- Production DDL discipline: on large tables use `CREATE INDEX CONCURRENTLY` (Postgres; requires the migration to run outside a transaction — Flyway: put it in its own file and mark non-transactional), add columns as nullable-first then backfill then constrain.
- `spring.jpa.hibernate.ddl-auto: validate` — Hibernate verifies mapping matches the schema Flyway built; drift fails fast at startup.

## Entity conventions

```java
@Entity
@Table(name = "orders")
public class Order {

  @Id
  @GeneratedValue          // sequence/identity per DB; UUIDv7 also fine
  private UUID id;

  @Enumerated(EnumType.STRING)          // never ORDINAL — reordering the enum corrupts data
  @Column(nullable = false, length = 32)
  private OrderStatus status;

  @Column(nullable = false, precision = 19, scale = 4)
  private BigDecimal total;

  @Version
  private long version;                  // optimistic locking

  @CreatedDate  @Column(nullable = false, updatable = false)
  private Instant createdAt;             // enable @EnableJpaAuditing

  @LastModifiedDate
  private Instant updatedAt;

  protected Order() {}                   // JPA only
  // real constructor + behavior methods; setters only where mutation is legal
}
```

Rules and the reasons:

- **All associations LAZY.** `@ManyToOne`/`@OneToOne` are EAGER by default — override with `fetch = FetchType.LAZY`. Eager fetching turns one query into a cascade you can't opt out of.
- **Prefer unidirectional associations**; add the inverse side only when queries need it. Bidirectional requires sync helpers and invites serialization cycles.
- **equals/hashCode on id only, null-safe**, or skip overriding and never put entities in hash sets before persisting. Lombok `@EqualsAndHashCode`/`@Data` on entities is a known footgun (proxies, lazy fields in hashCode) — don't.
- **No cascade REMOVE across aggregates.** Cascades stay inside one aggregate (Order → OrderLine yes; Order → Customer never).
- Soft delete only when the business needs it; implement with `deleted_at` + partial indexes rather than Hibernate `@Where` magic if queries must sometimes see deleted rows.

## Repositories & queries

- Derived names for trivial queries; `@Query` JPQL once a name exceeds ~4 words.
- Fetch what the use case needs:
  - Read-only lists → **DTO projections** (constructor expression in JPQL or interface projections). Skips dirty checking and lazy landmines entirely.
  - Loading a graph for an operation → `join fetch` or `@EntityGraph`.
- **N+1 detection is part of the definition of done** for list endpoints: run the test with `spring.jpa.properties.hibernate.show_sql` locally or assert query counts (e.g., Hypersistence `SQLStatementCountValidator` / datasource-proxy) in an integration test.
- Pagination: `Pageable` everywhere; beware `join fetch` on collections + pagination (Hibernate paginates in memory and warns `HHH000104`) — paginate ids first, then fetch, or use `@BatchSize`/two queries.
- Set `spring.jpa.properties.hibernate.default_batch_fetch_size: 32` as a cheap global N+1 mitigation.

## Transactions

- `@Transactional` on **service methods**, the unit-of-work boundary. `@Transactional(readOnly = true)` on query methods — enables driver/Hibernate optimizations and documents intent.
- Self-invocation does not go through the proxy: a `@Transactional` method called from the same class runs without a transaction. Restructure into another bean instead of injecting self.
- Don't do slow I/O (HTTP calls, file ops) inside a transaction — you're pinning a DB connection. Pattern: transaction to write + publish `ApplicationEvent`; a `@TransactionalEventListener(phase = AFTER_COMMIT)` handles the side effect. If the side effect must not be lost, use the transactional outbox pattern instead.
- Checked exceptions don't roll back by default — prefer unchecked domain exceptions, or set `rollbackFor`.

## Connection pool (Hikari)

Size deliberately: pool size ≈ `(cores × 2)` per instance is a sane start; total across replicas must stay under the DB `max_connections` budget. Set `maximumPoolSize`, `connectionTimeout` (e.g., 3s — fail fast when saturated), and expose Hikari metrics (automatic with Actuator + Micrometer).
