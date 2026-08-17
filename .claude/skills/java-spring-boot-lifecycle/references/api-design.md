# REST API Design

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

Error body is RFC 7807 `ProblemDetail` everywhere (see `architecture-conventions.md`).

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

Notes: no logic beyond mapping; pagination is mandatory on every collection endpoint (unbounded lists are an outage waiting for data growth); cap page size (`spring.data.web.pageable.max-page-size`).

## Validation

- Bean Validation on request records: `@NotBlank`, `@Email`, `@Positive`, `@Size`, nested with `@Valid`.
- Custom rules that need dependencies → validate in the service, throw a domain exception → 422.
- Custom `ConstraintValidator` only for reusable, dependency-free formats (e.g., a national ID format).
- Always constrain string lengths (`@Size(max=...)`) matching DB column limits — otherwise you trade a clean 400 for a 500 from the database.

## Serialization rules

- Configure Jackson once: `spring.jackson.default-property-inclusion: non_null`, dates as ISO-8601 (default in Boot), never timestamps-as-epoch unless the client demands it.
- Enums: serialize by name; be deliberate about `READ_UNKNOWN_ENUM_VALUES_AS_NULL` vs failing.
- IDs as UUID/string in the API even if numeric internally when enumeration is a concern.

## OpenAPI

Add `springdoc-openapi-starter-webmvc-ui`. Annotate only what the code can't express (descriptions, examples); the types and validation annotations already generate accurate schemas. Publish the spec artifact from CI so client teams generate SDKs from it rather than reading controllers.

## Idempotency & concurrency

- For client-retryable POSTs (payments, order submission), support an `Idempotency-Key` header stored with the result; replay returns the original response.
- Expose `@Version`-based optimistic locking as HTTP: return 409 on `ObjectOptimisticLockingFailureException`; optionally support `ETag`/`If-Match` for updates.

## HTTP clients (calling other services)

- Boot 3.2+: prefer `RestClient` (sync) or declarative HTTP interfaces (`@HttpExchange`) over the legacy `RestTemplate`; `WebClient` only when reactive is genuinely needed.
- Always set connect + read timeouts explicitly — the JDK/client defaults are effectively infinite and will exhaust your thread pool during a downstream outage.
- Wrap outbound calls with resilience where failure is expected: Resilience4j `@Retry` (idempotent calls only), `@CircuitBreaker`, `@TimeLimiter`.
