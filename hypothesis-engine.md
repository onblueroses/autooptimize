# Hypothesis Engine

Given profile data, experiment history, and codebase constraints - what's the single highest-expected-value change to try next?

This document is the protocol for answering that question. It produces ranked, testable hypotheses. The output is an optimization spec (see `spec-format.md`) ready to hand to any executor.

## Quick Nav

| Task | Jump to |
|------|---------|
| Generate the next hypothesis | Generation Protocol |
| Understand the tier system | Tier System |
| Pick between candidates | Picking Between Candidates |
| Extract signals from past experiments | Experiment Log Synthesis |
| Check a hypothesis before implementing | Quality Rubric |
| Run many hypotheses at once | Parallel Search Mode |
| Log results for future hypotheses | Learning Loop |

---

## Generation Protocol

Follow these steps in order to produce the next hypothesis.

### Step 1: Synthesize the experiment log

Before generating candidates, extract signals from history. See Experiment Log Synthesis below. If there is no history (first experiment), skip to Step 2.

### Step 2: Identify bottlenecks

**Performance metrics (gens/sec, latency, throughput):** Read the profile data (`.claude/autooptimize-profile.md`). If no profile exists and the project config has a `[profiling]` section, run the profiler first. Identify top-5 hotspots by inclusive time.

**Non-performance metrics (accuracy, bundle size, eval pass rate):** Run the domain-equivalent analysis:
- ML accuracy: error analysis - which input categories have the highest error rate?
- Bundle size: bundle analyzer - which modules contribute the most bytes?
- Eval pass rate: failure audit - which eval queries fail most often and why?
- Latency: request tracing - which stages of the pipeline take the longest?

The output is the same regardless of domain: a ranked list of bottlenecks with their contribution to the overall metric. Cross-reference with the experiment log: which bottlenecks have been targeted? Which are exhausted? Which have remaining headroom?

Do not generate hypotheses without bottleneck data. "Try things and see what happens" is not a protocol.

### Step 3: Generate candidates

For each hotspot with remaining headroom, generate one candidate hypothesis per applicable tier. A candidate is:
- A one-sentence description of the change
- The tier (T0-T4)
- A basis citation (specific evidence)
- A predicted impact (Amdahl estimate or domain-specific)

Generate 3-7 candidates. Fewer means you're being too conservative. More means you're not filtering.

### Step 4: Pick the best candidate

Rank candidates by estimated impact adjusted for tier confidence (see Picking Between Candidates). Take the top one.

### Step 5: Select and write spec

Take the top-ranked candidate. Write a full optimization spec using the template in `spec-format.md`. Run the completeness checklist before handing it to an executor.

If the top candidate's estimated impact is below `min_improvement_pct`, consider stopping - you may have hit the plateau.

---

## Tier System

Five tiers, ordered by confidence. Work top to bottom. Move to the next tier when the current one is exhausted.

### T0: Profile-Driven (Highest Confidence)

Target a measured hotspot directly. The profiler tells you where the time goes; you propose a faster implementation of that specific code.

**Entry condition:** Profile data exists with at least one hotspot above 5% inclusive time that hasn't been exhausted.

**Exhaustion condition:** All hotspots above 5% inclusive time have been targeted by at least one T0 experiment that was either KEPT or DISCARDED with a clear root cause showing the hotspot is at its practical minimum. INCONCLUSIVE results do not exhaust a hotspot - the approach may have been wrong, not the target.

**Default base rate:** 0.40. This is a starting prior, not measured data. Your project's observed rate (from the learning loop) replaces this after 3+ T0 experiments.

<details>
<summary>T0 examples</summary>

- "SIMD batch processing of distance calculations" - basis: profiler shows `compute_distances` at 41.2% inclusive
- "Replace HashMap with sorted Vec for small-N lookup" - basis: profiler shows `entity_lookup` at 12.3% inclusive, N always < 50
- "Pre-compute sine table instead of runtime `f32::sin()`" - basis: profiler shows `update_angles` at 8.7% inclusive, only 360 discrete values used

