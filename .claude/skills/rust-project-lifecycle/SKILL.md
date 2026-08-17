---
name: rust-project-lifecycle
description: End-to-end guidance for Rust projects across their entire lifecycle - project scaffolding, workspace layout, dependency management, idiomatic code and error handling, testing (unit/integration/property/nextest), CI/CD with GitHub Actions, benchmarking and profiling, releasing to crates.io, cross-compilation, Docker packaging, and long-term maintenance (MSRV, security audits, upgrades). Use this skill whenever the user is creating a new Rust project or crate, adding dependencies, structuring a Cargo workspace, writing or reviewing Rust code, setting up tests or CI for Rust, optimizing Rust performance, publishing/releasing a crate or binary, or maintaining an existing Rust codebase - even if they only mention "cargo", a Cargo.toml file, or .rs files without saying "Rust" explicitly.
---

# Rust Project Lifecycle

A complete playbook for taking a Rust project from `cargo new` to long-term maintenance. This SKILL.md is a router: identify which lifecycle phase the task belongs to, then read the matching reference file before acting. Multiple phases often apply to one request (e.g., "set up a new CLI project with CI" = setup + testing + ci-cd).

## Phase router

| Phase | When the task involves... | Read |
|---|---|---|
| 1. Setup & scaffolding | `cargo new`/`cargo init`, workspace layout, bin vs lib, project structure, toolchain pinning, editions | `references/01-setup.md` |
| 2. Dependencies | Adding/choosing crates, feature flags, workspace dependencies, `cargo-deny`, supply-chain security, build times | `references/02-dependencies.md` |
| 3. Code quality | Writing/reviewing Rust code, error handling, API design, clippy/rustfmt, unsafe code, common idioms | `references/03-code-quality.md` |
| 4. Testing | Unit/integration/doc tests, `cargo-nextest`, property testing, mocking, snapshot tests, coverage | `references/04-testing.md` |
| 5. CI/CD | GitHub Actions pipelines, caching, matrix builds, MSRV checks, automated releases | `references/05-ci-cd.md` |
| 6. Performance | Benchmarks (criterion/divan), profiling (flamegraph, perf), release profiles, allocation, async performance | `references/06-performance.md` |
| 7. Release & distribution | Versioning/semver, publishing to crates.io, changelogs, cross-compilation, Docker images, cargo-dist | `references/07-release.md` |
| 8. Maintenance | Dependency upgrades, security audits, MSRV policy, deprecations, edition migration, refactoring legacy code | `references/08-maintenance.md` |

## Core principles (apply in every phase)

1. **Let the toolchain do the enforcement.** Prefer configuration over convention: `rustfmt.toml`, `clippy` lints in `Cargo.toml` `[lints]`, `deny.toml`, CI gates. A rule not enforced by a tool will decay.
2. **Verify before claiming.** After writing or editing Rust code, run `cargo check` (fast) and, if warranted, `cargo clippy --all-targets` and `cargo test`. Never present code as working without at least a successful `cargo check` when a toolchain is available. If no toolchain is available, say so explicitly.
3. **Workspace-first for anything non-trivial.** If a project might grow beyond one crate (a CLI plus a lib, a server plus shared types), start with a Cargo workspace and virtual manifest. Splitting later is more painful than starting split.
4. **Errors are API.** Libraries expose typed errors (`thiserror`); binaries/application layers may use `anyhow`/`eyre`. Never `unwrap()`/`expect()` on fallible paths in library code or request-handling paths; `expect("reason")` is acceptable for true invariants and in tests.
5. **Pin what CI runs, float what users get.** Commit `Cargo.lock` for binaries and workspaces (current guidance: commit it for libraries too); use `rust-toolchain.toml` to pin the toolchain; declare `rust-version` (MSRV) in Cargo.toml and test it in CI.
6. **Edition 2024 by default** for new projects (requires Rust 1.85+). Only use an older edition when constrained by MSRV requirements the user states.

## Standard workflow for common requests

**"Start a new Rust project"** → read 01-setup.md fully, ask (or infer) bin/lib/workspace, generate layout + `rust-toolchain.toml` + `[lints]` config + minimal CI from 05-ci-cd.md. Offer testing scaffold from 04-testing.md.

**"Review my Rust code" / "fix this"** → read 03-code-quality.md. Run `cargo clippy --all-targets -- -W clippy::pedantic` mentally or literally; check error handling, ownership patterns, API surface.

**"My build/tests are slow"** → 02-dependencies.md (feature pruning, duplicate deps) + 06-performance.md (profiles, linker) + 04-testing.md (nextest).

**"Ship it"** → 07-release.md, plus 05-ci-cd.md if release automation is wanted.

**"Upgrade / audit this old project"** → 08-maintenance.md first; it sequences the other phases.

## Quick reference: the standard project baseline

Every project this skill produces should end up with (adapt, don't cargo-cult):

```
project/
├── Cargo.toml            # [lints] configured, rust-version set
├── Cargo.lock            # committed
├── rust-toolchain.toml   # channel pinned (e.g. "1.88")
├── rustfmt.toml          # only if deviating from defaults (prefer defaults)
├── deny.toml             # licenses + advisories + duplicate bans
├── .github/workflows/ci.yml
├── src/
└── tests/                # integration tests
```

And these commands must pass locally and in CI:

```bash
cargo fmt --check
cargo clippy --all-targets --all-features -- -D warnings
cargo test --all-features        # or: cargo nextest run
cargo doc --no-deps              # docs build without warnings
```

## Interaction guidance

- When the user's request spans phases, state which phases you're covering and read those references before generating files.
- Prefer showing complete, runnable files (full Cargo.toml, full ci.yml) over fragments, unless editing an existing file.
- When choices are genuinely contested (tokio vs async-std is not contested — use tokio; but e.g. axum vs actix-web is a real choice), present the default recommendation with a one-line reason and mention the alternative.
- Respect existing project conventions over this skill's defaults when working in an established codebase.
