# Phase 3 — Code Quality, Idioms & API Design

## Error handling (the #1 review item)

**Libraries** — typed errors with thiserror:

```rust
#[derive(Debug, thiserror::Error)]
pub enum StoreError {
    #[error("record {id} not found")]
    NotFound { id: u64 },
    #[error("storage backend failed")]
    Backend(#[from] sqlx::Error),   // source preserved for error chains
}
```

Rules: variants describe *what failed* in domain terms, not which function failed; `#[from]` only when the conversion is unambiguous; don't expose third-party error types in public API without deliberation (they become part of your semver surface — consider `#[error(transparent)]` wrappers or boxing).

**Applications** — `anyhow::Result` with context at each fallible boundary:

```rust
let config = std::fs::read_to_string(&path)
    .with_context(|| format!("reading config from {}", path.display()))?;
```

**Never** in library or request-path code: bare `unwrap()`, `expect("")`, `panic!` on recoverable conditions. Acceptable: `expect("mutex poisoned")`-style true invariants (with a message stating *why it can't fail*), tests, examples, build scripts.

Exit-code mapping in binaries: `fn main() -> anyhow::Result<()>` for simple tools; `ExitCode` + manual error printing when specific codes matter.

## Ownership & API design checklist

- **Accept borrows, return owned**: parameters `&str`, `&[T]`, `impl AsRef<Path>`; return `String`, `Vec<T>`. Take ownership only when you actually store the value.
- Prefer `impl Trait` in argument position for one-off generics; named generics when the type appears multiple times.
- `#[must_use]` on builders and on functions whose ignored result is a bug.
- Constructors: `new()` for infallible, `try_new()` or a builder for fallible/multi-parameter construction. Use `derive_builder` or hand-rolled typestate builders for 4+ optional params.
- Newtypes over primitive obsession: `struct UserId(u64)` prevents argument-swap bugs at zero cost. Derive `Copy, Clone, Debug, PartialEq, Eq, Hash` as applicable.
- Implement standard traits eagerly on public types: `Debug` (always), `Clone`, `PartialEq`, `Default`, `Display` where meaningful, `serde` derives behind a `serde` feature for libraries.
- Avoid `Deref` for inheritance-like tricks; it's for smart pointers only.
- Sealed traits (`mod private { pub trait Sealed {} }`) when downstream impls would break your evolution.

## Concurrency & async idioms

- Don't hold `std::sync::Mutex`/`RwLock` guards across `.await` (compile error with Send bounds, deadlock risk otherwise) — use `tokio::sync::Mutex` only when a lock must span awaits; prefer restructuring so it doesn't.
- Share state via `Arc<T>` where `T` is immutable, `Arc<Mutex<T>>`/`Arc<RwLock<T>>` (std, parking_lot) for short critical sections, or message passing (`tokio::sync::mpsc`) for ownership-transfer designs.
- Spawned tasks: capture what you need with `move`, keep them cancel-safe or document that they aren't; use `JoinSet` for dynamic task groups; always have a shutdown path (`CancellationToken` from tokio-util).
- CPU-bound work inside async: `tokio::task::spawn_blocking` or rayon — never block the runtime.

## Unsafe code policy

- Default `#![forbid(unsafe_code)]` for application crates; `warn` + documented exceptions for others.
- Every `unsafe` block needs a `// SAFETY:` comment stating the invariant that makes it sound.
- Isolate unsafe in a small module with a safe API; test with `cargo +nightly miri test` in CI for crates with meaningful unsafe.

## Lints & formatting

- rustfmt with defaults; a `rustfmt.toml` only for `imports_granularity = "Module"`-style team preferences (nightly-only options — verify before adding).
- Clippy configured in `[lints]` (see 01-setup.md), gated with `-D warnings` in CI only (not locally, to keep dev loop pleasant).
- Use `#[expect(clippy::lint_name, reason = "...")]` (Rust 1.81+) instead of `#[allow]` — it warns when the suppression becomes unnecessary.

## Idiom quick-hits for code review

- `if let ... else` / `let ... else` for early returns over nested match.
- Iterator chains over index loops, but don't contort logic to avoid a `for`; `collect::<Result<Vec<_>, _>>()` for fallible maps.
- `impl Display` + `to_string()`, never `format!("{:?}")` for user-facing text.
- `matches!(x, Pattern)` for boolean pattern checks.
- Return `impl Iterator` instead of collecting when the caller might not need a Vec.
- `Cow<'_, str>` when a function sometimes allocates.
- `#[non_exhaustive]` on public enums/structs likely to grow.
- `tracing::instrument` on async entry points; structured fields (`%user_id`) over string interpolation.
- Prefer `TryFrom` impls over ad-hoc `to_x()` conversion methods.

## Documentation as part of code quality

- Every public item on a published crate: one-line summary, then details. `# Errors`, `# Panics`, `# Examples` sections where applicable.
- Doctests are tests: write examples that compile and assert. Use `no_run` for examples needing network/IO, not `ignore`.
- Crate root: what/why/quickstart. `#![doc = include_str!("../README.md")]` keeps README as the source of truth.

## Verification ritual after writing code

```bash
cargo check                                  # fast feedback
cargo clippy --all-targets --all-features    # lint everything incl. tests
cargo fmt
cargo test                                   # if behavior changed
```

Report which of these actually ran and their results; never imply code was verified when it wasn't.
