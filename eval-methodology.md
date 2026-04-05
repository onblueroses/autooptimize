# Eval Methodology

How to build evaluators, eval fixtures, and benchmarks for AI agent outputs. Defines the eval type taxonomy, assertion primitives, fixture formats, and common failure modes.

Companion to `autooptimize-methodology.md`. The optimization loop needs good evaluation - this document covers how to build the evaluators that measure what you're optimizing.

---

## Quick Nav

| Task | Jump to |
|------|---------|
| Pick the right eval type | Eval Types |
| Understand assertion primitives | Assertion Primitives |
| Write an eval fixture | Fixture Formats |
| Decide which type to use | Decision Flowchart |
| Structure a dataset | Dataset Design |
| Use bootstrap CI or adaptive sampling | Statistical Rigor |
| Stop benchmarking early when signal is clear | SPRT Early Stopping |
| Gate cheap checks before expensive ones | Evaluation Composition |
| Detect noisy benchmark environments | Noise Floor Detection |
| Avoid common mistakes | Common Failures |

---

## Eval Types

<details>
<summary>Eval Types</summary>

Five types, ordered from cheapest to most expensive to run. Pick the cheapest type that can detect the failure mode you care about.

| Type | What it checks | Cost |
|------|---------------|------|
| **Trigger** | Did the right skill/tool fire? | Free (subprocess) |
| **Behavioral** | Does output contain/not-contain specific content? | Free (string ops) |
| **Benchmark** | Does a stochastic metric land in acceptable bands? | Low (N runs) |
| **Semantic** | Does an LLM judge pass the output against natural-language criteria? | High (LLM call) |
| **Regression** | Does output match a known-good baseline (snapshot)? | Medium (diff) |

### Trigger

**Definition:** Verifies that a given input causes a specific tool or skill to be invoked (or not invoked). Binary pass/fail.

**Use when:** You need to test routing logic - "does this prompt cause the agent to call the right skill?"

**Example:** Query `"review my changes before committing"` should trigger the `review` skill. Query `"what time is it"` should not.

---

### Behavioral

**Definition:** Verifies structural properties of the output using deterministic string operations. No LLM needed.

**Use when:** You can specify the test as "output must contain X" or "output must not mention Y." Works for format compliance, required keywords, forbidden phrases.

**Example:** A commit message generator's output must contain a verb in the subject line. A privacy-aware response must not contain PII patterns.

---

### Benchmark

**Definition:** Runs the same query N times, aggregates a numeric metric, and checks it falls within a `{min, target, tolerance}` band.

**Use when:** The output is stochastic and you care about average quality rather than any single run. Metrics like accuracy, trigger rate, score distribution.

**Example:** A skill's trigger rate on "should trigger" queries must be >= 0.80 (min) with target 0.90.

---

### Semantic

**Definition:** An LLM judge evaluates the output against one or more natural-language criteria. Returns `passed: bool` + `justification: String` per criterion.

**Use when:** Quality is subjective or structural checks aren't expressive enough. "The explanation should be concise and avoid jargon" cannot be checked with a regex.

**Example:** A code review output must "identify the most critical issue without nitpicking style" - only a judge can assess this.

**Key rule:** Configure the judge model separately from the tested model (different temperature, different instance). Prevents the model from judging its own outputs.

---

### Regression

**Definition:** Stores a known-good output as a golden file; future runs diff against it. Fails on unexpected change.

**Use when:** You have a verified correct output and want to detect regressions. Useful for deterministic transformations (formatters, linters, code generators with fixed inputs).

**Gap note:** Neither lm-evaluation-harness nor Braintrust have built-in snapshot regression testing - this is a genuine gap in the ecosystem.

</details>

---

## Assertion Primitives

<details>
<summary>Assertion Primitives</summary>

An `Assertion` has a `kind`, an optional `weight` (default 1.0), and is evaluated against the LLM's output string.

