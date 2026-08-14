---
name: spring-boot-architecture
description: >-
  Guidance for Java/Kotlin Spring Boot package structure, layering, DTOs,
  exception handling, configuration classes, and bean definitions. Use this
  skill whenever the user is designing or reworking package/module structure,
  deciding how controllers/services/repositories/entities should be layered,
  adding a global exception handler, converting DTOs to/from entities,
  binding configuration properties, wiring beans, or doing a general code
  review of a Spring Boot codebase's structure and conventions — including
  when the codebase clearly uses Spring Boot (pom.xml/build.gradle with
  spring-boot-starter, @SpringBootApplication, application.yml) even if the
  user doesn't say "Spring Boot" explicitly.
---

# Spring Boot Architecture & Coding Conventions

This skill turns Claude into a reliable Spring Boot engineer for package structure and coding conventions, so code written in month 1 and month 18 looks like it came from the same team.

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

**Constructor injection only.** Never `@Autowired` on fields, anywhere in any layer. Constructor injection makes dependencies explicit, enables `final` fields, and keeps classes testable without Spring. With a single constructor, `@Autowired` is unnecessary; Lombok `@RequiredArgsConstructor` is acceptable if the project already uses Lombok.

## DTOs and mapping

- **Never expose JPA entities from controllers.** Always map to DTOs (Java `record`s by default). Entities leak lazy-loading exceptions, bidirectional-relation serialization loops, and schema details into the API contract.
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

Enable with `@ConfigurationPropertiesScan` on the application class. Never sprinkle `@Value("${...}")` across many classes — it's unfindable and unvalidated. This is also how you fail fast on config: a misconfigured pod crashes at startup instead of at 3 a.m. under load.

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
- Time and money are never `LocalDateTime`-in-a-vacuum or `double`. Use `Instant`/`OffsetDateTime` with explicit zones for timestamps, `BigDecimal` for money.
- Prefer the current LTS Java (21 as safe default; 25 where the platform supports it).

## Working style expectations

- When adding a feature, deliver the **full vertical slice**: migration → entity → repository → service → DTOs → controller → exception mapping → tests. Don't stop at the controller.
- When reviewing code, check in this order: correctness → security → transaction boundaries → N+1/performance → naming/style. Report findings in that order too.
- Explain *why* a convention applies when it changes user-written code — the user should learn the reasoning, not just accept edits.
