# autooptimize

Spec engine for autonomous code optimization. Inspired by Karpathy's [autoresearch](https://github.com/karpathy/autoresearch).

Coding agents can write code. What they can't do well is decide *what* to try and *whether it worked*. autooptimize generates optimization specs - markdown documents that encode a hypothesis, implementation steps, acceptance criteria, and evaluation protocol. Hand a spec to any coding agent and it runs the full experiment without reading anything else.

Profile the codebase, generate a hypothesis from experiment history, write a spec, delegate it, evaluate the result, feed it back. Each iteration is better informed than the last because the learning loop calibrates predictions against observed outcomes.

No code to install. Clone the repo, paste SETUP.md into your agent, and it configures itself.

## Quick Nav

| I want to... | Go to |
|--------------|-------|
| Set up autooptimize on my project | [Quick Start](#quick-start) |
| See the executable spec format | [`spec-format.md`](spec-format.md) |
| Understand the optimization loop | [`autooptimize-methodology.md`](autooptimize-methodology.md) |
| Generate better hypotheses | [`hypothesis-engine.md`](hypothesis-engine.md) |
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
spec-format.md                 Executable spec template, executor interface, completeness checklist
hypothesis-engine.md           Hypothesis generation protocol with tier system and quality rubric
autooptimize-methodology.md    Core optimization loop: profiling, A/B benchmarking, decision logic
eval-methodology.md            Eval type taxonomy, assertion primitives, fixture formats, SPRT
evaluator-framings.md          7 adversarial framings for LLM evaluators
SETUP.md                       Bootstrap prompt - paste this into your agent
scripts/                       Python tools for running evals and aggregating benchmarks (optional)
tests/                         Regression tests for the scripts
```

## How It Works

autooptimize decides what to try. The coding agent does the work.

1. **Profile** the codebase to find bottlenecks
2. **Generate hypothesis** from experiment history, ranked by estimated impact
3. **Write a spec** - one markdown file with everything the executor needs
4. **Delegate** to any coding agent (or run it yourself)
5. **Evaluate** - cheap gates first (compile, lint, test), then benchmark with SPRT early stopping
6. **Learn** - results calibrate the next hypothesis
7. **Repeat** until stopping conditions are met

See [`spec-format.md`](spec-format.md) for the format and a complete example.

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
