# Build, Docker & CI/CD

## Docker image

Two good options; pick one and stay consistent:

**Option A — Buildpacks (zero Dockerfile):** `./mvnw spring-boot:build-image -Dspring-boot.build-image.imageName=ghcr.io/acme/orders:${TAG}`. Paketo produces a patched, layered, non-root image. Best when you don't want to own a Dockerfile.

**Option B — Multi-stage Dockerfile with layertools** (more control, standard in most CI):

```dockerfile
# ---- build ----
FROM eclipse-temurin:21-jdk AS build
WORKDIR /app
COPY .mvn/ .mvn/
COPY mvnw pom.xml ./
RUN ./mvnw -q dependency:go-offline          # cached layer: deps change rarely
COPY src ./src
RUN ./mvnw -q -DskipTests package

# ---- extract Boot layers ----
FROM eclipse-temurin:21-jre AS layers
WORKDIR /app
COPY --from=build /app/target/*.jar app.jar
RUN java -Djarmode=tools -jar app.jar extract --layers --destination extracted

# ---- runtime ----
FROM eclipse-temurin:21-jre
RUN useradd -r -u 1001 app
USER 1001
WORKDIR /app
COPY --from=layers /app/extracted/dependencies/ ./
COPY --from=layers /app/extracted/spring-boot-loader/ ./
COPY --from=layers /app/extracted/snapshot-dependencies/ ./
COPY --from=layers /app/extracted/application/ ./
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
```

Why layers: dependencies (~100MB) and your code (~1MB) go in separate image layers, so a code-only change pushes/pulls megabytes, not the world.

Rules: non-root user; JRE not JDK at runtime; pin base image tags; never `latest` in deploys — tag with git SHA + semver.

Faster startup options when it matters: CDS/AOT cache (`spring-boot:process-aot` + training run), or GraalVM native image for scale-to-zero workloads (test thoroughly — reflection-heavy libs need hints).

## CI pipeline (GitHub Actions skeleton — same stages apply to GitLab/Jenkins)

```yaml
name: ci
on:
  pull_request:
  push: { branches: [main] }

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-java@v4
        with: { distribution: temurin, java-version: 21, cache: maven }
      - name: Verify (format, unit, integration, coverage)
        run: ./mvnw -B verify
      - name: Upload JaCoCo report
        uses: actions/upload-artifact@v4
        with: { name: jacoco, path: target/site/jacoco }

  image:
    needs: build
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    permissions: { contents: read, packages: write }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-java@v4
        with: { distribution: temurin, java-version: 21, cache: maven }
      - name: Build & push image
        run: |
          ./mvnw -B -DskipTests spring-boot:build-image \
            -Dspring-boot.build-image.imageName=ghcr.io/${{ github.repository }}:${{ github.sha }} \
            -Dspring-boot.build-image.publish=true \
            -Ddocker.publishRegistry.username=${{ github.actor }} \
            -Ddocker.publishRegistry.password=${{ secrets.GITHUB_TOKEN }}
```

Testcontainers runs fine on hosted runners (Docker available) — no service-container gymnastics needed.

## Quality gates wired into `verify`

- **Format**: Spotless `check` — fails CI on unformatted code; devs run `spotless:apply`.
- **Static analysis**: Error Prone (compile-time) and/or SonarQube; treat new issues as blocking, legacy as baseline.
- **CVE scanning**: OWASP Dependency-Check or Trivy on the built image; GitHub Dependabot/Renovate for automated bump PRs (see `maintenance-upgrades.md`).
- **Enforcer plugin** (Maven): ban dependency convergence conflicts and accidental duplicate classes.

## Versioning & release flow

- Trunk-based with short-lived branches; every merge to main builds a deployable image tagged with SHA.
- Human-facing releases: tag `vX.Y.Z`, generate changelog from Conventional Commits if the team uses them.
- The artifact that passed tests is the artifact you deploy — promote the *image* through environments; never rebuild per environment (rebuilds reintroduce "works in staging" drift).
