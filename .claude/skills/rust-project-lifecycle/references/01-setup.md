# Phase 1 — Setup & Scaffolding

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
3. `deny.toml` — see 02-dependencies.md
4. `.github/workflows/ci.yml` — see 05-ci-cd.md
5. `README.md` with build/test/run commands
6. For libraries: `#![doc = include_str!("../README.md")]` in lib.rs to keep docs and README in sync, plus `#[deny(missing_docs)]` once the API stabilizes

## Config & secrets pattern for services

- `figment` or plain `serde` + `toml` for layered config (defaults < file < env vars).
- Env vars prefixed with the project name (`MYPROJECT_DATABASE_URL`).
- Never read `std::env::var` scattered through the codebase; deserialize once into a `Config` struct at startup and pass it down (or wrap in `Arc<Config>`).

## Common scaffolding by project type

- **CLI**: clap (derive), anyhow, `main() -> anyhow::Result<()>` returning exit codes via `std::process::ExitCode` when granular codes are needed.
- **Web service**: tokio + axum + tower middleware + tracing/tracing-subscriber + serde. Health endpoint and graceful shutdown (`tokio::signal`) from day one.
- **gRPC**: tonic + prost; keep `.proto` files in a `proto/` dir and a dedicated `-proto` crate with `build.rs` running `tonic_build`.
- **Library**: no binary, `#![forbid(unsafe_code)]` unless needed, docs with `# Examples` sections that double as doctests.
