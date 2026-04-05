# SETUP.md - Bootstrap Prompt

Paste this into your AI agent to set up autooptimize.

Two phases. Phase A (steps 1-4) configures the project. Phase B (steps 5-8) runs the first optimization. You can stop after Phase A and come back later.

---

You are setting up autooptimize - a spec engine for autonomous code optimization. Follow each section in order.

## Phase A: Configure

## 1. Locate the autooptimize repo

Ask the user where they cloned the autooptimize repo. If they're running this prompt from inside the cloned repo, use the current directory. You need the path to copy the reference docs.

## 2. Copy Reference Docs

Copy these files from the autooptimize repo into this project's `.claude/reference/` directory:

- `autooptimize-methodology.md` - the core optimization loop
- `spec-format.md` - the executable spec template and executor interface
- `hypothesis-engine.md` - hypothesis generation protocol
- `eval-methodology.md` - eval type taxonomy and assertion primitives
- `evaluator-framings.md` - adversarial framings for LLM evaluators

Create `.claude/reference/` if it doesn't exist.

## 3. Create Config

Read the Config Reference section in `.claude/reference/autooptimize-methodology.md` for the full schema. Create `.claude/autooptimize.toml` with at minimum these sections:

```toml
[project]
name = ""                        # project name
scope = []                       # files the optimizer can modify

[build]
command = ""                     # e.g., "cargo build --release", "npm run build"
test_command = ""                # e.g., "cargo test", "npm test"

[benchmark]
script = ""                      # path to benchmark script
metric_name = ""                 # what to measure
metric_direction = "higher"      # "higher" or "lower"
runs_per_experiment = 7

[constraints]
min_improvement_pct = 2.0
max_consecutive_failures = 5
max_experiments = 5
```

Ask the user:
1. What metric they want to optimize and how to measure it
2. What build/test commands their project uses
3. Which files the optimizer is allowed to modify

## 4. Verify Setup

Confirm:
- [ ] All five `.md` files exist in `.claude/reference/`
- [ ] `.claude/autooptimize.toml` exists with valid config
- [ ] The build command runs successfully
- [ ] The benchmark script runs and outputs the metric

Phase A done. Stop here or continue to Phase B.

## Phase B: First Optimization

## 5. Establish Baseline

Follow Phase 0 (Initialize) from `autooptimize-methodology.md`:
1. Verify clean git state on main/master
2. Build the project
3. Run the benchmark, record the median metric
4. Write the baseline entry to `autooptimize-experiments.jsonl`
5. Report: "Baseline: {metric} {unit}."

## 6. Profile

Follow Phase 0.5 (Profile) from `autooptimize-methodology.md`:
1. Run the profiler (language-specific default or `[profiling].command`)
2. Extract top-5 hotspots
3. Save to `.claude/autooptimize-profile.md`

## 7. Generate First Spec

Now use the hypothesis engine to generate your first optimization spec:

1. Read `.claude/reference/hypothesis-engine.md` - follow the Generation Protocol
2. Since there's no experiment history yet, skip Step 1 (synthesis) and start at Step 2 (check profile)
3. Generate 3-5 candidate hypotheses from the profile data
4. Rank by estimated impact adjusted for tier confidence (see Picking Between Candidates)
5. Take the top-ranked candidate
6. Write a complete optimization spec using the template in `.claude/reference/spec-format.md`
7. Run the completeness checklist

The spec is ready. Execute it yourself or hand it off.

## 8. Execute or Delegate

**Option A: Execute the spec yourself.** Follow the Implementation Guidance, run the Acceptance Criteria, fill in the Result section.

**Option B: Hand the spec to another agent.** Any agent that can read markdown, run shell commands, edit files, and use git can execute it. See the Executor Interface in `spec-format.md`.

After the experiment, write the hypothesis feedback entry (see Learning Loop in `hypothesis-engine.md`), then generate the next spec. Keep going until stopping conditions are met.