</details>

### T1: Structural (Algorithm/Data Structure)

Changes that alter complexity class or data layout. Higher risk, higher potential reward. These change how the program works, not just how fast it runs.

**Entry condition:** T0 is exhausted or the structural opportunity is obviously higher-value (e.g., O(n^2) in a hot path when O(n log n) is possible).

**Exhaustion condition:** All feasible complexity-class improvements in hot paths (>5% inclusive) have been attempted. "Feasible" means: the algorithm exists, the data supports it, and the invariant constraints allow it.

**Default base rate:** 0.20. Higher variance than T0 - when they work, the improvement is often large. Replace with observed rate after 3+ T1 experiments.

<details>
<summary>T1 examples</summary>

- "Spatial indexing for neighbor search (O(n^2) -> O(n))" - basis: `find_neighbors` is O(n^2), profiler shows 28% inclusive
- "Array-of-Structs to Struct-of-Arrays for position updates" - basis: cache miss rate >5% in `update_positions`, struct has 8 fields but inner loop touches 2
- "Replace recursive tree walk with iterative stack" - basis: profiler shows deep recursion in `evaluate_tree`, stack frames dominate

</details>

### T2: Roadmap Items

Items from the project's performance doc or issue tracker marked as potential optimizations but not yet attempted. These have some prior analysis but haven't been validated against profiler data.

**Entry condition:** T0 is partially exhausted and T1 doesn't have clear candidates, OR a roadmap item has strong prior analysis suggesting high impact.

**Exhaustion condition:** All roadmap items with estimated impact above `min_improvement_pct` have been attempted or invalidated by profiler data.

**Default base rate:** 0.30. Replace with observed rate after 3+ T2 experiments.

### T3: Variations on Partial Successes

Past experiments that improved the metric but failed a gate. The optimization works - only the constraint violation needs solving.

**Entry condition:** At least one prior experiment has status `gate_fail` or `determinism_fail` with a positive metric delta.

**Exhaustion condition:** All partial successes have been re-attempted with adapted approaches, or the constraint is proven incompatible with the optimization.

**Default base rate:** 0.50. Highest-conversion tier because the hard part (finding what works) is already done. Replace with observed rate after 3+ T3 experiments.

<details>
<summary>T3 examples</summary>

- "SIMD distance calc with order-independent reduction" - basis: experiment 003 had +4.1% but failed determinism check due to f32 reordering. Fix: use `f32x8::reduce_sum()` which guarantees ordering.
- "Parallel chunk processing with deterministic merge" - basis: experiment 007 had +6.2% but tests failed on edge case where N < chunk_size. Fix: add remainder handling.

</details>

### T4: Micro-Optimizations (Diminishing Returns)

Constant-factor tuning: `#[inline]`, field reordering, struct padding, branch hints. Small individual impact. Useful for squeezing the last few percent.

**Entry condition:** T0-T3 are exhausted or producing only INCONCLUSIVE results.

**Exhaustion condition:** Two consecutive T4 experiments on the same function produced INCONCLUSIVE results. The function is at its noise floor. Move to a different target or escalate.

**Default base rate:** 0.15. Replace with observed rate after 3+ T4 experiments.

---

## Parallel Search Mode

When sequential tier exhaustion is too slow or the search space is wide, switch to parallel hypothesis generation. This pattern won the Paradigm Autoresearch Hackathon: 1,039 AI-generated strategy variants evaluated in parallel, beating 110 manually-crafted iterations. Final score: 42.32 mean edge (1st place).

### When to use

- The metric is fast to evaluate (benchmark completes in <5 minutes)
- The search space is wide (many plausible approaches, unclear which tier will win)
- T0-T2 are producing INCONCLUSIVE results (the bottleneck is diffuse, not concentrated)
- You have compute budget for N parallel experiments

### Protocol

1. **Generate N candidates across all tiers.** Skip the "pick the best one" step. Instead, generate 5-15 candidates spanning T0-T3. Don't filter by estimated impact - let measurement decide.