### AssertionKind variants

| Kind | Signature | Evaluated by | Example |
|------|-----------|-------------|---------|
| `Contains(String)` | Output must contain substring | String search (free) | `Contains("Error:")` |
| `NotContains(String)` | Output must not contain substring | String search (free) | `NotContains("TODO")` |
| `Regex(String)` | Output must match regex pattern | Regex engine (free) | `Regex("^#\\s+\\w+")` |
| `LlmJudge(String)` | Output must satisfy natural-language criterion | LLM subprocess (expensive) | `LlmJudge("mentions the root cause without suggesting a workaround")` |

**Design rule (from verifiers):** Deterministic assertions (`Contains`, `NotContains`, `Regex`) are evaluated inline without any LLM call. Only `LlmJudge` assertions trigger a subprocess. Mix both kinds freely - the runtime separates them automatically.

### Weight and pass_threshold

`weight` controls how much each assertion contributes to the overall pass decision. `pass_threshold` on the query sets the fraction of weighted assertions that must pass (default: all must pass).

```json
{
  "query": "write a commit message for this diff",
  "should_trigger": true,
  "pass_threshold": 0.75,
  "assertions": [
    { "kind": { "Contains": "feat" }, "weight": 1.0 },
    { "kind": { "NotContains": "WIP" }, "weight": 2.0 },
    { "kind": { "LlmJudge": "subject line is under 72 characters and uses imperative mood" }, "weight": 1.5 }
  ]
}
```

Here, weighted total = 4.5. Pass threshold 0.75 requires 3.375 weighted points. If the `NotContains` (weight 2.0) and `LlmJudge` (weight 1.5) pass, total = 3.5 > 3.375 - passes even if `Contains` fails.

### Assertion composition rules

- **Use `Contains`/`NotContains` first.** Promote to `LlmJudge` only when string matching is too rigid.
- **One criterion per `LlmJudge`.** A judge cannot reliably evaluate two independent qualities in one assertion. Split them.
- **Negative assertions are as important as positive.** Test what the output should NOT do or say.
- **Don't make assertions tautological.** `Contains("")` always passes. `LlmJudge("is a valid response")` always passes.

</details>

---

## Fixture Formats

<details>
<summary>Fixture Formats</summary>

Fixtures live in JSON files. One file = one eval set for one skill. Arrays of `EvalQuery` objects.

**Design rule (from verifiers):** Fixtures store inputs and expected properties only. Scoring logic lives in the backend/rubric, not in the fixture. A fixture file should be readable by a human without understanding the eval framework.

### Trigger-only (minimal)

```json
[
  { "query": "review my staged changes", "should_trigger": true, "category": "direct" },
  { "query": "what is 2 + 2", "should_trigger": false, "category": "unrelated" },
  { "query": "can you check my code before I commit", "should_trigger": true, "category": "indirect" }
]
```

### With behavioral assertions

```json
[
  {
    "query": "write a function that adds two numbers",
    "should_trigger": true,
    "assertions": [
      { "kind": { "Contains": "def " } },
      { "kind": { "NotContains": "TODO" } },
      { "kind": { "Regex": "def \\w+\\(.*\\):" } }
    ]
  }
]
```

### With benchmark band

```json
[
  {
    "query": "refactor this function for readability",
    "should_trigger": true,
    "benchmark_band": { "min": 0.70, "target": 0.85, "tolerance": 0.05 }
  }
]
```

`min`: hard floor (fail below this). `target`: goal. `tolerance`: acceptable deviation from target in either direction before flagging as degraded.

### Combined: assertions + semantic + threshold

```json
[
  {
    "query": "explain why this test is failing",
    "should_trigger": true,
    "pass_threshold": 0.67,
    "assertions": [
      { "kind": { "NotContains": "I don't know" }, "weight": 2.0 },
      { "kind": { "LlmJudge": "identifies a specific cause, not just restates the error message" }, "weight": 1.0 },
      { "kind": { "LlmJudge": "suggests a concrete next step" }, "weight": 1.0 }
    ]
  }
]
```

