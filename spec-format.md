# Spec Format

A spec encodes one optimization hypothesis as a task: what to change, why, how to evaluate, and what to do with the result. The agent executing the spec doesn't need to read anything else.

## Quick Nav

| Task | Jump to |
|------|---------|
| See a complete example | Example Spec |
| Adapt for non-performance metrics | Non-Performance Metrics |
| Write a spec from scratch | Template |
| Check if a spec is complete | Completeness Checklist |
| Avoid common mistakes | Antipatterns |

---

## Example Spec

A complete spec. Copy this to a coding agent - it has everything needed to run the experiment.

```markdown
# Optimization Spec: SIMD Batch Distance Calculation

Experiment: 001
Project: boid-sim
Branch: autoopt/001-simd-distance
Created: 2026-03-31T14:00:00Z

## Hypothesis

SIMD batch processing of distance calculations will reduce branch overhead
and enable vectorized arithmetic in the hot loop.

**Predicted mechanism:** Replace scalar pairwise distance computation with
batched f32x8 SIMD operations. Eliminates per-pair branch overhead and
allows the CPU to process 8 distance calculations per instruction.

**Predicted impact:** 20.5% overall improvement.
Calculation: compute_distances is 41.2% of runtime (profiler). SIMD gives
~2x speedup on this workload. Amdahl: 0.412 * (1 - 1/2) = 20.6%.

## Basis

Tier: T0 (profile-driven)
Citation: samply flamegraph shows compute_distances at 41.2% inclusive,
38.1% exclusive. Flat top - leaf function, prime SIMD target.
Confidence: high - direct profiler measurement on representative workload.

## Scope

Modify:
- `src/signal.rs` — replace scalar distance loop with SIMD batch version

Do not modify:
- `src/sim.rs` — simulation loop (caller, not the bottleneck)
- `bench.sh` — benchmark script is the evaluator, never touch it
- Any test files — tests must pass without modification

Invariants:
- Output must be deterministic for the same seed (checked below)
- Distance calculations must produce identical results (f32 tolerance: 1e-6)

## Implementation Guidance

Approach:
1. Extract the inner distance loop from `compute_distances()`
2. Restructure input arrays as contiguous f32 slices (SoA if currently AoS)
3. Use `std::simd::f32x8` for batch processing
4. Handle remainder elements (N % 8) with scalar fallback
5. Ensure `#[repr(align(32))]` on the input arrays

Do not:
- Combine this with any other optimization (one change per experiment)
- Use unsafe code unless required for alignment
- Reorder floating-point additions (breaks determinism)

Maximum diff: ~50 lines changed in one file.

## Acceptance Criteria

Run these checks in order. Stop on first failure.

1. **Compile** — `cargo build --release`
   Pass: exit code 0
   Fail action: fix once, if still failing log `gate_fail` and discard

2. **Lint** — `cargo clippy -- -D warnings`
   Pass: exit code 0
   Fail action: fix lint issues, retry once

3. **Test** — `cargo test`
   Pass: all tests pass
   Fail action: if test failure relates to the change, log `gate_fail` and discard

4. **Determinism** — run twice with seed 42, 10 generations each, diff output
   Pass: outputs are byte-identical
   Fail action: log `determinism_fail` with root cause and discard

5. **Benchmark** — A/B comparison (see Evaluation Protocol below)
   Pass: delta >= 2.0% AND SNR >= 2.0
   Fail action: see Result Handling

## Evaluation Protocol

Benchmark: `./bench.sh`
Metric: `gens_per_sec` (higher is better)
Baseline: main branch (current best: 6.17 gens/sec)

Procedure:
1. Build both binaries: main (baseline) and this branch (experiment)
2. Warm up: 2 runs each, discard results
3. Interleave: 7 runs each, alternating B-E-B-E-B-E-B-E-B-E-B-E-B-E
4. Compute: median of each set, CoV of each set
5. delta_pct = (experiment_median - baseline_median) / baseline_median * 100
6. SNR = |delta_pct| / (CoV_baseline + CoV_experiment)

