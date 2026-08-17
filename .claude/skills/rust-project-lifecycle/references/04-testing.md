# Phase 4 — Testing

## Test taxonomy and where each lives

| Kind | Location | Purpose |
|---|---|---|
| Unit | `#[cfg(test)] mod tests` in the same file | Private functions, edge cases, fast feedback |
| Integration | `tests/*.rs` | Public API as a consumer sees it |
| Doctests | `///` examples | API docs that can't rot |
| Property | unit or integration, via proptest | Invariants over generated inputs |
| Snapshot | via insta | Complex output (rendered text, JSON, error messages) |
| E2E for CLIs | `tests/` with assert_cmd | Binary behavior, exit codes, stdout |

Structure integration tests as one `tests/integration.rs` (or a few themed files) with submodules — each `tests/*.rs` file is a separate crate and link unit, so 30 tiny files slow the build.

## Runner: cargo-nextest

Prefer `cargo nextest run` over `cargo test` for projects with more than trivial test suites: per-test process isolation, better output, retries for flaky tests, JUnit output for CI. Doctests still need `cargo test --doc` (nextest doesn't run them) — include both in CI.

## Writing good unit tests

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_rsrp_within_3gpp_range() {
        let m = Measurement::parse("-95.5").unwrap();
        assert_eq!(m.rsrp_dbm(), -95.5);
    }

    #[test]
    fn rejects_rsrp_below_floor() {
        let err = Measurement::parse("-150").unwrap_err();
        assert!(matches!(err, ParseError::OutOfRange { .. }));
    }
}
```

- Name tests as behavior statements, not `test_fn_name_1`.
- One logical assertion cluster per test; table-driven loops are fine but prefer `rstest` parametrized cases so failures identify the input:

```rust
#[rstest]
#[case(-140.0, true)]
#[case(-44.0, true)]
#[case(-141.0, false)]
fn rsrp_range_validation(#[case] value: f64, #[case] ok: bool) { /* ... */ }
```

- `unwrap()`/`expect()` are fine in tests; better: `fn test() -> anyhow::Result<()>` and use `?`.
- Test error paths as first-class citizens, not just happy paths.

## Async tests

```rust
#[tokio::test]
async fn fetch_times_out() {
    tokio::time::pause();                      // virtual time: no real sleeping
    let fut = client.fetch_with_timeout(Duration::from_secs(30));
    tokio::time::advance(Duration::from_secs(31)).await;
    assert!(matches!(fut.await, Err(FetchError::Timeout)));
}
```

Use `tokio::time::pause()`/`advance()` for anything timing-related — real sleeps make suites slow and flaky. `#[tokio::test(start_paused = true)]` sets it from the start.

## Doubles: prefer fakes over mocks

Order of preference:
1. **Real thing, cheap**: in-memory SQLite for sqlx, `tempfile::TempDir` for filesystem, wiremock for HTTP.
2. **Hand-written fake** implementing your trait (e.g., `InMemoryStore` with a `HashMap`).
3. **mockall** when interaction verification is genuinely the point.

Design for testability: depend on traits at I/O boundaries (`trait Clock`, `trait Store`), inject via generics or `Arc<dyn Store>`.

## Property-based testing (proptest)

Use for parsers, serializers, math, and any encode/decode pair:

```rust
proptest! {
    #[test]
    fn roundtrip(record in arb_record()) {
        let bytes = encode(&record);
        prop_assert_eq!(decode(&bytes).unwrap(), record);
    }
}
```

Commit `proptest-regressions/` to git — it replays past failures.

## Snapshot testing (insta)

For CLI help text, rendered templates, serialized structures, error message wording:

```rust
#[test]
fn renders_report() {
    insta::assert_snapshot!(render_report(&sample()));
}
```

Review changes with `cargo insta review`. Snapshots make "did my refactor change output?" a diff instead of an argument.

## CLI testing (assert_cmd + predicates)

```rust
#[test]
fn missing_arg_exits_2() {
    assert_cmd::Command::cargo_bin("mycli").unwrap()
        .arg("convert")
        .assert()
        .failure()
        .code(2)
        .stderr(predicates::str::contains("required"));
}
```

## Coverage

`cargo llvm-cov nextest` (or `--html` locally). Use coverage to find untested modules, not as a gate percentage; if a gate is required, gate on patch coverage, not total.

## Test hygiene rules

- Tests must not depend on execution order, wall-clock time, network, or shared mutable global state. Nextest's process-per-test surfaces these violations quickly.
- Anything touching real ports/files uses ephemeral resources (`TcpListener::bind("127.0.0.1:0")`, `TempDir`).
- Slow/expensive tests: mark `#[ignore = "requires docker"]` and run explicitly (`cargo nextest run --run-ignored all`) in a scheduled CI job.
- Shared setup goes in `tests/common/mod.rs` (a `common.rs` file would itself become a test crate).
