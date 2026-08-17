# Phase 6 — Performance: Benchmarking, Profiling, Optimization

## The iron rule

Measure → change → measure. No optimization lands without a benchmark or profile showing (a) the code was hot and (b) the change helped. Resist speculative `#[inline]`, hand-rolled SIMD, or clever unsafe until profiling justifies it.

## Benchmarking

**criterion** (statistical, mature) or **divan** (simpler, faster to write). Criterion setup:

```toml
[dev-dependencies]
criterion = { version = "0.5", features = ["html_reports"] }

[[bench]]
name = "fingerprint"
harness = false
```

```rust
// benches/fingerprint.rs
use criterion::{criterion_group, criterion_main, BatchSize, Criterion};

fn bench_knn(c: &mut Criterion) {
    let db = load_test_db();
    c.bench_function("wknn_k5_41k", |b| {
        b.iter_batched(
            || sample_query(),
            |q| db.wknn(std::hint::black_box(&q), 5),
            BatchSize::SmallInput,
        )
    });
}
criterion_group!(benches, bench_knn);
criterion_main!(benches);
```

Key points: `black_box` inputs/outputs to defeat const-folding; `iter_batched` when setup shouldn't be timed; bench realistic data sizes, not toys. Compare runs with `cargo bench -- --save-baseline before` / `--baseline before`. CI regression tracking: bencher.dev or `criterion-compare` actions — but benchmarks on shared CI runners are noisy; treat CI benches as smoke tests, trust local/dedicated hardware for decisions.

## Profiling

Always profile **release builds with debug symbols**:

```toml
[profile.profiling]
inherits = "release"
debug = true
strip = false
```

Tools by question:
- **Where is CPU time going?** `cargo flamegraph --profile profiling` (Linux perf under the hood; needs `perf_event_paranoid` ≤ 2) or `samply record ./target/profiling/app` (great UI, cross-platform).
- **Why is this async service slow?** tokio-console (task-level: which tasks are busy/starved) + tracing spans with timing; flamegraphs of async code are hard to read — lean on instrumentation.
- **Allocations?** `dhat` crate (heap profiling as a test), or swap in jemalloc/mimalloc and compare (often a free 5-20% for allocation-heavy services):

```toml
[dependencies]
mimalloc = "0.1"
```
```rust
#[global_allocator]
static GLOBAL: mimalloc::MiMalloc = mimalloc::MiMalloc;
```

- **Binary size?** `cargo bloat --release -n 20`.

## Release profile tuning

```toml
[profile.release]
lto = "thin"          # "fat" squeezes a few % more at big compile cost
codegen-units = 1     # better optimization, slower build
panic = "abort"       # smaller/faster if you don't need unwinding (breaks catch_unwind)
strip = "symbols"
```

`opt-level = 3` is default; `"s"`/`"z"` only for size-constrained targets. PGO (`cargo-pgo`) for the last 5-15% on mature hot services — not before.

## Common optimization patterns (apply after profiling confirms)

1. **Allocation churn**: reuse buffers (`Vec::clear` + refill), `String` → `&str` plumbing, `SmallVec` for tiny hot vectors, `Box<str>`/`Arc<str>` for stored immutable strings.
2. **Cloning to satisfy borrowck**: restructure ownership first; `Arc` second; `clone()` in hot loops is a smell but in cold paths is fine — don't uglify cold code.
3. **Hashing hot**: `FxHashMap`/`ahash` (non-DoS-resistant — only for trusted keys), or `Vec` + linear scan for < ~30 elements.
4. **Iterator vs index**: usually identical after optimization; check `--emit asm` or Godbolt only when it truly matters. Bounds checks: prefer restructuring (iterators, `chunks_exact`) over `get_unchecked`.
5. **Parallelism**: rayon `par_iter` for data-parallel CPU work — measure, as small workloads lose to splitting overhead.
6. **Async service throughput**: check you're not blocking the runtime (spawn_blocking for CPU/disk), connection pooling sized correctly, and buffer/batch small writes (`BufWriter`, message batching) before micro-optimizing.
7. **Layout**: order struct fields by alignment only for arrays-of-millions; consider SoA (struct-of-arrays) for numeric batch processing.

## When numbers look wrong

- Benchmarking debug builds (100x slowdowns) — check `--release`.
- Turbo/thermal noise: pin CPU frequency or use `--warm-up-time`/more samples.
- The compiler deleted your work: verify with `black_box` and sanity-check throughput against theoretical limits (memory bandwidth, NIC line rate).
