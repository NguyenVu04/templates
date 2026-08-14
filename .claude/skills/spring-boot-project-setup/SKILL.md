---
name: spring-boot-project-setup
description: >-
  Guidance for bootstrapping new Java/Kotlin Spring Boot services and modules:
  build tool and dependency choices, generating a project via start.spring.io,
  initial repo hygiene, application.yml baseline, local dev loop (Docker
  Compose), and multi-module layout. Use this skill whenever the user is
  starting a brand-new Spring Boot project or module, choosing between Maven
  and Gradle, picking a Java or Spring Boot version, scaffolding a new
  service, setting up local dev infrastructure, or deciding whether to split
  into multiple modules — including when the codebase clearly uses Spring
  Boot (pom.xml/build.gradle with spring-boot-starter, @SpringBootApplication,
  application.yml) but has no project yet or is adding a new module.
---

# Spring Boot Project Setup & Bootstrapping

This skill turns Claude into a reliable Spring Boot engineer for the earliest phase of a project: choosing defaults and getting a new service off the ground with correct hygiene from commit one.

## Detect the project's existing state first

Never assume greenfield:
- Build tool: look for `pom.xml` (Maven) vs `build.gradle(.kts)` (Gradle). Match whichever exists; only choose fresh for a genuinely new project.
- Spring Boot version: `spring-boot-starter-parent` version in pom, or plugin version in Gradle.
- Java version: `<java.version>` / `sourceCompatibility` / toolchain block.
- Follow the codebase's existing conventions over this skill when they conflict on style; follow this skill on correctness and safety.

## Decision defaults (override only if the user has reasons)

| Decision | Default | Why |
|---|---|---|
| Build tool | Maven for teams/enterprise; Gradle (Kotlin DSL) if the user prefers faster builds or already uses it | Maven is boringly predictable; Gradle is faster and better for multi-module |
| Java | 21 LTS (25 LTS if infra supports it) | Virtual threads, records, pattern matching; Boot 3.2+ fully supports 21. Always prefer the current LTS Java and the latest patch of the project's Spring Boot minor line — patch releases are low-risk and fix CVEs. |
| Spring Boot | Latest patch of latest GA minor (3.5.x line; 4.x if greenfield and team accepts newer) | Patch releases are low-risk and fix CVEs |
| Packaging | Single module until proven otherwise | Multi-module adds friction; split when a second deployable or shared lib actually exists |
| DB | PostgreSQL | Best default: JSONB, sane locking, Testcontainers support |
| Migrations | Flyway | Simpler than Liquibase; SQL-first is reviewable. Every schema change goes through a migration from the first commit — `ddl-auto` must be `validate` (or `none`) outside local dev; `update` in production silently corrupts schemas. |
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

Baseline dependencies for a typical service: `web`, `validation`, `data-jpa` + driver, `flyway`, `actuator`, `configuration-processor`. Add `security`, `oauth2-resource-server` when auth is in scope. Testing: `spring-boot-starter-test` is included; add `org.testcontainers:junit-jupiter` + DB module, and `spring-boot-testcontainers`. New endpoints and bug fixes should always ship with tests in the same change — bake that expectation into the project from the start (test dependencies present, CI wired) rather than retrofitting it later.

## Initial repo hygiene (do this in the first commit, it never happens later)

- `.gitignore`: `target/`, `build/`, `.idea/`, `*.iml`, `.env`, `application-local.yml`
- `README.md` with: how to run locally, required env vars, how to run tests
- `.editorconfig` + a formatter: Spotless plugin with `palantir-java-format` or `google-java-format`, wired to `check` phase so CI fails on format drift
- Maven wrapper / Gradle wrapper committed (`./mvnw`, `./gradlew`) — CI and new machines must not depend on a globally installed build tool
- Rename `application.properties` → `application.yml` (nesting readability), create `application-local.yml` (gitignored) for developer overrides
- **No secrets in the repo.** Not in `application.yml`, not in Dockerfiles, not in test fixtures. Use env vars / secret managers from day one; document required variables in the README.

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
    open-in-view: false         # OSIV holds a DB connection for the whole HTTP request and hides lazy-loading bugs until they explode later
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

`open-in-view: false` from day one: turning it off on a mature codebase is painful; starting with it off is free.

Fail fast on config from the start: bind config with `@ConfigurationProperties` + validation annotations so a misconfigured pod crashes at startup instead of at 3 a.m. under load, rather than scattering `@Value("${...}")` across classes later.

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
