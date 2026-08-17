---
name: java-spring-boot-lifecycle
description: >-
  End-to-end guidance for Java + Spring Boot projects across the entire
  lifecycle: bootstrapping a new service, package architecture and coding
  conventions, REST API design and validation, JPA/persistence and Flyway
  migrations, Spring Security (JWT/OAuth2), testing strategy (JUnit 5,
  Mockito, Testcontainers), observability (Actuator/Micrometer/structured
  logging), Docker images, CI/CD pipelines, production configuration and
  Kubernetes deployment, and dependency/Spring Boot version upgrades. Use
  this skill whenever the user works on a Java or Kotlin Spring Boot codebase
  in any way — creating a project, adding a feature or endpoint, writing or
  fixing tests, designing entities or migrations, configuring security,
  reviewing code, debugging Spring errors, containerizing, deploying, or
  upgrading — even if they don't say "Spring Boot" but the code clearly uses
  it (pom.xml/build.gradle with spring-boot-starter, @SpringBootApplication,
  application.yml).
---

# Java + Spring Boot Project Lifecycle

This skill turns Claude into a reliable Spring Boot engineer across the whole life of a project. It encodes conventions so that code written in month 1 and month 18 looks like it came from the same team.

## How to use this skill

1. **Identify the phase** the user is in (table below).
2. **Read the matching reference file(s)** before writing code. Most tasks touch 1–2 files; a new feature slice typically needs `architecture-conventions.md` + `api-design.md` + `data-persistence.md` + `testing.md`.
3. **Detect the project's existing state first** — never assume greenfield:
   - Build tool: look for `pom.xml` (Maven) vs `build.gradle(.kts)` (Gradle). Match whichever exists.
   - Spring Boot version: `spring-boot-starter-parent` version in pom, or plugin version in Gradle. Conventions differ between 2.x, 3.x, and 4.x (see `maintenance-upgrades.md`).
   - Java version: `<java.version>` / `sourceCompatibility` / toolchain block.
   - Package layout, naming, existing test style — follow the codebase over this skill when they conflict on style; follow this skill on correctness and safety (transactions, security, migrations).

## Phase router

| Phase / task | Read |
|---|---|
| New project, module setup, dependency choices | `references/project-setup.md` |
| Package structure, layering, DTOs, exceptions, config classes | `references/architecture-conventions.md` |
| REST endpoints, validation, error responses, OpenAPI, versioning | `references/api-design.md` |
| Entities, repositories, transactions, Flyway/Liquibase, N+1, pagination | `references/data-persistence.md` |
| Auth, JWT, OAuth2/OIDC, method security, CORS, secrets | `references/security.md` |
| Unit / slice / integration tests, Testcontainers, coverage | `references/testing.md` |
| Logging, metrics, tracing, health checks, Actuator | `references/observability.md` |
| Dockerfile, image build, CI pipeline, quality gates | `references/build-ci-cd.md` |
| Profiles, externalized config, K8s manifests, graceful shutdown, JVM tuning | `references/production-operations.md` |
| Upgrading Spring Boot / Java / dependencies, deprecations, CVE response | `references/maintenance-upgrades.md` |

## Non-negotiable defaults (all phases)

These apply regardless of which reference file is loaded. They exist because each one prevents a class of production incidents or unmaintainable code:

- **Constructor injection only.** Never `@Autowired` on fields. Constructor injection makes dependencies explicit, enables `final` fields, and keeps classes testable without Spring. With a single constructor, `@Autowired` is unnecessary; Lombok `@RequiredArgsConstructor` is acceptable if the project already uses Lombok.
- **Never expose JPA entities from controllers.** Always map to DTOs (Java `record`s by default). Entities leak lazy-loading exceptions, bidirectional-relation serialization loops, and schema details into the API contract.
- **Every schema change goes through a migration** (Flyway by default). `ddl-auto` must be `validate` (or `none`) outside local dev. `update` in production silently corrupts schemas.
- **Fail fast on config.** Bind config with `@ConfigurationProperties` + validation annotations so a misconfigured pod crashes at startup instead of at 3 a.m. under load.
- **No secrets in the repo.** Not in `application.yml`, not in Dockerfiles, not in test fixtures. Use env vars / secret managers; document required variables in the README.
- **Tests accompany the code in the same change.** A new endpoint ships with at least one web-slice or integration test; a bug fix ships with a regression test that fails before the fix.
- **Time and money are never `LocalDateTime`-in-a-vacuum or `double`.** Use `Instant`/`OffsetDateTime` with explicit zones for timestamps, `BigDecimal` for money.
- **Prefer the current LTS Java** (21 as safe default; 25 where the platform supports it) and the latest patch of the project's Spring Boot minor line.

## Working style expectations

- When adding a feature, deliver the **full vertical slice**: migration → entity → repository → service → DTOs → controller → exception mapping → tests. Don't stop at the controller.
- When debugging, ask for (or find) the full stack trace and the active profile before proposing fixes. Most "Spring is broken" reports are bean-wiring, profile, or classpath issues visible in the first 20 lines of the log.
- When reviewing code, check in this order: correctness → security → transaction boundaries → N+1/performance → naming/style. Report findings in that order too.
- Explain *why* a convention applies when it changes user-written code — the user should learn the reasoning, not just accept edits.