### File naming convention

```
skills/
  review/
    eval-set.json              # primary eval set (used by optimizer)
    eval-set-edge-cases.json   # supplemental sets
    eval-set-negatives.json
```

Keep supplemental sets separate so the optimizer's train/test split isn't contaminated by hand-curated edge cases.

</details>

---

## Decision Flowchart

<details>
<summary>Decision Flowchart</summary>

```
Can you write a deterministic check for this failure mode?
|
+-- Yes: Is it "did the right tool fire"?
|         +-- Yes -> Trigger eval (EvalQuery.should_trigger)
|         +-- No: Is it "output contains/doesn't contain X"?
|                   +-- Yes -> Behavioral eval (AssertionKind::Contains/NotContains/Regex)
|                   +-- No: Is there a numeric metric you care about?
|                             +-- Yes -> Benchmark band (EvalQuery.benchmark_band)
|                             +-- No -> ??? (see below)
|
+-- No: Is the quality judgment subjective or hard to specify precisely?
          +-- Yes -> Semantic eval (AssertionKind::LlmJudge)
          +-- No: Can you record a known-good output to diff against?
                    +-- Yes -> Regression / golden file
                    +-- No -> You may not have a testable requirement yet.
                              Write down what "correct" looks like first.
```

**Rule of thumb:** If you find yourself writing a `LlmJudge` assertion that starts with "is a good" or "is correct" - stop. That's the tautological trap. Make the criterion specific: *what* makes it good? Write that instead.

**When to mix types:** A single query can combine all types. Trigger + behavioral + semantic is common: verify routing, then check structural properties cheaply, then use the judge only for the nuanced quality check.

</details>

---

## Dataset Design

<details>
<summary>Dataset Design</summary>

### Minimum set sizes

| Eval type | Minimum examples | Recommended | Rationale |
|-----------|-----------------|-------------|-----------|
| Trigger | 20 | 40+ | Train/test split needs at least 12/8 for meaningful accuracy |
| Behavioral | 10 | 20+ | Deterministic - smaller sets are fine |
| Benchmark | 5 | 10+ | Run each N=3 times minimum; statistical noise matters |
| Semantic | 10 | 15+ | LLM judge has variance; need enough to distinguish signal from noise |

### Class balance

For trigger evals: aim for 40-60% positive (`should_trigger: true`). Heavily imbalanced sets (90% positive) make false-negative rates invisible.

For behavioral/semantic: include both "good output" and "bad output" examples. If all your examples test what the output should contain, you're not testing what it should reject.

### Category coverage

Use `category` to tag examples by the kind of trigger or failure mode. Run per-category accuracy to diagnose which category is weak, not just overall accuracy.

Common categories: `direct` (explicit request), `indirect` (implicit), `negative` (should not trigger), `edge-case` (boundary behavior), `adversarial` (attempts to mislead).

### Deterministic splits

Always use a fixed seed when splitting. Pass the same seed for reproducible splits across optimization iterations. Changing the seed changes which examples land in train vs test, potentially inflating reported improvement.

### Handling stochastic outputs with `repeats`

For benchmark evals, run each query `repeats: N` times (minimum N=3, recommended N=5). A single run result is noise. Report the mean and whether it falls in the benchmark band.

### Keep fixture files clean

Never store runtime outputs (actual LLM responses) in fixture files. Fixtures are static inputs + expected properties. Runtime outputs belong in eval result logs, not committed JSON.

</details>

---

## Reliability Metrics

<details>
<summary>Reliability Metrics</summary>

When running multiple attempts per query, two complementary metrics capture different failure modes:

### pass@k (lucky-once)

Probability that at least one of k runs passes. Useful for creative tasks where you only need one good output.

```
pass@k = 1 - (1 - p)^k
```

