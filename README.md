# autooptimize

Autonomous optimization and evaluation for AI coding agents. Inspired by Karpathy's [autoresearch](https://github.com/karpathy/autoresearch).

I wanted a way to improve Claude Code's performance on my projects without manually tweaking prompts. autooptimize is the loop I built: measure a metric, hypothesize an improvement, implement it on a branch, benchmark, keep or discard. The eval toolkit grew out of needing to actually measure whether changes helped.

There's no code to install. You clone the repo, paste SETUP.md into your agent, and it configures itself for your project.

## Quick Nav

| I want to... | Go to |
|--------------|-------|
| Set up autooptimize on my project | [Quick Start](#quick-start) |
| Understand the optimization loop | [`autooptimize-methodology.md`](autooptimize-methodology.md) |
| Write evals for my agent | [`eval-methodology.md`](eval-methodology.md) |
| Use adversarial evaluator framings | [`evaluator-framings.md`](evaluator-framings.md) |
| Run the eval scripts | [Scripts](#scripts-optional) |

## Quick Start

```bash
git clone https://github.com/onblueroses/autooptimize.git
```

Open your AI agent. Paste the contents of [`SETUP.md`](SETUP.md).

The agent copies the methodology docs into your project, creates a config, and starts the optimization loop. No build step.

## What's Inside

```
autooptimize-methodology.md    Core optimization loop: profiling, A/B benchmarking, hypothesis strategy
eval-methodology.md            Eval type taxonomy, assertion primitives, fixture formats
evaluator-framings.md          7 adversarial framings for LLM evaluators
SETUP.md                       Bootstrap prompt - paste this into your agent
scripts/                       Python tools for running evals and aggregating benchmarks (optional)
tests/                         Regression tests for the scripts
```

## Optimization Loop

One metric, one loop, git-based rollback. For each experiment:

1. Establish baseline measurement
2. Generate hypothesis from performance docs + past results
3. Create isolated branch, implement change
4. Run local gates (compile, lint, test, determinism)
5. Benchmark against baseline
6. Keep if improvement exceeds threshold (default 2%), discard otherwise
7. Log result, repeat

Stops after max experiments (default 5) or N consecutive failures.

## Evaluation Toolkit

<details>
<summary>Eval types (cheapest to most expensive)</summary>

| Type | What it checks | Cost |
|------|---------------|------|
| **Trigger** | Did the right skill/tool fire? | Free (subprocess) |
| **Behavioral** | Does output contain/not-contain specific content? | Free (string ops) |
| **Benchmark** | Does a stochastic metric land in acceptable bands? | Low (N runs) |
| **Semantic** | Does an LLM judge pass the output against criteria? | High (LLM call) |
| **Regression** | Does output match a known-good baseline? | Medium (diff) |

</details>

<details>
<summary>Evaluator framings</summary>

Adversarial preambles that shift an LLM evaluator's perspective. Each counters a specific class of systematic bias:

| Framing | Assumes |
|---------|---------|
| **security-audit** | Every input is attacker-controlled |
| **production-load** | 1000 concurrent requests |
| **maintainability** | Original author is unreachable |
| **adversarial-user** | Users do everything wrong |
| **specification-lawyer** | Reads criteria with zero charity |
| **dependency-skeptic** | Every external call will fail |
| **reality-declaration** | This is a real deployment, not an exercise |

</details>

## Scripts (Optional)

Python tools for running evals programmatically. You don't need these - the methodology docs work on their own. The scripts help if you want to automate eval runs at scale.

<details>
<summary>Available scripts</summary>

**Trigger eval runner** - tests whether a skill description causes Claude Code to invoke it:

```
python -m scripts.run_eval \
  --eval-set path/to/eval-set.json \
  --skill-path path/to/skill/ \
  --runs-per-query 3 \
  --num-workers 10
```

**Benchmark aggregator** - rolls up multiple eval runs into summary statistics:

```
python -m scripts.aggregate_benchmark benchmarks/2026-01-15T10-30-00/
```

Requires Python 3.10+.

</details>

## Works With

Claude Code (primary), or any AI coding agent that reads markdown.

## License

MIT
