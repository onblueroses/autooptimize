# SETUP.md - Bootstrap Prompt

Paste this into your AI agent to set up autonomous optimization for your project.

---

You are configuring the autooptimize loop for this project. Follow each section in order.

## 1. Locate the autooptimize repo

Ask the user where they cloned the autooptimize repo. If they're running this prompt from inside the cloned repo, use the current directory. You need the path to copy the methodology docs.

## 2. Copy Reference Docs

Copy these files from the autooptimize repo into this project's `.claude/reference/` directory:

- `autooptimize-methodology.md` - the optimization loop procedure
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
- [ ] All three `.md` files exist in `.claude/reference/`
- [ ] `.claude/autooptimize.toml` exists with valid config matching the methodology's schema
- [ ] The build command runs successfully
- [ ] The benchmark script runs and outputs the metric

## 5. First Run

Read `.claude/reference/autooptimize-methodology.md` and follow the optimization loop from the beginning. Start with a baseline measurement.
