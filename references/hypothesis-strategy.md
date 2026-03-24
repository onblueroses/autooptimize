# Hypothesis Strategy for Autooptimize

How to generate and prioritize optimization hypotheses. This doc is the "high-freedom" part of the loop - the LLM's strength is reasoning about code and forming hypotheses, not following rigid scripts.

## Prioritization Ladder

<details>
<summary>Prioritization Ladder</summary>

Try ideas in this order. Move to the next tier only when the current tier is exhausted or blocked.

### Tier 1: Roadmap Items (Highest Impact)

Read the project's performance doc (PERFORMANCE.md or equivalent). Look for items under the roadmap section marked "High impact" or similar. Cross-reference with the experiment log - skip anything already tried and failed.

These are the lowest-risk, highest-reward experiments because someone already identified them as promising and estimated their impact.

### Tier 2: Variations on Partial Successes

If a past experiment improved the metric but failed a gate (e.g., broke determinism, failed tests), the underlying idea might still be good. Adapt the approach:
- If determinism failed: check if the change reordered floating-point operations in a parallel context. Try making the computation order-independent.
- If tests failed: the optimization might have an edge case. Fix the edge case rather than discarding the approach entirely.
- If the improvement was below threshold: combine with another micro-optimization to push past the threshold.

### Tier 3: Novel Ideas from Code Reading

Read the hot path code. Look for:
- Unnecessary allocations in loops
- Cache-unfriendly access patterns (stride > 64 bytes between accesses)
- Branches that could be replaced with branchless arithmetic
- Redundant computations (same value computed multiple times)
- Opportunities for SIMD (4+ identical operations on different data)
- Layout changes (AoS -> SoA or vice versa)

### Tier 4: Micro-optimizations

Small, safe changes with modest expected impact:
- Constant tuning (buffer sizes, spatial grid cell sizes)
- Loop unrolling hints
- `#[inline]` / `#[inline(always)]` on hot functions
- Reducing struct sizes to improve cache utilization
- Reordering struct fields for alignment

</details>

## Rust-Specific Optimization Patterns

<details>
<summary>Rust-Specific Optimization Patterns</summary>

### SIMD / Auto-vectorization
- Restructure inner loops to operate on contiguous f32 arrays
- Avoid branches inside the innermost loop (use conditional moves or masks)
- Ensure loop trip counts are known at compile time when possible
- Use `#[repr(align(32))]` on arrays processed by SIMD
- Check auto-vectorization: `RUSTFLAGS="-C target-cpu=znver3 --emit=asm" cargo build --release`, grep for `vmulps`/`vaddps`

### Cache Locality
- Struct-of-Arrays (SoA) > Array-of-Structs (AoS) when iterating one field
- Keep hot data contiguous: if only 3 fields of a 20-field struct are used in the inner loop, extract them
- Minimize pointer indirection: `Vec<T>` > `Vec<Box<T>>` > `Vec<Arc<T>>`
- Pre-sort data by access pattern when possible

### Allocation Reduction
- Move allocations outside loops (`Vec::with_capacity` + `clear()` instead of `Vec::new()` each iteration)
- Use stack arrays (`[T; N]`) for small, fixed-size collections
- Reservoir sampling instead of collecting into a Vec
- `SmallVec` for vectors that are usually small

### Branch Elimination
- `if x > 0 { x } else { 0 }` -> `x.max(0)` (branchless on most architectures)
- Replace `%` (remainder/modulo) with conditional subtract when the value is within 2x the modulus
- `bool as usize` for conditional indexing

### Profiling
- `samply record` for flamegraphs (best tool for Rust on Linux)
- `perf stat` for instruction-level metrics (IPC, cache misses, branch mispredicts)
- `cargo bench` with criterion for micro-benchmarks of isolated functions

</details>

## Semiotic-Emergence Context

<details>
<summary>Semiotic-Emergence Context</summary>

### Current Bottleneck (2026-03-23)

`receive_detailed_grid` in `src/signal.rs:158-272` accounts for 41% of runtime. It's the inner loop where each prey checks nearby signals in the spatial grid.

The inner loop structure:
```
for each prey (384-2000):
  for each ring (0..r_max):
    for each cell in ring:
      for each signal in cell:
        compute wrap_delta (2x conditional)
        early exit on single-axis range
        compute dist_sq (2x mul + add)
        compare to range_sq
        update best per-symbol if closer
```

### What's Been Tried and Failed

From PERFORMANCE.md "Not worth it" section:

| Attempt | Result | Why it failed |
|---------|--------|---------------|
| Branchless signal reception | -7% regression | Loss of early single-axis bailout. Well-predicted branches win here. |
| Per-symbol signal index | -23% regression at pop=2000 | 6x cell-iteration overhead from separate ring traversals per symbol |
| target-cpu=native on laptop | No measurable difference | LLVM auto-vectorizes with SSE2, hot loops are branch-heavy |
| wrap_delta lookup table | Not needed | Conditional wrap (CMOV) is already fast enough |
| I/O decoupling | Not worth it | CSV writes are once per generation, not the bottleneck |
| GPU offload | Poor fit | Branch-heavy step(), brain at 1000x12 neurons too small for transfer overhead |

### What's Promising

From PERFORMANCE.md "High impact" roadmap:

**#9: SIMD distance batch in receive_detailed_grid.** After spatial filtering, batch remaining candidates into SSE/AVX lanes (4-8 at once). Pure arithmetic inner loop is ideal for vectorization. Expected: 2-4x on the 41% bottleneck = 8-16% overall improvement.

**#10: Batch brain forward.** Restructure as matrix multiply across all prey. Enables BLAS-style optimization. Requires genome layout changes for row-major access. Medium impact, higher complexity.

### Architecture Constraints

- Single ChaCha8Rng - never create a second source of randomness
- Deterministic replay from seed is mandatory
- Clippy pedantic + deny(unwrap_used, expect_used, panic)
- Metrics are read-only (never modify world state during measurement)
- Vision (5.6) : signal range (22.4) = 4:1 ratio is a core design parameter

</details>

## Estimating Expected Impact

Before implementing, estimate the expected speedup:

```
expected_improvement = bottleneck_fraction * (1 - 1/speedup_factor) * 100%
```

Example: If `receive_detailed_grid` is 41% of runtime and SIMD gives 2x speedup on that function:
```
0.41 * (1 - 1/2) * 100% = 20.5% overall improvement
```

If the expected improvement is below `min_improvement_pct` (2%), it's probably not worth the experiment. Move to the next hypothesis.

## Anti-Patterns

- **Don't optimize what you haven't profiled.** Intuition about bottlenecks is wrong more often than right.
- **Don't combine multiple changes.** If experiment #5 combines SIMD + layout change and improves 8%, you don't know which contributed. Keep experiments atomic.
- **Don't fight the branch predictor.** If profiling shows low branch misprediction rate on a branch, branchless alternatives often regress (they do more work unconditionally).
- **Don't add complexity for < 2% gain.** The maintenance cost exceeds the performance benefit.
- **Don't assume local benchmarks transfer.** VPS has different CPU (Zen 3 shared), different cache hierarchy, different contention. Always benchmark on VPS.
