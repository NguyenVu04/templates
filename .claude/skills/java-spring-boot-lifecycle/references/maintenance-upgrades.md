# Maintenance & Upgrades

## Cadence

- **Patch releases (3.5.x → 3.5.y): apply within days.** They are bugfix + CVE only; risk is minimal, and Spring Security CVEs get weaponized quickly.
- **Minor (3.4 → 3.5): within a quarter.** Read the release notes' deprecation list; fix deprecation warnings *before* they become removals.
- **Major (2.x → 3.x, 3.x → 4.x): planned project.** Never stack it with feature work in one PR.
- Track OSS support windows — running an EOL Boot line means no CVE fixes. Check the current support table at spring.io before recommending a target version.
- Automate the boring part: Renovate or Dependabot with grouped PRs; CI green + review = merge. A repo where bumps are automated stays perpetually one small step from current instead of facing a yearly big-bang.

## Safe upgrade procedure (any size)

1. Branch; bump only the Boot version (parent/BOM) — let the BOM move managed dependency versions; remove any version overrides that the BOM now covers (overrides are the #1 source of upgrade breakage).
2. `./mvnw -q dependency:tree` diff if something behaves oddly — look for duplicate/conflicting artifacts.
3. Compile with deprecation warnings on; fix them now.
4. Run full `verify` (integration tests with Testcontainers are your safety net — this is where the test investment pays off).
5. Boot the app locally, hit health + a few endpoints, check startup log for new WARNs (property renames log warnings via `spring-boot-properties-migrator` — add it temporarily, remove after).
6. Deploy to staging behind the normal pipeline; watch dashboards for latency/error deltas.

## Known big-bump landmines

**Boot 2 → 3** (if you meet a legacy codebase):
- Java 17+ required; `javax.*` → `jakarta.*` (use OpenRewrite recipe `org.openrewrite.java.spring.boot3.UpgradeSpringBoot_3_x` — it automates most of this).
- Spring Security: `WebSecurityConfigurerAdapter` removed → `SecurityFilterChain` beans.
- Properties renamed en masse — run the properties migrator.

**Boot 3 → 4 / Framework 7**: Java 17+ baseline retained but check the notes; some 3.x deprecations removed; Jakarta EE baseline raised; test annotations churn (e.g., `@MockBean` → `@MockitoBean` already since 3.4). Read the official migration guide for the exact minor — do not guess from memory; the guide is authoritative and short.

**Hibernate major bumps** (ride along with Boot minors): query semantics and dialect changes can alter SQL — DataJpaTest-against-real-DB coverage catches these.

## Dependency hygiene

- Only manage versions the BOM doesn't; keep them in `<properties>`/version catalog, one place.
- Quarterly: `./mvnw versions:display-dependency-updates` (or Gradle versions plugin) for non-BOM libs.
- Remove unused dependencies when touched (`mvn dependency:analyze` hints); every jar is attack surface and upgrade friction.
- CVE response flow: scanner flags → check if the vulnerable code path is reachable → patch via BOM bump if possible → if no patch exists, pin a fixed transitive version *with a comment and a ticket to remove the pin*.

## Deprecation & refactoring discipline

- Treat compiler/startup deprecation warnings as tech-debt tickets, not noise; zero-warning policy on new code.
- When Boot logs `... is deprecated: use ...` for a property, fix it the same day you see it — batching property renames is how upgrades become archaeology.
- Keep a `docs/adr/` folder of one-page Architecture Decision Records for choices future maintainers will question (why Flyway-at-startup, why no CPU limits, why self-issued JWT). Cheap to write now, gold in year 2.

## Long-lived codebase health checks (run when you inherit or revisit a service)

- `ddl-auto` still `validate`? OSIV still off? Actuator exposure still minimal? (These regress silently.)
- Test suite runtime: if `verify` exceeds ~10 min, invest in container reuse and slice-test conversion before people start skipping tests.
- Startup time creep: `spring-context-indexer` won't help anymore, but lazy init (`spring.main.lazy-initialization=true`) in dev and dependency pruning do.
- Logback/log volume: INFO noise grows monotonically unless pruned; audit top log emitters yearly.