Thresholds:
- min_improvement_pct: 2.0
- min_snr: 2.0
- max_runs: 7 per binary

## Result Handling

**KEEP** (delta >= 2.0% AND SNR >= 2.0):
- Merge branch to main
- Push to origin
- Delete branch (local + remote)
- Log experiment entry (see below)
- New baseline = experiment_median

**INCONCLUSIVE** (|delta| < 2.0% OR SNR < 2.0):
- Delete branch (local + remote)
- Log with analysis: was the change too small, or is the benchmark too noisy?
- Do NOT increment failure counter

**DISCARD** (delta < -2.0% AND SNR >= 2.0):
- Delete branch (local + remote)
- Log with root cause analysis
- Increment failure counter

## Result

_Filled in by the executor after running the experiment._

- **Outcome**: KEEP | INCONCLUSIVE | DISCARD
- **Metric before**: gens/sec
- **Metric after**: gens/sec
- **Delta**: %
- **SNR**:
- **Gate results**: [compile: , lint: , test: , determinism: , benchmark: ]
- **Notes**:

## Experiment Log Entry

_Template. Fill in all null/empty fields from the Result section before appending to `autooptimize-experiments.jsonl`._

{"timestamp":"__FILL__","id":"001","branch":"autoopt/001-simd-distance","hypothesis":"SIMD batch distance calc","basis":"T0: profile hotspot compute_distances (41.2%)","files_changed":["src/signal.rs"],"metric_before":6.17,"metric_after":"__FILL__","delta_pct":"__FILL__","snr":"__FILL__","kept":"__FILL__","notes":"__FILL__"}
```

---

## Non-Performance Metrics

The example above optimizes runtime performance (gens/sec). The same format works for any measurable metric - you just swap the estimation method and evaluation protocol.

<details>
<summary>Non-Performance Metrics</summary>

### ML accuracy / eval pass rate

- **Hypothesis**: "Adding chain-of-thought prompting will improve classification accuracy on ambiguous cases." Not Amdahl's Law - use empirical estimates: "Baseline: 84.2%. Similar CoT improvements in literature: +3-8%. Predicted: 87%."
- **Basis**: Error analysis, confusion matrix patterns, literature precedent. T0 equivalent: targeting the highest-error class.
- **Evaluation Protocol**: Run eval set N times (stochastic output), report mean accuracy with bootstrap CI. Decision: KEEP if mean improvement >= threshold AND CI doesn't contain zero.
- **Profiling equivalent**: Error analysis. Which input categories fail most? That's your "hotspot."

### Bundle size / build output

- **Hypothesis**: "Tree-shaking the unused lodash imports will reduce bundle size." Predicted: "lodash contributes 72KB of 400KB total. Removing unused: ~50KB reduction (12.5%)."
- **Basis**: Bundle analyzer output (equivalent to profiler). Direct measurement of module sizes.
- **Evaluation Protocol**: Build, measure output size. Deterministic - single run is sufficient. Decision: KEEP if size reduction >= threshold.

### Latency / response time

- **Hypothesis**: "Connection pooling will reduce p95 latency." Predicted: "Database connection setup is 40ms of 120ms p95. Pool eliminates setup for cached connections: ~33% reduction."
- **Evaluation Protocol**: Load test with fixed request pattern, measure p50/p95/p99. Multiple runs with statistical comparison (same A/B protocol as performance).

### LLM output quality

- **Hypothesis**: "Adding a specification-lawyer evaluator framing will catch 'close enough' implementations that the default framing misses."
- **Basis**: Audit of past eval runs showing false-positive rate on borderline outputs.
- **Evaluation Protocol**: Run eval set with both framings, compare unique-finding rates. Decision: KEEP if unique_findings_rate improves AND total_pass_rate doesn't regress beyond constraint.

### The general pattern

Swap "profiler hotspot" for whatever bottleneck analysis your domain uses. Swap "Amdahl's Law" for whatever estimation method fits. The structure stays the same: hypothesis with mechanism, basis with evidence, gates ordered by cost, statistical decision.

</details>

---

## Template

Every spec must include these sections. Optional sections are marked.

<details>
<summary>Template</summary>

```markdown
# Optimization Spec: [short description]