Where `p` is the per-run pass probability estimated from observed data.

### pass^k (all-runs-ok)

Probability that all k runs pass. Useful for reliability-critical tasks where every invocation must succeed.

```
pass^k = p^k
```

### When to report

Only display pass@k and pass^k when they diverge meaningfully from the raw pass rate. If pass@k ~= pass^k, the eval is deterministic and the metrics add noise. When they diverge, it signals stochastic behavior worth investigating.

### Interpretation

| pass@k | pass^k | Meaning |
|--------|--------|---------|
| High | High | Reliable - passes consistently |
| High | Low | Flaky - sometimes works, sometimes doesn't. Needs debugging. |
| Low | Low | Broken - rarely works |
| Low | High | Impossible (pass^k <= pass@k always) |

</details>

---

## Statistical Rigor

<details>
<summary>Statistical Rigor</summary>

### Bootstrap Confidence Intervals

When you have N benchmark runs and need to know how confident you are in the median, use bootstrap resampling instead of assuming a normal distribution.

**Algorithm (bootstrap difference of medians):**
```
1. Collect N paired measurements: baseline[i], experiment[i] for i in 1..N
   (pairs come from the interleaved A/B protocol)
2. For j in 1..B (B=10000):
   a. Sample N indices WITH replacement
   b. Compute median of resampled baseline values -> boot_baseline[j]
   c. Compute median of resampled experiment values -> boot_experiment[j]
   d. boot_delta[j] = boot_experiment[j] - boot_baseline[j]
3. Sort boot_delta
4. CI_lower = boot_delta[B * 0.025]
5. CI_upper = boot_delta[B * 0.975]
```

This bootstraps the same statistic the decision logic uses (difference of medians), so the CI and the reported delta_pct agree. Resampling the same indices for both arrays preserves the pairing from interleaved runs.

**When to use:** Any benchmark with N >= 7 paired runs. Below 7, the CI is too wide to be useful - increase N first.

**Decision rule:** If the CI does not contain zero, the change is statistically significant. If the CI contains zero, the result is INCONCLUSIVE.

### Adaptive Sample Sizing

Don't commit to a fixed number of runs. Start small, add runs if the signal is unclear.

**Protocol:**
```
1. Run initial N=7 paired measurements (minimum for reliable bootstrap CI)
2. Compute bootstrap CI on paired differences (see above)
3. Convert CI to percentage of baseline: CI_width_pct = (CI_upper - CI_lower) / baseline_median * 100
4. If CI_width_pct < min_improvement_pct: stop (enough precision to decide)
5. If CI_width_pct >= min_improvement_pct AND N < max_runs:
   a. Add 2 more paired runs (interleaved)
   b. Recompute CI
   c. Go to step 3
6. If N = max_runs and CI still wide: result is INCONCLUSIVE (environment too noisy)
```

**Thresholds:**
- Initial runs: 7 per binary (minimum for bootstrap CI)
- Max runs: 15 per binary (local) or 10 per binary (VPS)
- CI width target: `min_improvement_pct` from project config (default 2.0%), expressed as percentage of baseline

This saves time on clear wins (stop at 5 runs) and invests more measurement on borderline results.

</details>

---

## SPRT Early Stopping

<details>
<summary>SPRT Early Stopping</summary>

Sequential Probability Ratio Test (SPRT) lets you decide "keep" or "discard" after each measurement pair, without waiting for all N runs. Useful for large improvements (stop early) and clear regressions (stop early).

### Setup

- **H0 (null):** The experiment has no effect. `delta = 0`.
- **H1 (alternative):** The experiment improves the metric by at least `min_improvement_pct`.
- **alpha = 0.05:** Probability of falsely accepting H1 (false positive).
- **beta = 0.10:** Probability of falsely accepting H0 (false negative / missed improvement).
- **Boundaries:** `A = ln(beta / (1 - alpha))`, `B = ln((1 - beta) / alpha)`

