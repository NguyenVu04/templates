# Project Setup & Bootstrapping

## Decision defaults (override only if the user has reasons)

| Decision | Default | Why |
|---|---|---|
| Build tool | Maven for teams/enterprise; Gradle (Kotlin DSL) if the user prefers faster builds or already uses it | Maven is boringly predictable; Gradle is faster and better for multi-module |
| Java | 21 LTS (25 LTS if infra supports it) | Virtual threads, records, pattern matching; Boot 3.2+ fully supports 21 |
| Spring Boot | Latest patch of latest GA minor (3.5.x line; 4.x if greenfield and team accepts newer) | Patch releases are low-risk and fix CVEs |
| Packaging | Single module until proven otherwise | Multi-module adds friction; split when a second deployable or shared lib actually exists |
| DB | PostgreSQL | Best default: JSONB, sane locking, Testcontainers support |
| Migrations | Flyway | Simpler than Liquibase; SQL-first is reviewable |
| Boilerplate reduction | Java records for DTOs; Lombok only if codebase already uses it | Records are standard; Lombok is a dependency on bytecode magic |

## Bootstrapping

Generate via start.spring.io (works headless):

```bash
curl -s https://start.spring.io/starter.zip \
  -d type=maven-project -d language=java -d javaVersion=21 \
  -d bootVersion=<latest> \
  -d groupId=com.example -d artifactId=orders -d name=orders \
  -d packageName=com.example.orders \
  -d dependencies=web,data-jpa,postgresql,flyway,validation,actuator,configuration-processor \
  -o orders.zip && unzip orders.zip -d orders
```

Baseline dependencies for a typical service: `web`, `validation`, `data-jpa` + driver, `flyway`, `actuator`, `configuration-processor`. Add `security`, `oauth2-resource-server` when auth is in scope. Testing: `spring-boot-starter-test` is included; add `org.testcontainers:junit-jupiter` + DB module, and `spring-boot-testcontainers`.

## Initial repo hygiene (do this in the first commit, it never happens later)

- `.gitignore`: `target/`, `build/`, `.idea/`, `*.iml`, `.env`, `application-local.yml`
- `README.md` with: how to run locally, required env vars, how to run tests
- `.editorconfig` + a formatter: Spotless plugin with `palantir-java-format` or `google-java-format`, wired to `check` phase so CI fails on format drift
- Maven wrapper / Gradle wrapper committed (`./mvnw`, `./gradlew`) — CI and new machines must not depend on a globally installed build tool
- Rename `application.properties` → `application.yml` (nesting readability), create `application-local.yml` (gitignored) for developer overrides

## application.yml starting point

```yaml
spring:
  application:
    name: orders
  datasource:
    url: ${DB_URL:jdbc:postgresql://localhost:5432/orders}
    username: ${DB_USER:orders}
    password: ${DB_PASSWORD:orders}
  jpa:
    hibernate:
      ddl-auto: validate        # Flyway owns the schema
    open-in-view: false         # see data-persistence.md — critical
  flyway:
    enabled: true

server:
  shutdown: graceful

management:
  endpoints:
    web:
      exposure:
        include: health,info,metrics,prometheus
```

`open-in-view: false` from day one: OSIV holds a DB connection for the whole HTTP request and hides lazy-loading bugs until they explode later. Turning it off on a mature codebase is painful; starting with it off is free.

## Local dev loop

- `spring-boot-devtools` (optional) for restart-on-change.
- Docker Compose for local infra, and Boot 3.1+ can auto-start it via `spring-boot-docker-compose`:

```yaml
# compose.yaml at repo root
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_DB: orders
      POSTGRES_USER: orders
      POSTGRES_PASSWORD: orders
    ports: ["5432:5432"]
```

## Multi-module layout (only when needed)

```
orders-parent/
├── pom.xml            (packaging=pom, dependencyManagement)
├── orders-app/        (Spring Boot executable, thin)
├── orders-domain/     (entities, services — no web deps)
└── orders-api/        (DTOs shared with clients, optional)
```

Keep the Boot plugin only on the executable module; libraries build plain jars.