2. **Write N specs in parallel.** Each spec is a self-contained optimization experiment. Use the standard spec format but add `parallel_batch: <batch_id>` to the metadata.

3. **Execute all N in isolated branches.** Each experiment runs in its own git worktree or branch. No experiment can see another's changes. Build + benchmark independently.

4. **Rank by measured impact.** After all N complete, rank by actual `delta_pct`. The winner is KEPT. All others are logged as DISCARD with `batch_id` and `batch_rank` in their hypothesis_feedback entry (this feeds the learning loop - a discarded +3% is still useful calibration data).

5. **Compose if compatible.** If the top 2-3 results target different hotspots and their changes don't overlap, attempt sequential composition: apply #1, re-benchmark, apply #2, re-benchmark. Composition fails if the combined delta is less than the sum of individual deltas by more than 20% (interference).

### Tradeoffs

- **Pro:** Explores more of the search space per wall-clock hour. Avoids local optima from sequential hill-climbing. Discovers surprising wins that sequential tier exhaustion would never reach (the Paradigm winner found an "arbitrage risk probability" model that no human designed).
- **Con:** N times the compute cost. Most candidates will be discarded. Requires fast benchmarks - if each run takes 30 minutes, 15 parallel experiments is 7.5 hours of GPU time.
- **When NOT to use:** When T0 has clear, untargeted hotspots above 20% inclusive time. Sequential T0 is cheaper and higher-confidence. Parallel search is for when you've exhausted the obvious wins.

### Logging

Individual experiments use standard hypothesis_feedback entries in `autooptimize-experiments.jsonl` with an added `batch_id` and `batch_rank` field. The batch summary goes to `autooptimize-meta.jsonl` (Channel 2) to avoid breaking the Channel 1 schema:

```jsonl
{"type":"parallel_batch","batch_id":"pb_003","n_candidates":12,"n_kept":1,"n_composed":0,"best_delta_pct":4.1,"median_delta_pct":0.8,"wall_clock_min":45,"compute_min":540}
```

---

## Picking Between Candidates

When you have 3-5 candidates, rank them by estimated impact adjusted for risk:

**Performance metrics** - use Amdahl's Law to estimate impact:

```
estimated_impact = bottleneck_fraction * (1 - 1/speedup_factor) * 100%
```

Example: function is 41.2% of runtime, SIMD gives ~2x speedup: `0.412 * (1 - 1/2) * 100 = 20.6%`.

**Non-performance metrics** - estimate what fraction of the problem this addresses:

- ML accuracy: "Error class X is 30% of failures. Fix covers ~60% of those. ~5.4pp gain."
- Bundle size: "Module X is 72KB of 400KB. Removing unused exports cuts ~50KB. 12.5% reduction."
- Eval pass rate: "Category X fails 8/20 times. Fix targets the failure mode. ~+4 passes."

Every prediction needs a number with a derivation. If you can't derive one, you don't understand the bottleneck well enough.

**Then adjust for risk.** A T0 change targeting a 41% hotspot is a safer bet than a T1 algorithmic rewrite, even if the rewrite has higher theoretical upside. The tier ordering already encodes this - T0 before T1 before T4. Within the same tier, pick the bigger hotspot.

Don't overthink the ranking. With 3-5 candidates, the right answer is usually obvious: the biggest bottleneck at the highest-confidence tier. If it's not obvious, pick either one - you'll learn something regardless.

---

## Experiment Log Synthesis

Extract signals from the experiment history before generating candidates. This turns raw JSONL entries into structured context.

### Procedure

1. **List exhausted avenues.** For each function/approach combination: count experiments, outcomes. If 2+ experiments with the same approach on the same target produced INCONCLUSIVE, mark the avenue as exhausted. Output: `exhausted: [{target, approach, experiments, reason}]`

2. **List discovered constraints.** Scan all `gate_fail` and `determinism_fail` entries. Each failure reveals a boundary of the feasible design space. Output: `constraints: [{constraint, discovered_in, implication}]`
   Example: "SIMD reorders f32 additions" -> all future SIMD work must use order-independent reductions.