### Procedure

Assumes paired differences are approximately normal (reasonable for benchmark timing after warmup). Estimate variance from the first 3 pairs, then test sequentially.

**Direction normalization:** If `metric_direction = "lower"` (e.g., latency), flip the sign: `delta_i = baseline_i - experiment_i` so that improvement is always positive. For `metric_direction = "higher"`, use `delta_i = experiment_i - baseline_i`.

```
1. After each interleaved pair i, compute:
   delta_i = (experiment_i - baseline_i) * direction_sign
   where direction_sign = +1 for "higher is better", -1 for "lower is better"

2. After 3+ pairs, estimate:
   mu_hat = mean(delta_1..delta_i)
   sigma_hat = stddev(delta_1..delta_i)
   effect_size = min_improvement_pct / 100 * baseline_median

   Under H0: delta ~ Normal(0, sigma_hat^2)
   Under H1: delta ~ Normal(effect_size, sigma_hat^2)

3. For each new pair, update cumulative LLR:
   LLR += (delta_i * effect_size / sigma_hat^2) - (effect_size^2 / (2 * sigma_hat^2))

4. Compare LLR to boundaries:
   If LLR >= B: ACCEPT H1 (improvement detected, stop early)
   If LLR <= A: ACCEPT H0 (no improvement, stop early)
   If A < LLR < B: CONTINUE (not enough evidence yet)

5. If all N pairs exhausted without crossing a boundary:
   Result is INCONCLUSIVE
```

### Practical notes

- SPRT is most valuable when the effect is large. A 20% improvement typically triggers after 3-4 pairs. A 2% improvement needs almost all pairs.
- SPRT does NOT replace the full benchmark for borderline results. If SPRT is inconclusive, fall back to the full adaptive sampling protocol.
- SPRT assumes each pair is independent. The interleaved B-E-B-E pattern from A/B Benchmarking satisfies this.

### When NOT to use

- When you need the full distribution (tail latency analysis, variance characterization)
- When the metric is not pair-wise comparable (e.g., accuracy over a dataset, not per-run timing)
- First experiment in a session (no prior variance estimate to parameterize H1)

</details>

---

## Evaluation Composition

Multi-tier evaluation gates cheap checks before expensive ones. A failure at any tier skips all subsequent tiers.

### Gate Order

| Tier | Check | Cost | Stops on |
|------|-------|------|----------|
| 1 | Compile | Free | Syntax errors, type errors |
| 2 | Lint | Free | Style violations, common bugs |
| 3 | Test | Cheap | Functional regressions |
| 4 | Determinism | Cheap | Non-deterministic behavior |
| 5 | Benchmark | Expensive | Performance regression or no improvement |
| 6 | Semantic (if applicable) | Very expensive | Quality regression |

### How it works

Run gates sequentially. If gate N fails, the experiment outcome is determined by the fail action in that gate's spec entry. Do not run gate N+1.

This saves the most expensive check (benchmarking, which requires multiple runs and wall-clock time) for experiments that have already passed every cheaper check.

### Worked example

<details>
<summary>Worked example</summary>

An experiment modifies `src/signal.rs` to add SIMD processing:

1. **Compile** (`cargo build --release`): PASS (3 seconds)
2. **Lint** (`cargo clippy -- -D warnings`): PASS (5 seconds)
3. **Test** (`cargo test`): FAIL - one assertion in `test_distance_accuracy` fails because SIMD reorders float additions

**Result:** `gate_fail` logged with root cause "SIMD f32 reordering changes distance results beyond tolerance." Experiment is DISCARDED. Benchmark never runs, saving ~5 minutes of A/B comparison.

The constraint "SIMD must use order-independent reductions" is added to the experiment log and fed back to the hypothesis engine via the learning loop.

</details>

---

## Noise Floor Detection

<details>
<summary>Noise Floor Detection</summary>

