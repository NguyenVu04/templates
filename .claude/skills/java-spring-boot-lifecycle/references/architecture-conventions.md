# Architecture & Coding Conventions

## Package structure: package-by-feature

Default to feature packages, not layer packages. Layer packages (`controller/`, `service/`, `repository/` at the top) scatter every feature across the tree and make deletion/refactoring risky. Feature packages keep a vertical slice together and let you use package-private visibility as an architecture guard:

```
com.example.orders
├── OrdersApplication.java
├── common/                  # cross-cutting: errors, config, security
│   ├── error/
│   └── config/
├── order/
│   ├── OrderController.java
│   ├── OrderService.java
│   ├── OrderRepository.java       # package-private if only used here
│   ├── Order.java                 # entity
│   ├── OrderDtos.java             # or separate record files
│   └── OrderMapper.java
└── customer/
    └── ...
```

Cross-feature calls go through the other feature's *service* (or a dedicated facade), never its repository. If the project grows, this structure upgrades cleanly to Spring Modulith or a modular monolith.

## Layer responsibilities

- **Controller**: HTTP concerns only — parse/validate input, call one service method, map to response DTO + status. No business logic, no repository access, no try/catch for business errors (the global handler does that).
- **Service**: business logic, transaction boundaries (`@Transactional` here, not on controllers or repositories). Accepts and returns domain objects or command/result records — controllers do the web-DTO mapping.
- **Repository**: Spring Data interfaces. Derived queries for simple cases, `@Query` JPQL for anything with joins; native SQL only with a comment explaining why.
- **Entity**: persistence model. Never serialized to JSON, never accepts client input directly.

## DTOs and mapping

- DTOs are Java `record`s: `public record OrderResponse(UUID id, String status, BigDecimal total) {}`
- Separate request and response types even when fields overlap today (`CreateOrderRequest` vs `OrderResponse`) — they evolve differently.
- Mapping: hand-written static methods or a small `Mapper` class for ≤ ~8 fields; MapStruct when mappings are numerous/nested. Avoid ModelMapper (reflection-based, silent mismatches).

## Exception handling: one global handler

Business code throws domain exceptions; a single `@RestControllerAdvice` translates them to RFC 7807 `ProblemDetail` (built into Boot 3):

```java
// domain exception
public class OrderNotFoundException extends RuntimeException {
  public OrderNotFoundException(UUID id) { super("Order %s not found".formatted(id)); }
}

@RestControllerAdvice
class GlobalExceptionHandler {

  @ExceptionHandler(OrderNotFoundException.class)
  ProblemDetail handleNotFound(OrderNotFoundException ex) {
    return ProblemDetail.forStatusAndDetail(HttpStatus.NOT_FOUND, ex.getMessage());
  }

  @ExceptionHandler(MethodArgumentNotValidException.class)
  ProblemDetail handleValidation(MethodArgumentNotValidException ex) {
    var pd = ProblemDetail.forStatusAndDetail(HttpStatus.BAD_REQUEST, "Validation failed");
    pd.setProperty("errors", ex.getBindingResult().getFieldErrors().stream()
        .map(f -> Map.of("field", f.getField(), "message", f.getDefaultMessage()))
        .toList());
    return pd;
  }
}
```

Rules: never return stack traces to clients; never catch-and-log-and-swallow in services (let it propagate); log 5xx causes at ERROR with context, 4xx at most at WARN/DEBUG.

## Configuration classes

Bind related settings into typed, validated records:

```java
@ConfigurationProperties(prefix = "app.payment")
@Validated
public record PaymentProperties(
    @NotBlank String apiBaseUrl,
    @NotNull Duration timeout,
    @Min(0) int maxRetries) {}
```

Enable with `@ConfigurationPropertiesScan` on the application class. Never sprinkle `@Value("${...}")` across many classes — it's unfindable and unvalidated.

## Bean definitions

- Stereotype annotations (`@Service`, `@Component`) for your own classes; `@Bean` methods in `@Configuration` classes for third-party types (clients, `ObjectMapper` customizations, `Clock`).
- Register a `Clock` bean (`Clock.systemUTC()`) and inject it wherever code reads "now" — this makes time testable.
- Avoid `@Conditional` gymnastics in app code; profiles + properties cover almost every case.

## General Java conventions

- `final` fields, immutability by default; return `List.of(...)`/unmodifiable collections.
- `Optional` for return types that may be empty; never for fields or parameters.
- No business logic in static utility classes if it needs collaborators — make it a bean.
- Nullability: validate at the boundary (Bean Validation on DTOs), so internals can assume non-null.
- Keep methods small enough that `@Transactional` boundaries and error paths are obvious at a glance.