Experiment: [NNN]
Project: [project-name]
Branch: autoopt/[NNN]-[short-name]
Created: [ISO 8601 timestamp]

## Hypothesis

[One paragraph: what you're changing and the predicted mechanism.]

**Predicted mechanism:** [How the change produces the improvement. Be specific
about the CPU/memory/IO behavior that changes.]

**Predicted impact:** [X% overall improvement.]
Calculation: [function] is [Y%] of runtime. [Change] gives ~[Z]x speedup.
Amdahl: [Y/100] * (1 - 1/[Z]) = [X%].

## Basis

Tier: [T0-T4]
Citation: [specific evidence - profiler data, experiment log entry, roadmap item]
Confidence: [high/medium/low] - [one-line justification]

## Scope

Modify:
- `[file]` — [what changes]

Do not modify:
- `[file]` — [why not]

Invariants:
- [constraints that must hold after the change]

## Implementation Guidance

Approach:
1. [concrete step]
2. [concrete step]

Do not:
- [specific antipattern for this change]

Maximum diff: [rough line count estimate]

## Acceptance Criteria

Run these checks in order. Stop on first failure.

1. **[Gate name]** — `[command]`
   Pass: [condition]
   Fail action: [what to do]

[repeat for each gate, cheapest first]

## Evaluation Protocol

Benchmark: `[command]`
Metric: `[name]` ([higher/lower] is better)
Baseline: [branch] (current best: [value] [unit])

Procedure:
[numbered steps for A/B comparison]

Thresholds:
- min_improvement_pct: [N]
- min_snr: [N]
- max_runs: [N] per binary

## Result Handling

**KEEP** (delta >= [N]% AND SNR >= [N]):
- [actions]

**INCONCLUSIVE** (|delta| < [N]% OR SNR < [N]):
- [actions]

**DISCARD** (delta < -[N]% AND SNR >= [N]):
- [actions]

## Result

_Filled in by the executor after running the experiment._

- **Outcome**: KEEP | INCONCLUSIVE | DISCARD
- **Metric before**: [value] [unit]
- **Metric after**: [value] [unit]
- **Delta**: [value]%
- **SNR**: [value]
- **Gate results**: [gate: pass/fail, ...]
- **Notes**: [observations, root cause if discarded]

## Experiment Log Entry

_Append this to `autooptimize-experiments.jsonl` after completing the experiment._

[pre-filled JSONL template with nulls for measured values]
```

</details>

---

## Section Reference

<details>
<summary>Section Reference</summary>

### Identity (required)

The header block: experiment number, project name, branch name, timestamp. Enough to locate this experiment in git and logs.

### Hypothesis (required)

What you're changing and why you think it will work. Must include:
- **Predicted mechanism** - the causal chain from code change to metric improvement. "SIMD reduces branch overhead" is a mechanism. "Should be faster" is not.
- **Predicted impact** - a number with a calculation. Use Amdahl's Law for performance work. Use domain-specific estimates for other metrics. The prediction is tested after the experiment for calibration.

### Basis (required)

Where the hypothesis came from. Tier (T0-T4) plus the specific evidence. A hypothesis without a basis is speculation. See `hypothesis-engine.md` for the tier system and how to generate hypotheses.

### Scope (required)

What files to modify, what files NOT to modify, and what invariants must hold. The "do not modify" list is as important as the "modify" list - it prevents scope creep and protects the evaluator (benchmark script, test files).

### Implementation Guidance (required)

Concrete approach: numbered steps, specific functions to change, patterns to follow. Also: what NOT to do. This section replaces vague instructions with a roadmap.

**Maximum diff** is a soft constraint that catches scope creep. If the implementation exceeds the estimate by 3x, something went wrong with the hypothesis scoping.

### Acceptance Criteria (required)

Ordered list of gates, cheapest first. Each gate has a command, a pass condition, and a fail action. Run sequentially, stop on first failure. Free checks (compile, lint) run before cheap checks (test) run before expensive checks (benchmark).

### Evaluation Protocol (required)

How to measure the metric. For performance: the A/B benchmarking procedure with specific run counts, warmup, interleaving pattern, and statistical thresholds. For other metrics: the measurement procedure and decision criteria.

### Result Handling (required)

What to do with each outcome. KEEP, INCONCLUSIVE, and DISCARD have different actions. This section must be unambiguous - the executor follows it mechanically.

### Result (required, filled by executor)

Structured output the executor fills in after running. Feeds into the learning loop.

### Experiment Log Entry (optional)

Pre-filled JSONL template. Reduces friction for logging. The executor fills in measured values and appends to the experiment log.

</details>

---

## Completeness Checklist

Before handing a spec to an executor, verify every item. An incomplete spec produces ambiguous results.

- [ ] **Testable prediction**: Hypothesis includes a specific metric change (number), not "should improve"
- [ ] **Falsifiable basis**: Basis cites measured data (profiler, experiment log, known complexity), not intuition
- [ ] **Bounded scope**: Modify list is explicit, do-not-modify list covers the evaluator and tests
- [ ] **Concrete implementation**: Approach has numbered steps referencing specific functions/files, not "optimize the code"
- [ ] **Ordered gates**: Acceptance criteria are ordered cheapest to most expensive
- [ ] **Every gate has a fail action**: No gate leaves the executor guessing what to do on failure
- [ ] **Measurement procedure**: Evaluation protocol specifies exact commands, run counts, and thresholds
- [ ] **All three outcomes handled**: KEEP, INCONCLUSIVE, and DISCARD each have explicit actions
- [ ] **Single change**: The spec describes one hypothesis, not a bundle of optimizations
- [ ] **Impact above noise floor**: Predicted impact exceeds min_improvement_pct from project config

---

## Antipatterns

<details>
<summary>Antipatterns</summary>

### Vague hypothesis

**Bad:** "Try to optimize the distance calculation."
**Good:** "SIMD batch processing of f32 distance pairs eliminates per-pair branch overhead. Predicted: 20.5% improvement (Amdahl on 41.2% hotspot, 2x speedup)."

The test: could two different engineers read this hypothesis and implement the same change? If not, it's too vague.

### Missing acceptance criteria

**Bad:** Spec has Hypothesis and Scope but no Acceptance Criteria. The executor implements the change and... then what?

Every spec must define what "done" looks like. Even if the only gate is "it compiles and tests pass," write that down.

### Untestable prediction

**Bad:** "This should make the code cleaner and faster."
**Good:** "Predicted: 8.3% improvement in gens_per_sec. Measured via A/B benchmark, 7 runs each."

If you can't write a number, you don't have a hypothesis - you have a hope. Rephrase or find a measurable proxy.

### Scope creep

**Bad:** "While we're in signal.rs, also refactor the neighbor lookup and add some tests."

One spec, one change. If the refactor is worth doing, it gets its own spec with its own measurement. Bundled changes make it impossible to attribute metric changes to specific optimizations.

### Optimistic fail actions

**Bad:** "Fail action: investigate and fix."
**Good:** "Fail action: fix once. If still failing, log gate_fail with root cause analysis and discard."

The executor needs a bounded procedure, not an open-ended debugging session. One retry is reasonable. Unlimited retries are not.

### Missing "do not modify" list

**Bad:** Scope only lists files to change.

The do-not-modify list protects the measurement infrastructure. If the executor accidentally improves the benchmark script instead of the code, the result is meaningless.

</details>

---

## Executor Interface

The executor receives a spec, implements the change, runs the gates, fills in the Result section, and executes the Result Handling actions. It doesn't choose what to optimize or decide whether to continue - that's the hypothesis engine's job.

The executor needs to: read markdown, run shell commands, edit source files, and use git. Any coding agent can do this.
