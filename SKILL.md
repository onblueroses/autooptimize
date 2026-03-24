---
name: autooptimize
description: |
  Autonomous code optimization loop inspired by Karpathy's autoresearch. Reads per-project config
  from .claude/autooptimize.toml, generates optimization hypotheses, implements on isolated branches,
  benchmarks on VPS, keeps improvements, discards regressions. Full cycle: hypothesize -> implement ->
  test -> benchmark -> decide -> log -> repeat.
  Manual: when the user asks to optimize performance, run autooptimize, or wants autonomous
  experimentation on measurable code metrics.
---

# Autooptimize

Autonomous optimization loop. One metric, one loop, git-based rollback.

```
/autooptimize              # Run with defaults from config
/autooptimize --max 10     # Override max experiments
/autooptimize --dry-run    # Show what would be tried, don't execute
```

## Skip Conditions

- **Skip if** no `.claude/autooptimize.toml` exists in the project - tell the user to create one
- **Skip if** git working tree is dirty - require clean state before starting
- **Skip if** not on main/master branch - the loop starts from main

## Instructions

### Phase 0: Initialize

<details>
<summary>Phase 0: Initialize</summary>

1. **Read config.** Parse `.claude/autooptimize.toml` from the project root. Validate all required fields are present. The config defines everything project-specific: scope files, build/test/bench commands, VPS connection, metric, constraints.

2. **Check git state.** Must be on `main` (or `master`), clean working tree. If not, stop and tell the user.

3. **Parse arguments.** Check for `--max N` (override `constraints.max_experiments`), `--dry-run` (plan only).

4. **Establish baseline.** Check if `[context].experiment_log` file exists. If not, or if it's empty:
   - Build: run `[build].command` locally to verify it compiles
   - Push current main to origin
   - SSH to VPS, pull, build with `[build].vps_rustflags`, run benchmark script
   - Parse median metric value from benchmark output
   - Create the experiment log file with header and a baseline row:
     ```
     timestamp	experiment_id	branch	hypothesis	files_changed	metric_before	metric_after	delta_pct	kept	notes
     {now}	000-baseline	main	baseline measurement	-	-	{metric}	-	-	initial baseline
     ```
   - Report baseline to user

   If the log exists, read the last "kept" row to get the current best metric. That's the baseline.

5. **Load context.** Read:
   - `[context].performance_doc` (e.g., PERFORMANCE.md) - bottleneck analysis, optimization roadmap
   - `[context].experiment_log` - past experiments (avoid repeating failures)
   - Scope files listed in `[project].scope` - the code that can be modified
   - `references/hypothesis-strategy.md` from this skill's directory - optimization patterns

6. **Report plan.** Tell the user: "Baseline: {metric} {unit}. Will run up to {max} experiments. Stopping after {max_failures} consecutive failures."

</details>

### Phase 1: Experiment Loop

For each experiment (up to `constraints.max_experiments`):

#### Step 1: Hypothesize

<details>
<summary>Step 1: Hypothesize</summary>

Generate the next optimization hypothesis. Read `references/hypothesis-strategy.md` for detailed guidance. The prioritization ladder:

1. **Roadmap items**: Check `[context].performance_doc` for items under `[context].roadmap_section` marked "High impact" that haven't been tried (check experiment log)
2. **Variations on partial successes**: If a past experiment improved the metric but failed a gate, adapt the approach
3. **Novel ideas**: Based on reading the scope files and understanding the hot path
4. **Micro-optimizations**: Constant tuning, layout changes, branch prediction hints

Write a 1-2 sentence hypothesis with expected impact. Identify which files will change.

