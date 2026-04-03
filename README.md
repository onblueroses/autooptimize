# autooptimize

Autonomous optimization and evaluation toolkit for [Claude Code](https://docs.anthropic.com/en/docs/claude-code). Inspired by Karpathy's [autoresearch](https://github.com/karpathy/autoresearch).

Two components:
1. **Optimization loop** - one metric, one loop, git-based rollback. Hypothesize, implement, benchmark, keep or discard, repeat.
2. **Evaluation toolkit** - eval type taxonomy, assertion primitives, adversarial evaluator framings, and scripts for measuring AI agent behavior.

## Contents

| File | What it covers |
|------|---------------|
| `autooptimize-methodology.md` | Core optimization loop: profiling, A/B benchmarking, hypothesis strategy, decision logic |
| `eval-methodology.md` | Eval type taxonomy (trigger, behavioral, benchmark, semantic, regression), assertion primitives, fixture formats, dataset design |
| `evaluator-framings.md` | 7 adversarial framings for LLM evaluators: security-audit, production-load, maintainability, adversarial-user, specification-lawyer, dependency-skeptic, reality-declaration |
| `scripts/` | Python tools for running trigger evals and aggregating benchmark results |

## Optimization Loop

1. Read per-project config from `.claude/autooptimize.toml`
2. Establish a baseline measurement
3. For each experiment (default 5):
   - Generate optimization hypothesis from performance docs + past results
   - Create isolated branch, implement change
   - Run local gates (compile, lint, test, determinism)
   - Benchmark on a remote server or locally
   - Keep if improvement exceeds threshold (default 2%), discard otherwise
   - Log result to experiment log
4. Stop after max experiments or N consecutive failures

## Evaluation Toolkit

### Eval types (cheapest to most expensive)

| Type | What it checks | Cost |
|------|---------------|------|
| **Trigger** | Did the right skill/tool fire? | Free (subprocess) |
| **Behavioral** | Does output contain/not-contain specific content? | Free (string ops) |
| **Benchmark** | Does a stochastic metric land in acceptable bands? | Low (N runs) |
| **Semantic** | Does an LLM judge pass the output against criteria? | High (LLM call) |
| **Regression** | Does output match a known-good baseline? | Medium (diff) |

### Evaluator framings

Adversarial preambles that shift an LLM evaluator's perspective. Each counters a specific class of systematic bias:

- **security-audit** - assumes every input is attacker-controlled
- **production-load** - assumes 1000 concurrent requests
- **maintainability** - assumes original author is unreachable
- **adversarial-user** - assumes users do everything wrong
- **specification-lawyer** - reads criteria with zero charity
- **dependency-skeptic** - assumes every external call will fail
- **reality-declaration** - treats the review as a real deployment, not an exercise

### Scripts

**Trigger eval runner** - tests whether a skill description causes Claude Code to invoke it:

```
python -m scripts.run_eval \
  --eval-set path/to/eval-set.json \
  --skill-path path/to/skill/ \
  --runs-per-query 3 \
  --num-workers 10
```

**Benchmark aggregator** - rolls up multiple eval runs into summary statistics with delta:

```
python -m scripts.aggregate_benchmark benchmarks/2026-01-15T10-30-00/
```

## Setup

**For the optimization loop:** Copy `autooptimize-methodology.md` into your project's `.claude/reference/` directory and create `.claude/autooptimize.toml`. See the Config Reference section in the methodology doc.

**For evals:** Copy `eval-methodology.md` and `evaluator-framings.md` into `.claude/reference/`. Use the scripts directly or adapt them to your eval pipeline.

## Requirements

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI
- Python 3.10+ (for scripts)
- Git (experiments use branch isolation)

## License

MIT
