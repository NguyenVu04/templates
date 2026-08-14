---
name: rust-setup
description: Guidance for scaffolding new Rust projects and crates - choosing bin vs lib vs workspace layout, virtual workspace structure, toolchain pinning, module conventions, config/secrets patterns, and the standard project baseline (files every project should have, required CI commands). Use this skill whenever the user is starting a new Rust project or crate, running (or planning to run) `cargo new`/`cargo init`, structuring a Cargo workspace, deciding project layout, or pinning a Rust toolchain - even if they only mention "cargo", a Cargo.toml file, or .rs files without saying "Rust" explicitly.
---

# Rust Setup & Scaffolding

Use this skill when the request is "start a new Rust project": infer or ask bin/lib/workspace, generate the layout, `rust-toolchain.toml`, `[lints]` configuration, and point toward CI and testing scaffolding as follow-ups.

## Core principles that apply here

- **Let the toolchain do the enforcement.** Prefer configuration over convention: `rustfmt.toml`, `clippy` lints in `Cargo.toml` `[lints]`, `deny.toml`, CI gates. A rule not enforced by a tool will decay.
- **Workspace-first for anything non-trivial.** If a project might grow beyond one crate (a CLI plus a lib, a server plus shared types), start with a Cargo workspace and virtual manifest. Splitting later is more painful than starting split.
- **Pin what CI runs, float what users get.** Commit `Cargo.lock` for binaries and workspaces (current guidance: commit it for libraries too); use `rust-toolchain.toml` to pin the toolchain; declare `rust-version` (MSRV) in Cargo.toml and test it in CI.
- **Edition 2024 by default** for new projects (requires Rust 1.85+). Only use an older edition when constrained by MSRV requirements the user states.
- **Verify before claiming.** After scaffolding, run `cargo check` (and `cargo clippy --all-targets` / `cargo test` if warranted). Never present a generated project as working without at least a successful `cargo check` when a toolchain is available. If no toolchain is available, say so explicitly.

## Decision: bin, lib, or workspace

- **Pure library** → `cargo new --lib name`. Add a `src/main.rs` later only for internal tooling, never as the primary interface.
- **CLI or service** → still split: a thin `src/main.rs` that parses args/config and calls into `src/lib.rs`. This makes the logic testable via integration tests without spawning processes.
- **Anything with 2+ deliverables** (server + CLI, core + plugins, app + shared proto types) → virtual workspace from day one.

## Virtual workspace layout (default for non-trivial projects)

```
myproject/
├── Cargo.toml          # virtual manifest, no [package]
├── Cargo.lock
├── rust-toolchain.toml
├── crates/
│   ├── myproject-core/     # domain logic, no I/O deps if possible
│   ├── myproject-server/   # axum/tonic binary
│   └── myproject-cli/      # clap binary
└── xtask/                  # optional: repo automation as a Rust crate
```

Root `Cargo.toml`:

```toml
[workspace]
resolver = "3"                # edition-2024 resolver; use "2" if MSRV < 1.84
members = ["crates/*", "xtask"]

[workspace.package]
edition = "2024"
rust-version = "1.85"
license = "MIT OR Apache-2.0"
repository = "https://github.com/user/myproject"

[workspace.dependencies]
# single source of truth for versions; member crates use `dep = { workspace = true }`
serde = { version = "1", features = ["derive"] }
tokio = { version = "1", features = ["full"] }
thiserror = "2"
anyhow = "1"

[workspace.lints.rust]
unsafe_code = "warn"          # "forbid" if the project truly needs no unsafe
missing_docs = "warn"         # for libraries

[workspace.lints.clippy]
all = { level = "warn", priority = -1 }
pedantic = { level = "warn", priority = -1 }
# targeted allows for pedantic lints that are usually noise:
module_name_repetitions = "allow"
must_use_candidate = "allow"
missing_errors_doc = "allow"   # remove for published libraries

[profile.release]
lto = "thin"
codegen-units = 1
strip = "symbols"
```

Member crate `Cargo.toml` inherits:

```toml
[package]
name = "myproject-core"
version = "0.1.0"
edition.workspace = true
rust-version.workspace = true
license.workspace = true

[dependencies]
serde = { workspace = true }
thiserror = { workspace = true }

[lints]
workspace = true
```

## Toolchain pinning

`rust-toolchain.toml` at repo root:

```toml
[toolchain]
channel = "1.88"              # pin a specific stable; bump deliberately
components = ["rustfmt", "clippy"]
```

Pin a concrete version rather than `"stable"` so CI and every contributor build identically. `rust-version` in Cargo.toml (MSRV) can be lower than the pinned toolchain — the pin is what you develop with, MSRV is what you promise users.

## Module layout conventions

- Prefer `src/foo.rs` + `src/foo/` over `src/foo/mod.rs` (edition-2018+ style; mixing both confuses navigation).
- Keep `lib.rs` as a table of contents: module declarations, re-exports (`pub use`), crate-level docs. No logic.
- Binaries: `src/main.rs` should be < ~50 lines — parse CLI (clap `#[derive(Parser)]`), init tracing, load config, call `lib::run(config)`, map error to exit code.
- One concept per module; split when a file passes ~500 lines *and* has separable concerns, not before.

## Files to generate for every new project

1. `rust-toolchain.toml` (above)
2. `.gitignore`: `/target` (and `.env` if config uses dotenv)
3. `deny.toml` — supply-chain policy (licenses, advisories, duplicate bans)
4. `.github/workflows/ci.yml` — fmt/clippy/test/MSRV/deny/docs pipeline
5. `README.md` with build/test/run commands
6. For libraries: `#![doc = include_str!("../README.md")]` in lib.rs to keep docs and README in sync, plus `#[deny(missing_docs)]` once the API stabilizes

## Config & secrets pattern for services

- `figment` or plain `serde` + `toml` for layered config (defaults < file < env vars).
- Env vars prefixed with the project name (`MYPROJECT_DATABASE_URL`).
- Never read `std::env::var` scattered through the codebase; deserialize once into a `Config` struct at startup and pass it down (or wrap in `Arc<Config>`).

## Common scaffolding by project type

- **CLI**: clap (derive), anyhow, `main() -> anyhow::Result<()>` returning exit codes via `std::process::ExitCode` when granular codes are needed.
- **Web service**: tokio + axum + tower middleware + tracing/tracing-subscriber + serde. Health endpoint and graceful shutdown (`tokio::signal`) from day one. When the choice of web framework is genuinely contested (axum vs actix-web is a real choice — unlike tokio vs async-std, which isn't), default to axum with a one-line reason (tower ecosystem, tokio-native) and mention actix-web as the alternative.
- **gRPC**: tonic + prost; keep `.proto` files in a `proto/` dir and a dedicated `-proto` crate with `build.rs` running `tonic_build`.
- **Library**: no binary, `#![forbid(unsafe_code)]` unless needed, docs with `# Examples` sections that double as doctests.

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

- Prefer showing complete, runnable files (full Cargo.toml, full rust-toolchain.toml) over fragments, unless editing an existing file.
- When choices are genuinely contested (tokio vs async-std is not contested — use tokio; but e.g. axum vs actix-web is a real choice), present the default recommendation with a one-line reason and mention the alternative.
- Respect existing project conventions over this skill's defaults when working in an established codebase.