When the benchmark environment is too noisy, small improvements are invisible. Detect this and adapt.

### Protocol

CoV is expressed as a percentage throughout (CoV = std/mean * 100). This keeps it in the same units as `min_improvement_pct`.

1. After warmup, compute CoV of the baseline runs: `CoV_pct = (std / mean) * 100`.
2. **If CoV_pct <= 2%:** Environment is clean. Proceed with normal thresholds.
3. **If CoV_pct is 2-5%:** Environment is moderately noisy. Increase N to max_runs. Only accept effects with SNR >= 3.0 (stricter than default 2.0).
4. **If CoV_pct > 5%:** Environment is too noisy for small-effect detection.
   - Log the noise level in the experiment entry
   - Temporarily raise `min_improvement_pct` to `CoV_pct * 3` (e.g., 6% CoV -> require 18% effect)
   - Consider: is the benchmark running on shared infrastructure? Are background processes interfering? Can you reduce noise at the source?
5. **If CoV_pct > 10%:** Abort benchmarking. The environment cannot distinguish signal from noise. Fix the environment before continuing.

### Root causes of high noise

- Background processes (CI runners, cron jobs, other benchmarks)
- Thermal throttling (CPU frequency scaling under sustained load)
- VM/container overhead (virtualization introduces measurement variance)
- I/O contention (benchmark writing logs while measuring CPU-bound code)
- NUMA effects (process migrating between CPU sockets)

</details>

---

## Common Failures

<details>
<summary>Common Failures</summary>

### 1. Exact-match brittleness

**Problem:** Testing `output == expected_string` when the output is generated text. Fails on trivial rephrasing that preserves correctness.

**Mitigation:** Use `Contains` for required keywords, `LlmJudge` for semantic correctness. Reserve exact match for deterministic code generation with fixed inputs (regression tier).

---

### 2. Tautological assertions

**Problem:** Assertions that always pass regardless of output quality. `Contains("")`, `LlmJudge("is a helpful response")`, `NotContains("zzz")`.

**Detection:** Run your assertions against a known-bad output. If they still pass, the assertions are tautological.

**Mitigation:** Every assertion must be falsifiable. Write the bad output you're trying to prevent, then write the assertion that catches it.

---

### 3. Missing negative examples

**Problem:** All examples test what should happen. No examples test what should NOT happen. Result: a model that always fires passes all tests.

**Mitigation:** At least 30% of trigger eval examples should be `should_trigger: false`. For behavioral evals, include examples with deliberately bad outputs that should fail assertions.

---

### 4. Judge agrees with bad outputs

**Problem:** The LLM judge is too lenient. Assigns `passed: true` to outputs that clearly fail the criterion.

**Detection:** Feed known-bad outputs through the judge and check the `justification` field. If the judge is making excuses, recalibrate.

**Mitigation:** Make judge criteria concrete and negative: "does NOT suggest workarounds when the root cause is unknown" is harder to pass than "addresses the root cause." Use a separate judge model, not the same model that generated the output.

---

### 5. Stochastic undersampling

**Problem:** Running each query once for a benchmark eval. A single run can be an outlier.

**Mitigation:** Minimum N=3 runs per query for benchmark evals. Use `benchmark_band.tolerance` to encode the acceptable variance range.

---

### 6. Train/test contamination

**Problem:** Using the same examples for both optimizer training and final evaluation. The optimizer overfits to the train set; test accuracy looks artificially high.

**Mitigation:** Separate train/test with a deterministic seed. Never manually add examples to the test set that were inspired by observing failures during training.

---

### 7. Single-dimension coverage

**Problem:** All assertions test the same dimension (e.g., all check for a specific keyword). A model that includes that keyword regardless of actual quality passes every assertion.

**Mitigation:** Use category tags. Ensure assertions cover orthogonal dimensions: structural (format, length), content (required elements), quality (semantic correctness), safety (forbidden outputs).

</details>
