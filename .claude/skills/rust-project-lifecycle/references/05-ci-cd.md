# Phase 5 — CI/CD (GitHub Actions)

## The baseline pipeline

`.github/workflows/ci.yml` — copy and adapt:

```yaml
name: CI
on:
  push: { branches: [main] }
  pull_request:

env:
  CARGO_TERM_COLOR: always
  RUSTFLAGS: "-D warnings"

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  check:
    name: fmt + clippy
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: dtolnay/rust-toolchain@stable
        with: { components: "rustfmt, clippy" }
      - uses: Swatinem/rust-cache@v2
      - run: cargo fmt --all --check
      - run: cargo clippy --all-targets --all-features

  test:
    name: test (${{ matrix.os }})
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]  # trim to ubuntu-only if platform-independent
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: dtolnay/rust-toolchain@stable
      - uses: Swatinem/rust-cache@v2
      - uses: taiki-e/install-action@nextest
      - run: cargo nextest run --all-features
      - run: cargo test --doc --all-features

  msrv:
    name: MSRV
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: dtolnay/rust-toolchain@master
        with: { toolchain: "1.85" }   # keep in sync with rust-version in Cargo.toml
      - uses: Swatinem/rust-cache@v2
      - run: cargo check --all-features

  deny:
    name: cargo-deny
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: EmbarkStudios/cargo-deny-action@v2

  docs:
    name: doc build
    runs-on: ubuntu-latest
    env: { RUSTDOCFLAGS: "-D warnings" }
    steps:
      - uses: actions/checkout@v4
      - uses: dtolnay/rust-toolchain@stable
      - uses: Swatinem/rust-cache@v2
      - run: cargo doc --no-deps --all-features
```

Notes:
- `RUSTFLAGS: -D warnings` at the env level makes both check and test jobs strict; keep local builds lenient.
- `dtolnay/rust-toolchain` respects `rust-toolchain.toml` when pointed at `@stable` won't — if you pin via the file, use the action without a toolchain arg or `@master`. Verify current action semantics if uncertain.
- Trim the matrix aggressively for private/internal projects — CI minutes are real money; a full matrix belongs on published cross-platform crates.

## Optional jobs, add when relevant

- **Feature powerset** (published libs): `taiki-e/install-action@cargo-hack` + `cargo hack check --feature-powerset --depth 2`.
- **Miri** (crates with unsafe): nightly toolchain + `cargo miri test`, scheduled weekly rather than per-PR (slow).
- **Coverage**: `taiki-e/install-action@cargo-llvm-cov` + `cargo llvm-cov nextest --lcov --output-path lcov.info` + Codecov upload.
- **Semver check** (published libs): `obi1kenobi/cargo-semver-checks-action@v2` — catches accidental breaking changes before release.
- **cargo-udeps / machete**: unused dependency detection, scheduled.

## Caching strategy

`Swatinem/rust-cache@v2` covers 90% of cases (caches registry + target dir keyed on lockfile + toolchain). Beyond that: `sccache` with GHA backend (`mozilla-actions/sccache-action`) for large workspaces, or a self-hosted runner with persistent disk.

Cache-busting gotcha: the cache keys on `Cargo.lock`; PRs that bump many deps get cold caches — that's expected, don't fight it.

## Release automation

Two solid patterns; pick one:

**Pattern A — release-plz (libraries, crates.io-focused)**: bot maintains a release PR with version bumps + changelog (from conventional commits); merging it publishes to crates.io and tags. Setup: `release-plz.toml` + a workflow using `release-plz/action`, secrets `CARGO_REGISTRY_TOKEN`.

**Pattern B — cargo-dist (binaries)**: `dist init` generates a release workflow that, on tag push, builds binaries for a target matrix, creates GitHub Releases with installers (shell/powershell/homebrew/MSI). Best-in-class for CLI distribution.

For containerized services, a `docker/build-push-action` job on tags pushing to GHCR — Dockerfile in 07-release.md.

## Pipeline hygiene

- Pin third-party actions to a major version at minimum; security-sensitive repos pin to SHA.
- Grant minimal permissions: top-level `permissions: contents: read`, escalate per job.
- Fail fast locally instead: mirror CI in a `justfile`/`Makefile` (`just ci` runs fmt+clippy+nextest) so contributors don't discover failures 10 minutes after pushing.