If `--dry-run`: print the hypothesis and stop (don't implement).

</details>

#### Step 2: Implement

<details>
<summary>Step 2: Implement</summary>

1. **Create branch.** Format: `autoopt/{NNN}-{short-name}` where NNN is zero-padded experiment number, short-name is 2-4 word kebab-case description. Example: `autoopt/001-simd-distance-batch`.

   ```bash
   git checkout -b autoopt/{NNN}-{short-name}
   ```

2. **Edit code.** Modify only files listed in `[project].scope`. Make the smallest change that tests the hypothesis. Keep changes focused - one idea per experiment.

3. **Commit.** Short, technical commit message. Public-facing (no internal process narrative).

   ```bash
   git add {changed files}
   git commit -m "{technical description of change}"
   ```

</details>

#### Step 3: Local Gates

<details>
<summary>Step 3: Local Gates</summary>

Run all local validation gates in order. If any fail, attempt to fix. If unfixable, discard.

```bash
# 1. Format check
{build.fmt_command}

# 2. Compile
{build.command}

# 3. Lint
{build.lint_command}

# 4. Tests
{build.test_command}
```

If any gate fails after one fix attempt:
- Log: `{now}\t{id}\t{branch}\t{hypothesis}\t{files}\t{baseline}\t-\t-\tfalse\tgate_fail: {which gate}`
- Discard: `git checkout main && git branch -D {branch}`
- Continue to next experiment

</details>

#### Step 4: Determinism Check

<details>
<summary>Step 4: Determinism Check</summary>

**Only if `constraints.determinism_check = true`.**

This verifies the optimization doesn't change simulation behavior - same seed must produce identical output.

1. Build release locally: `{build.command}`
2. Run with determinism seed: `cargo run --release -- {determinism_seed} {determinism_gens}`
3. Compare output.csv to the baseline output.csv (captured during Phase 0 or a prior run)

If outputs differ:
- Log: `{now}\t{id}\t{branch}\t{hypothesis}\t{files}\t{baseline}\t-\t-\tfalse\tdeterminism_fail`
- Discard branch
- Continue to next experiment

**Note:** The determinism baseline output.csv should be captured once during Phase 0 and stored at `.claude/autooptimize-determinism-baseline.csv`. If it doesn't exist, capture it from main before the first experiment.

</details>

#### Step 5: VPS Benchmark

<details>
<summary>Step 5: VPS Benchmark</summary>

Push to remote and benchmark on VPS. All VPS commands use PowerShell SSH pattern.

1. **Push branch:**
   ```bash
   git push origin {branch}
   ```

2. **SSH to VPS - fetch, checkout, build, benchmark.**
   Construct the SSH command from config values:

   ```
   powershell -NoProfile -ExecutionPolicy Bypass -Command "& 'C:\Windows\System32\OpenSSH\ssh.exe' {benchmark.vps.host_alias} 'cd {benchmark.vps.repo_path} && git fetch origin && git checkout {branch} && RUSTFLAGS=\"{build.vps_rustflags}\" cargo build --release 2>&1 | tail -3 && bash {benchmark.script} {benchmark.benchmark_seed} {benchmark.benchmark_gens} {benchmark.runs_per_experiment} {benchmark.benchmark_args}'"
   ```

   **Timeout:** 180 seconds. If SSH times out:
   - Log: `vps_timeout`
   - Discard branch (local + remote)
   - Continue to next experiment

3. **Parse output.** bench.sh outputs TSV. The last line is `median\t{wall_secs}\t{gens_per_sec}`. Extract the metric value (3rd column of median line).

   If output is unparseable:
   - Log: `parse_fail`
   - Discard branch
   - Continue

4. **Restore VPS to main:**
   ```
   powershell ... ssh {alias} 'cd {repo_path} && git checkout main'
   ```

</details>

#### Step 6: Decide

<details>
<summary>Step 6: Decide</summary>

Compare the experiment metric to the current baseline.

```
delta_pct = (new_metric - baseline) / baseline * 100
```

**If `delta_pct >= constraints.min_improvement_pct` (default 2%):** KEEP

1. Merge to main:
   ```bash
   git checkout main
   git merge {branch}
   git push origin main
   ```
2. Clean up branch:
   ```bash
   git branch -d {branch}
   git push origin --delete {branch}
   ```
3. Update baseline to new metric value
4. Reset consecutive failure counter to 0
5. Log with `kept=true`
6. Report: "Experiment {id}: {hypothesis} - {delta_pct}% improvement. Kept."

**If `delta_pct < constraints.min_improvement_pct`:** DISCARD

1. Clean up:
   ```bash
   git checkout main
   git branch -D {branch}
   git push origin --delete {branch}
   ```
2. Increment consecutive failure counter
3. Log with `kept=false`
4. Report: "Experiment {id}: {hypothesis} - {delta_pct}% (below {min_improvement_pct}% threshold). Discarded."

</details>

#### Step 7: Loop or Stop

Check stopping conditions:
- `experiment_count >= max_experiments` -> stop, report summary
- `consecutive_failures >= constraints.max_consecutive_failures` -> stop with "Diminishing returns - {N} consecutive experiments below threshold."
- Otherwise: go to Step 1 for next experiment

### Phase 2: Summary

<details>
<summary>Phase 2: Summary</summary>

When the loop ends (any stopping condition), report:

1. **Experiment table:**
   ```
   #   | Hypothesis              | Delta  | Kept
   001 | SIMD distance batch     | +8.3%  | yes
   002 | Unroll inner loop       | +0.5%  | no (below 2%)
   003 | Batch brain forward     | -1.2%  | no (regression)
   ```

2. **Cumulative result:** "Started at {initial_baseline} gens/sec, now at {current_baseline} gens/sec ({total_improvement}% total improvement from {kept_count} experiments)."

3. **Remaining opportunities:** If the performance doc has roadmap items not yet tried, list them.

4. **Reminder:** "Update PERFORMANCE.md if significant gains were made."

</details>

## Error Recovery

<details>
<summary>Error Recovery</summary>

| Failure | Recovery |
|---------|----------|
| VPS SSH timeout | Retry once. If still fails, log `vps_timeout`, discard, continue |
| Cargo build fails on VPS | Log `vps_build_fail`, discard. Check if RUSTFLAGS mismatch |
| bench.sh output unparseable | Log `parse_fail`, discard, continue |
| Git merge conflict | Attempt auto-resolve. If fails, discard experiment |
| VPS repo in dirty state | SSH: `git reset --hard origin/main` before checkout |
| Local tests flaky | Re-run once. If still fails, log `gate_fail_flaky`, discard |

</details>

## Quality Self-Check

After each experiment iteration, verify:

1. `autooptimize-experiments.tsv` has a new row for this experiment
2. Git is back on `main` with clean working tree
3. If kept: `main` includes the merged changes, pushed to origin
4. If discarded: branch deleted (local AND remote)
5. Determinism check was actually run (not skipped) if `determinism_check = true`

## Config Reference

<details>
<summary>Config Reference (.claude/autooptimize.toml)</summary>

```toml
[project]
name = "project-name"
scope = ["src/file1.rs", "src/file2.rs"]  # files the optimizer can modify

[build]
command = "cargo build --release"           # local build
vps_rustflags = "-C target-cpu=znver3"      # RUSTFLAGS for VPS build
test_command = "cargo test"                 # test gate
lint_command = "cargo clippy -- -D warnings" # lint gate
fmt_command = "cargo fmt --check"           # format gate

[benchmark]
script = "bench.sh"                         # benchmark script (runs on VPS)
metric_name = "gens_per_sec"                # human-readable metric name
metric_direction = "higher"                 # "higher" or "lower"
runs_per_experiment = 3                     # bench iterations for noise rejection
aggregation = "median"                      # "median" or "mean"
benchmark_gens = 50                         # gens per benchmark run
benchmark_seed = 42                         # seed for benchmark
benchmark_args = "--metrics-interval 10"    # extra args for benchmark

[benchmark.vps]
host_alias = "hetzner"                      # SSH config alias (NOT raw IP)
repo_path = "/root/semiotic-emergence"      # repo path on VPS
binary_path = "target/release/binary-name"  # binary path on VPS

[constraints]
determinism_check = true                    # require identical output for same seed
determinism_seed = 42                       # seed for determinism check
determinism_gens = 10                       # gens for determinism check
min_improvement_pct = 2.0                   # minimum improvement to keep
max_consecutive_failures = 3                # stop after N consecutive discards
max_experiments = 5                         # max experiments per invocation

[context]
performance_doc = "PERFORMANCE.md"          # bottleneck analysis doc
roadmap_section = "## Optimization Roadmap" # section header for roadmap items
experiment_log = "autooptimize-experiments.tsv"  # experiment log file
```

**Generalization notes:**
- `[benchmark.vps]` is optional. If absent, benchmark runs locally.
- `determinism_check` is project-specific. Most projects don't need it.
- `scope` could be directories instead of files for larger projects.
- The core loop (branch -> implement -> gate -> benchmark -> decide) is universal.

</details>

## DO NOT

- Modify the benchmark script (bench.sh) during experiments - it's the evaluator
- Skip the determinism check when `determinism_check = true`
- Hardcode VPS IPs anywhere - use SSH config aliases from the TOML
- Make changes outside of `[project].scope` files
- Combine multiple hypotheses in one experiment - one idea per experiment
- Push to main without the merge workflow (always branch first)
- Continue after `max_experiments` or `max_consecutive_failures`
- Use bash `ssh` instead of PowerShell SSH for VPS commands
