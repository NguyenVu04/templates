# Phase 7 — Release & Distribution

## Versioning (semver, as Cargo interprets it)

- `0.x.y`: bumping `x` is breaking, `y` is compatible — Cargo treats `0.x` like a major series. Most crates live at 0.x for a long time; that's normal.
- Breaking changes include: removing/renaming public items, adding enum variants or struct fields to non-`#[non_exhaustive]` types, adding trait methods without defaults, tightening bounds, bumping a *publicly re-exported* dependency's major version, raising MSRV (policy-dependent — declare yours).
- Automate detection: `cargo semver-checks check-release` before every library release.

## Publishing to crates.io checklist

Cargo.toml metadata (publish fails or looks broken without these):

```toml
[package]
name = "mycrate"
version = "0.3.0"
description = "One sentence, shows in search results"
license = "MIT OR Apache-2.0"
repository = "https://github.com/user/mycrate"
documentation = "https://docs.rs/mycrate"     # optional, defaults to docs.rs
readme = "README.md"
keywords = ["localization", "fingerprint"]     # max 5
categories = ["science"]                       # from crates.io/category_slugs
exclude = ["/tests/fixtures", "/.github"]      # keep package small
```

Process:
1. `cargo semver-checks check-release` (libs)
2. Update CHANGELOG.md (Keep a Changelog format; or automate via release-plz/git-cliff)
3. `cargo publish --dry-run` then `cargo package --list` to inspect contents
4. `cargo publish` (in dependency order for workspaces — or let release-plz sequence it)
5. Tag: `git tag v0.3.0 && git push --tags`

Publishing is permanent (yank hides but never deletes). Workspace publishing order matters: leaf crates first; `cargo release` or release-plz handle this automatically.

## docs.rs polish for libraries

```toml
[package.metadata.docs.rs]
all-features = true
rustdoc-args = ["--cfg", "docsrs"]
```

plus `#[cfg_attr(docsrs, doc(cfg(feature = "tls")))]` on feature-gated items so docs show which feature enables what.

## Binary distribution: cargo-dist

For CLIs, `dist init` interactively generates a GitHub workflow that on `v*` tags builds a target matrix, uploads to GitHub Releases, and generates installers (curl-sh script, PowerShell, Homebrew formula, npm shim, MSI). This replaces hand-written release matrices — prefer it over bespoke YAML unless requirements are unusual.

## Cross-compilation

- Easy path: `cargo zigbuild` (Zig as linker — painless glibc version targeting) or `cross` (Docker-based, good for exotic targets).
- Static Linux binaries: target `x86_64-unknown-linux-musl`; watch for openssl (use rustls) and other C deps.
- `cargo build --target aarch64-unknown-linux-gnu` natively needs a cross linker configured in `.cargo/config.toml` — this is what zigbuild/cross abstract away.

## Docker packaging for services

Multi-stage with cargo-chef for layer-cached dependencies:

```dockerfile
FROM rust:1.88-slim AS chef
RUN cargo install cargo-chef
WORKDIR /app

FROM chef AS planner
COPY . .
RUN cargo chef prepare --recipe-path recipe.json

FROM chef AS builder
COPY --from=planner /app/recipe.json recipe.json
RUN cargo chef cook --release --recipe-path recipe.json   # deps layer, cached
COPY . .
RUN cargo build --release --bin myserver

FROM debian:bookworm-slim AS runtime
RUN useradd -u 10001 appuser
COPY --from=builder /app/target/release/myserver /usr/local/bin/
USER appuser
ENTRYPOINT ["/usr/local/bin/myserver"]
```

Variants: `gcr.io/distroless/cc-debian12` for smaller/safer runtime; musl build + `FROM scratch` for the minimal case (only if no dynamic deps). Pin the Rust image tag to match `rust-toolchain.toml`.

## Changelog discipline

- Keep a Changelog format, newest first, sections Added/Changed/Fixed/Removed/Security.
- Automate from conventional commits with git-cliff or release-plz if the team actually writes conventional commits; hand-written otherwise — a curated 5-line changelog beats 40 auto-generated commit subjects.

## Release readiness gate (run before any release)

```bash
cargo fmt --check && \
cargo clippy --all-targets --all-features -- -D warnings && \
cargo test --all-features && \
cargo doc --no-deps && \
cargo deny check && \
cargo semver-checks check-release   # libraries only
```
