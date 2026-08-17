# Phase 8 — Maintenance & Evolution

## Taking over / auditing an existing project

Run this triage sequence and report findings before changing anything:

```bash
cargo --version && rustc --version          # what toolchain does it expect?
cat rust-toolchain.toml Cargo.toml | head   # pinned? edition? MSRV declared?
cargo check 2>&1 | tail                     # does it even build?
cargo tree --duplicates                     # version fragmentation
cargo audit                                 # known vulnerabilities (install: cargo install cargo-audit)
cargo outdated --root-deps-only             # how stale?
cargo clippy --all-targets 2>&1 | grep -c warning
cargo test 2>&1 | tail                      # does the suite pass? does one exist?
```

Prioritize: (1) security advisories, (2) build health, (3) missing CI/tests, (4) staleness. Don't mix an upgrade PR with a refactor PR.

## Dependency upgrade cadence

- **Continuous**: Dependabot/Renovate for patch/minor bumps, auto-merged when CI is trustworthy. `cargo update` freely — it respects semver ranges.
- **Deliberate**: major-version bumps get their own PR, read the crate's CHANGELOG/migration guide first. `cargo update --breaking` (1.85+) or edit versions and fix.
- **Security**: `cargo audit` in CI (scheduled daily, not just per-PR — new advisories appear against unchanged code). On an advisory: `cargo audit fix` where possible, else bump/patch/vendored fix, else evaluate exposure honestly.

## MSRV policy

- Declare `rust-version` in Cargo.toml; verify in CI (dedicated job on that toolchain).
- Pick a policy and write it in the README: "latest stable" (apps), "N-2 releases" or "6 months" (typical libraries), longer only with contractual reasons.
- Raising MSRV: minor version bump by prevailing convention, but note it in the changelog prominently. Check what your dependency bumps drag in — a patch update of a dep can silently raise effective MSRV; `cargo hack check --rust-version` catches this.

## Edition migration (e.g., 2021 → 2024)

```bash
cargo fix --edition            # applies mechanical changes
# edit Cargo.toml: edition = "2024"
cargo fix --edition-idioms     # optional idiom cleanup
cargo test                     # editions are per-crate; deps are unaffected
```

Editions are opt-in and interoperable — migrate one workspace crate at a time if needed. Read the edition guide for semantic changes (2024: RPIT lifetime capture rules, `unsafe_op_in_unsafe_fn`, new prelude items).

## Deprecation workflow (libraries)

1. Mark: `#[deprecated(since = "0.4.0", note = "use `Foo::builder()` instead")]`
2. Ship a release where old and new coexist; document migration in the changelog.
3. Remove in the next breaking release. Never remove without a deprecation release in between (unless 0.x and you accept the churn).

## Refactoring legacy Rust safely

- Establish a characterization-test net first: snapshot tests (insta) on current outputs, even ugly ones, before touching logic.
- Lean on the compiler: change a type/signature, follow the errors — Rust refactors are unusually mechanical. Do them in small compiling steps, not big-bang.
- `cargo clippy --fix` for mechanical lint debt; review the diff, it's not infallible.
- Untangling module spaghetti: enforce direction with workspace crate boundaries (a crate can't cyclically depend), extracting the most stable concepts into a core crate first.
- Kill dead code honestly: `#[expect(dead_code)]` is a TODO with an expiry, not a lifestyle.

## Long-term health signals to monitor

- Time of `cargo check` after `touch src/lib.rs` (incremental latency creep → split crates).
- Warning count trend (should be pinned at zero by CI).
- `cargo tree | wc -l` growth (dependency sprawl).
- Test suite wall time (nextest partitioning or `#[ignore]`-tiering before it exceeds ~5 min).
- Unowned `unsafe` blocks (grep count; each must have a SAFETY comment).

## Sunsetting

Archive gracefully: final release with a README notice and `#[deprecated]` crate-level doc note, point to successors, mark the repo archived. Yank only genuinely broken/vulnerable versions, never as a deprecation mechanism.
