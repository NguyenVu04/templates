---
name: spring-boot-testing
description: >-
  Guidance for testing Java/Kotlin Spring Boot services: the test pyramid
  (plain JUnit 5/Mockito unit tests, @WebMvcTest/@DataJpaTest slice tests,
  @SpringBootTest + Testcontainers integration tests), test data builders,
  coverage expectations per change type, and CI test-stage configuration.
  Use this skill whenever the user is writing or fixing a test, adding
  Testcontainers, deciding what kind of test a change needs, debugging a
  flaky test, configuring JaCoCo coverage gates, or asking how to test a
  controller/repository/service — including when the codebase clearly uses
  Spring Boot (pom.xml/build.gradle with spring-boot-starter-test,
  @SpringBootApplication, application.yml) even if the user doesn't say
  "Spring Boot" explicitly.
---

# Spring Boot Testing Strategy

This skill turns Claude into a reliable Spring Boot engineer for testing, so tests written in month 1 and month 18 look like they came from the same team.

## The pyramid, Spring Boot edition

1. **Plain unit tests** (most): services/domain logic with JUnit 5 + Mockito (or hand-built fakes). No Spring context — these run in milliseconds. If a service is hard to test without Spring, that's a design smell (hidden static calls, field injection — use constructor injection so classes are testable without Spring).
2. **Slice tests** (some): `@WebMvcTest` for controller ↔ JSON ↔ validation ↔ exception mapping; `@DataJpaTest` for repository queries.
3. **Integration tests** (few but real): `@SpringBootTest` + Testcontainers Postgres, exercising the full slice through HTTP.

Name tests by behavior: `create_rejectsNegativeQuantity`, not `testCreate2`. Structure: given/when/then. Assertions with AssertJ (`assertThat`), which ships in `spring-boot-starter-test`.

## Unit test example

```java
@ExtendWith(MockitoExtension.class)
class OrderServiceTest {

  @Mock OrderRepository orderRepository;
  Clock clock = Clock.fixed(Instant.parse("2026-01-01T00:00:00Z"), ZoneOffset.UTC);

  OrderService service;

  @BeforeEach
  void setUp() { service = new OrderService(orderRepository, clock); }

  @Test
  void cancel_rejectsShippedOrder() {
    var order = anOrder().withStatus(SHIPPED).build();     // test data builders > 20-line setup
    when(orderRepository.findById(order.getId())).thenReturn(Optional.of(order));

    assertThatThrownBy(() -> service.cancel(order.getId()))
        .isInstanceOf(IllegalOrderStateException.class);
  }
}
```

Inject `Clock` (never `Instant.now()` inline) so time is controllable. Build test data with builders/object mothers shared under `src/test/java/.../support`.

## Slice tests

```java
@WebMvcTest(OrderController.class)
@Import(GlobalExceptionHandler.class)
class OrderControllerTest {

  @Autowired MockMvc mvc;
  @MockitoBean OrderService orderService;   // @MockBean pre-Boot-3.4

  @Test
  void create_returns400OnBlankCustomer() throws Exception {
    mvc.perform(post("/api/v1/orders")
            .contentType(MediaType.APPLICATION_JSON)
            .content("""
                {"customerId": "", "lines": []}
                """))
        .andExpect(status().isBadRequest())
        .andExpect(jsonPath("$.errors[0].field").value("customerId"));
  }
}
```

`@WebMvcTest` is where validation messages, status codes, and ProblemDetail bodies get verified — the things unit tests can't see. With security on, add `@WithMockUser` / `jwt()` post-processors or the test hits 401s.

`@DataJpaTest` for any non-trivial `@Query`: by default it swaps in an embedded DB — override with Testcontainers (below) because H2's SQL dialect lies about Postgres behavior (JSONB, `ILIKE`, sequences, locking).

## Integration tests with Testcontainers

```java
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class OrderIntegrationTest {

  @ServiceConnection
  static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:16");

  static { postgres.start(); }              // static singleton → one container for the whole suite

  @Autowired TestRestTemplate rest;

  @Test
  void fullOrderLifecycle() { /* POST → GET → cancel → assert 409 on double cancel */ }
}
```

- `@ServiceConnection` (Boot 3.1+) replaces manual `@DynamicPropertySource` datasource wiring.
- Reuse one container across the suite (static, or a shared abstract base class) — per-test containers make the suite unbearably slow.
- Flyway runs the real migrations here, which doubles as migration testing — every schema change is exercised by the same integration tests.
- Reset state between tests with `@Sql` cleanup scripts or transaction rollback — order-dependent tests are the #1 cause of flaky suites.

## What must be covered per change type

| Change | Minimum tests |
|---|---|
| New endpoint | WebMvcTest happy path + each validation/error branch; one integration test |
| New/changed query | DataJpaTest against real DB dialect |
| Bug fix | Regression test that fails on the old code |
| Security rule change | Negative tests (401/403 paths) |
| Migration on existing table | Suite passes on migrated schema (Testcontainers gives this for free) |

**Tests accompany the code in the same change**, always: a new endpoint ships with at least one web-slice or integration test; a bug fix ships with a regression test that fails before the fix. This is non-negotiable regardless of how small the change looks.

## CI expectations

- Split fast tests from integration tests (Maven Surefire vs Failsafe, `*IT` suffix) so devs can run `./mvnw test` in seconds and CI runs `verify`.
- Coverage with JaCoCo; gate on new-code coverage (e.g., 80% on changed lines) rather than a global number that invites gaming.
- A flaky test is a bug: quarantine and fix, never `@Disabled`-and-forget without a ticket.

## Working style expectations

- When adding a feature, deliver the full vertical slice ending in tests: migration → entity → repository → service → DTOs → controller → exception mapping → tests. Don't stop at the controller and skip tests.
- Explain *why* a test is missing or wrong when proposing a fix — the user should learn the reasoning, not just accept edits.
