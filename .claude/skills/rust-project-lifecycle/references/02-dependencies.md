# Phase 2 — Dependency Management

## Adding dependencies

- Use `cargo add <crate>` (edits Cargo.toml correctly, picks latest compatible version).
- Specify major version only (`serde = "1"`), not exact pins — `Cargo.lock` handles reproducibility. Exact pins (`=1.0.219`) only for known-broken upstream releases, with a comment explaining why.
- **Audit features before adding**: check the crate's `Cargo.toml`/docs.rs for default features and disable what you don't need:

```toml
tokio = { version = "1", default-features = false, features = ["rt-multi-thread", "macros", "net", "signal"] }
reqwest = { version = "0.12", default-features = false, features = ["rustls-tls", "json"] }  # avoids openssl
```

## The blessed defaults (avoid re-litigating these)

| Need | Use | Notes |
|---|---|---|
| Async runtime | tokio | The ecosystem default; don't mix runtimes |
| HTTP server | axum | tower ecosystem; actix-web is the main alternative |
| HTTP client | reqwest | `rustls-tls` feature to avoid native OpenSSL |
| Serialization | serde + serde_json | |
| Errors (lib) | thiserror 2.x | |
| Errors (app) | anyhow | eyre if you want fancier reports |
| CLI | clap (derive feature) | |
| Logging | tracing + tracing-subscriber | not `log` for new async code |
| Time | jiff or chrono | jiff for new projects; time crate also fine |
| SQL | sqlx (async, compile-checked) or diesel | sea-orm if ORM wanted |
| ID generation | uuid (v7 feature) | |
| Random | rand | |
| Lazy statics | `std::sync::LazyLock` | not lazy_static/once_cell on Rust ≥ 1.80 |
| HashMap perf | ahash or rustc-hash | only when profiling shows hashing is hot |

Prefer std over a crate when std suffices: `LazyLock`, `OnceLock`, `std::sync::mpsc` for simple cases, `#[expect]` instead of allow-with-TODO.

## Evaluating an unfamiliar crate

Check, in order: (1) recent releases / maintenance activity, (2) download count and reverse dependencies on crates.io, (3) unsafe usage (`cargo geiger` or docs), (4) dependency tree weight (`cargo tree -p <crate>` — a "small" crate pulling 80 transitive deps is not small), (5) license compatibility. If uncertain about current state, search the web rather than relying on training data.

## Supply chain & policy: cargo-deny

Every project gets a `deny.toml`. Baseline:

```toml
[advisories]
version = 2
yanked = "deny"

[licenses]
version = 2
allow = ["MIT", "Apache-2.0", "Apache-2.0 WITH LLVM-exception", "BSD-2-Clause", "BSD-3-Clause", "ISC", "Unicode-3.0", "Zlib"]

[bans]
multiple-versions = "warn"     # escalate to "deny" once tree is clean
wildcards = "deny"

[sources]
unknown-registry = "deny"
unknown-git = "deny"
```

Run `cargo deny check` in CI. For stricter environments add `cargo audit` (RustSec advisories only, lighter weight) and `cargo vet` / `cargo crev` for review-based trust.

## Keeping the tree healthy

- `cargo tree --duplicates` — find crates compiled at multiple versions (build-time and binary-size cost). Fix by bumping the laggard dependency or adding a direct dep to force unification.
- `cargo machete` or `cargo shear` — detect unused dependencies.
- `cargo outdated` or Renovate/Dependabot for upgrade PRs (see 08-maintenance.md for cadence).

## Build time management

Symptoms → fixes:

- **Cold builds slow**: prune features (biggest lever); check for `openssl-sys`-style native builds and swap to rustls; consider `cargo build --timings` to find the long pole.
- **Incremental builds slow**: split big crates — the crate is Rust's compilation unit, so a workspace of 8 small crates rebuilds far less than one monolith; move slow proc-macro-heavy types (huge serde derives) into leaf crates.
- **Linking slow**: use lld: on stable Linux add to `.cargo/config.toml`:

```toml
[target.x86_64-unknown-linux-gnu]
rustflags = ["-C", "link-arg=-fuse-ld=lld"]
```

(Rust 1.90+ uses lld by default on this target; check current status before adding.)
- **CI builds slow**: `Swatinem/rust-cache` action + `sccache` for larger orgs.

## Feature flag design (for your own crates)

- Features must be **additive** — enabling a feature never removes or changes existing API behavior, because Cargo unifies features across the tree.
- Never use `default-features = false` semantics that break compilation of dependents; test the powerset that matters: `cargo hack check --feature-powerset --depth 2` (from cargo-hack) in CI for published libraries.
- Name features after capability, not dependency: `tls` (which internally enables `dep:rustls`), using the `dep:` syntax to hide optional deps from the public feature list.