3. **List partial successes.** Experiments with positive metric delta but a gate failure. These are the highest-value signal. Output: `partial_successes: [{experiment_id, delta_pct, gate_failed, adaptation_needed}]`

4. **Identify current bottleneck.** Read the most recent profile. If more than 2 experiments have been KEPT since the last profile, the bottleneck may have shifted - re-profile before continuing.

5. **Compute remaining headroom per hotspot.** For each hotspot: original inclusive %, cumulative improvement from KEPT experiments targeting it, remaining fraction. Output: `headroom: [{function, original_pct, improvements_applied, remaining_pct}]`

6. **Check feedback entries.** If `hypothesis_feedback` entries exist from prior sessions, scan for `constraint_discoveries` and `transferable_pattern` fields. A pattern like "SIMD gives 2x not 4x on this workload" directly changes your Amdahl estimates.

### Output format

```
Exhausted: [list]
Constraints: [list]
Partial successes: [list]
Current bottleneck: [function, %]
Headroom: [table]
```

---

## Quality Rubric

Check every item before writing a hypothesis into a spec. Any failure means it's not ready.

- [ ] **Testable prediction**: Includes a specific number (e.g., "8.3% improvement"), not "should be faster"
- [ ] **Falsifiable basis**: Cites measured data. "Profile shows X at Y%" or "Experiment 003 showed +Z%". Not "I think this is slow"
- [ ] **Bounded scope**: Targets one function or one data structure. Not "refactor the hot path"
- [ ] **Predicted impact above noise floor**: Amdahl estimate exceeds the project's `min_improvement_pct`
- [ ] **Not a repeat**: Check exhausted avenues from log synthesis. Same target + same approach = don't bother
- [ ] **Constraint-compatible**: Doesn't violate any discovered constraint from the log synthesis
- [ ] **Mechanism specified**: Explains WHY the change improves the metric, not just WHAT changes. "Eliminates branch overhead in inner loop" vs "rewrite the function"

---

## Learning Loop

After each experiment, write a feedback entry to the experiment log (`autooptimize-experiments.jsonl`). This lives in Channel 1 (ground truth), not Channel 2 (disposable analysis), because future hypothesis generation depends on it.

### Hypothesis Feedback Entry

<details>
<summary>Hypothesis Feedback Entry</summary>

Append after every experiment, regardless of outcome:

```jsonl
{"type":"hypothesis_feedback","experiment_id":"003","tier":"T0","predicted_impact_pct":20.5,"actual_impact_pct":8.3,"prediction_ratio":0.40,"basis_accurate":true,"mechanism_confirmed":true,"gate_failures":[],"constraint_discoveries":["SIMD reorder breaks determinism with naive sum"],"transferable_pattern":"SIMD on f32 hot loops gives 1.5-2x, not theoretical 4x, due to memory bandwidth saturation"}
```

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | Always `"hypothesis_feedback"` |
| `experiment_id` | string | Matches the experiment log entry |
| `tier` | string | T0-T4 |
| `predicted_impact_pct` | number | What the Amdahl estimate predicted |
| `actual_impact_pct` | number or null | What was measured (null if gate_fail before benchmark) |
| `prediction_ratio` | number or null | actual / predicted. <1 means optimistic, >1 means conservative |
| `basis_accurate` | boolean | Was the profiler data / prior experiment data still valid? |
| `mechanism_confirmed` | boolean | Did the change work via the predicted mechanism? |
| `gate_failures` | string[] | Which gates failed, if any |
| `constraint_discoveries` | string[] | New constraints discovered from this experiment |
| `transferable_pattern` | string | A pattern that applies beyond this specific experiment |

</details>

The `prediction_ratio` field (actual/predicted) is useful for noticing if your estimates are consistently optimistic. If you see ratios clustering around 0.4-0.5 after several experiments, your Amdahl speedup estimates are probably 2x too high. Adjust future estimates accordingly - but do it by judgment, not a formula. With 5 experiments, any statistical calibration is noise.
