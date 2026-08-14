---
name: spring-boot-data-persistence
description: >-
  Guidance for JPA/Hibernate persistence and Flyway migrations in
  Java/Kotlin Spring Boot services: entity design, associations, Flyway
  migration authoring and safety, repository queries, N+1 detection,
  pagination, transaction boundaries, and Hikari connection pool sizing. Use
  this skill whenever the user is designing or changing entities, writing a
  Flyway/Liquibase migration, adding or modifying a Spring Data repository
  method, fixing N+1 query problems, adding pagination, setting
  @Transactional boundaries, or tuning the datasource/connection pool —
  including when the codebase clearly uses Spring Boot with JPA
  (pom.xml/build.gradle with spring-boot-starter-data-jpa,
  @SpringBootApplication, application.yml) even if the user doesn't say
  "Spring Boot" explicitly.
---

# Spring Boot Data & Persistence (JPA + Flyway)

This skill turns Claude into a reliable Spring Boot engineer for persistence, so schemas and queries written in month 1 and month 18 look like they came from the same team.

## Flyway migrations

- Location: `src/main/resources/db/migration`, named `V<version>__<description>.sql` (e.g., `V7__add_order_status_index.sql`). Use timestamps (`V20260708120000__...`) on teams with parallel branches to avoid version collisions.
- Migrations are **immutable once merged** — never edit an applied migration (checksum mismatch will brick deploys); fix forward with a new one.
- **Every schema change goes through a migration in the same PR as the entity change.** Reviewer checks SQL, not just Java. `ddl-auto` must be `validate` (or `none`) outside local dev — `update` in production silently corrupts schemas.
- Production DDL discipline: on large tables use `CREATE INDEX CONCURRENTLY` (Postgres; requires the migration to run outside a transaction — Flyway: put it in its own file and mark non-transactional), add columns as nullable-first then backfill then constrain.
- `spring.jpa.hibernate.ddl-auto: validate` — Hibernate verifies mapping matches the schema Flyway built; drift fails fast at startup, which is the persistence-layer instance of the general rule that misconfiguration should crash at boot, not corrupt data at 3 a.m.

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
- **Time and money are never `LocalDateTime`-in-a-vacuum or `double`.** Use `Instant`/`OffsetDateTime` with explicit zones for timestamps, `BigDecimal` for money (see `total` above: explicit precision/scale).
- **Never expose entities from controllers.** Entities stay inside the persistence/service layer; map to DTOs (records) at the service or controller boundary. Entities leak lazy-loading exceptions, bidirectional-relation serialization loops, and schema details into the API contract.

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

## Working style expectations

- When adding an entity/migration as part of a feature, it's one link in the **full vertical slice**: migration → entity → repository → service → DTOs → controller → exception mapping → tests. A migration lands with the entity in the same change, and both land with tests.
- A new or changed query ships with a `@DataJpaTest` against the real DB dialect (Testcontainers), not just H2 — H2 lies about Postgres behavior (JSONB, `ILIKE`, sequences, locking).
