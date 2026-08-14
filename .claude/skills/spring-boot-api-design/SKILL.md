---
name: spring-boot-api-design
description: >-
  Guidance for designing REST APIs in Java/Kotlin Spring Boot services: URL
  and verb conventions, HTTP status codes, controller shape, request
  validation, JSON serialization, OpenAPI documentation, idempotency,
  optimistic concurrency, and outbound HTTP clients. Use this skill whenever
  the user is adding or changing a REST endpoint, designing request/response
  shapes, choosing status codes or error formats, versioning an API, wiring
  OpenAPI/springdoc, handling idempotency keys or ETags, or calling another
  service over HTTP (RestClient/WebClient/@HttpExchange) — including when the
  codebase clearly uses Spring Boot (pom.xml/build.gradle with
  spring-boot-starter, @SpringBootApplication, application.yml) even if the
  user doesn't say "Spring Boot" explicitly.
---

# Spring Boot REST API Design

This skill turns Claude into a reliable Spring Boot engineer for REST API design, so endpoints written in month 1 and month 18 look like they came from the same team.

## URL & verb conventions

- Nouns, plural, kebab-case: `/api/v1/purchase-orders/{id}/line-items`
- Verbs map to semantics: GET (safe, cacheable), POST (create / non-idempotent action), PUT (full replace, idempotent), PATCH (partial update), DELETE (idempotent).
- Actions that don't fit CRUD: sub-resource POST — `POST /orders/{id}/cancellation` (or pragmatically `POST /orders/{id}/cancel`; pick one style per project).
- Version in the path (`/api/v1/...`) from day one. Adding versioning later breaks every client.

## Status codes

| Case | Code |
|---|---|
| Create | 201 + `Location` header |
| Successful DELETE / action with no body | 204 |
| Validation failure | 400 |
| Not authenticated | 401 |
| Authenticated but forbidden | 403 |
| Missing resource | 404 |
| State conflict (duplicate, optimistic lock) | 409 |
| Business rule rejection that isn't a conflict | 422 |
| Unhandled | 500 (never leak internals) |

Error body is RFC 7807 `ProblemDetail` everywhere, produced by a single `@RestControllerAdvice` global exception handler — business code throws domain exceptions, controllers never catch-and-map errors themselves.

## Controller shape

```java
@RestController
@RequestMapping("/api/v1/orders")
class OrderController {

  private final OrderService orderService;

  OrderController(OrderService orderService) { this.orderService = orderService; }

  @PostMapping
  ResponseEntity<OrderResponse> create(@Valid @RequestBody CreateOrderRequest request) {
    var order = orderService.create(request.toCommand());
    return ResponseEntity
        .created(URI.create("/api/v1/orders/" + order.id()))
        .body(OrderResponse.from(order));
  }

  @GetMapping("/{id}")
  OrderResponse get(@PathVariable UUID id) {
    return OrderResponse.from(orderService.get(id)); // service throws NotFound
  }

  @GetMapping
  Page<OrderResponse> list(
      @RequestParam(required = false) OrderStatus status,
      @PageableDefault(size = 20, sort = "createdAt", direction = Sort.Direction.DESC) Pageable pageable) {
    return orderService.list(status, pageable).map(OrderResponse::from);
  }
}
```

Notes: no logic beyond mapping; pagination is mandatory on every collection endpoint (unbounded lists are an outage waiting for data growth); cap page size (`spring.data.web.pageable.max-page-size`). Constructor injection only — never `@Autowired` on fields. Controllers accept and return DTOs (records), never JPA entities directly: entities leak lazy-loading exceptions, bidirectional-relation serialization loops, and schema details into the API contract.

## Validation

- Bean Validation on request records: `@NotBlank`, `@Email`, `@Positive`, `@Size`, nested with `@Valid`.
- Custom rules that need dependencies → validate in the service, throw a domain exception → 422.
- Custom `ConstraintValidator` only for reusable, dependency-free formats (e.g., a national ID format).
- Always constrain string lengths (`@Size(max=...)`) matching DB column limits — otherwise you trade a clean 400 for a 500 from the database.

## Serialization rules

- Configure Jackson once: `spring.jackson.default-property-inclusion: non_null`, dates as ISO-8601 (default in Boot), never timestamps-as-epoch unless the client demands it.
- Enums: serialize by name; be deliberate about `READ_UNKNOWN_ENUM_VALUES_AS_NULL` vs failing.
- IDs as UUID/string in the API even if numeric internally when enumeration is a concern.
- Time and money in the API contract follow the same discipline as internally: `Instant`/`OffsetDateTime` with explicit zones for timestamps, `BigDecimal` for money — never epoch-as-double or floating point money.

## OpenAPI

Add `springdoc-openapi-starter-webmvc-ui`. Annotate only what the code can't express (descriptions, examples); the types and validation annotations already generate accurate schemas. Publish the spec artifact from CI so client teams generate SDKs from it rather than reading controllers.

## Idempotency & concurrency

- For client-retryable POSTs (payments, order submission), support an `Idempotency-Key` header stored with the result; replay returns the original response.
- Expose `@Version`-based optimistic locking as HTTP: return 409 on `ObjectOptimisticLockingFailureException`; optionally support `ETag`/`If-Match` for updates.

## HTTP clients (calling other services)

- Boot 3.2+: prefer `RestClient` (sync) or declarative HTTP interfaces (`@HttpExchange`) over the legacy `RestTemplate`; `WebClient` only when reactive is genuinely needed.
- Always set connect + read timeouts explicitly — the JDK/client defaults are effectively infinite and will exhaust your thread pool during a downstream outage.
- Wrap outbound calls with resilience where failure is expected: Resilience4j `@Retry` (idempotent calls only), `@CircuitBreaker`, `@TimeLimiter`.

## Working style expectations

- When adding an endpoint, deliver the **full vertical slice**: migration → entity → repository → service → DTOs → controller → exception mapping → tests. Don't stop at the controller.
- A new endpoint ships with at least one web-slice (`@WebMvcTest`) or integration test in the same change; a bug fix ships with a regression test that fails before the fix.
- Explain *why* a convention applies when it changes user-written code — the user should learn the reasoning, not just accept edits.
