# autooptimize

autooptimize is a set of markdown documents for autonomous code optimization with a coding agent.
It decides what to try next and whether it worked. The agent does the work.

## What it does

A coding agent can write code. It is less good at two decisions: what to try, and whether the
change helped. autooptimize writes an optimization spec for each experiment. A spec is one
markdown file with a hypothesis, implementation steps, acceptance criteria and an evaluation
protocol. Any agent that can read markdown, run shell commands, edit files and use git can execute
it.

The results go back into the next hypothesis, so each experiment uses what the earlier ones found.
The idea comes from Karpathy's [autoresearch](https://github.com/karpathy/autoresearch).

## The loop

```text
Initialize -> Profile -> [Hypothesize -> Implement -> Gate -> Benchmark -> Decide -> Log] -> Summary
                ^                                                                    |
                |________ re-profile after 2+ kept experiments _____________________|
```

Each experiment ends in one of three outcomes:

- **KEEP**: the metric improves by at least `min_improvement_pct` and the signal-to-noise ratio is
  at least 2.0.
- **INCONCLUSIVE**: the change is inside the noise. It does not count as a failure.
- **DISCARD**: a measurable regression. It counts as a failure.

## The documents

| File | Contents |
|---|---|
| [`SETUP.md`](SETUP.md) | Bootstrap prompt to paste into your agent |
| [`autooptimize-methodology.md`](autooptimize-methodology.md) | The core loop, logging, A/B benchmarks, decision logic, profiling, config reference |
| [`hypothesis-engine.md`](hypothesis-engine.md) | How to make and rank hypotheses: tiers T0 to T4, parallel search mode, learning loop |
| [`spec-format.md`](spec-format.md) | Spec template, completeness checklist, antipatterns, executor interface |
| [`eval-methodology.md`](eval-methodology.md) | Eval types, assertion primitives, fixture formats, statistical methods such as SPRT |
| [`evaluator-framings.md`](evaluator-framings.md) | 7 adversarial framings for LLM evaluators |

## How to use it

There is no code to install for the method itself.

1. Clone the repo:

   ```bash
   git clone https://github.com/onblueroses/autooptimize.git
   ```

2. Open your coding agent in your project and paste the contents of [`SETUP.md`](SETUP.md).
3. The agent copies the five reference documents into `.claude/reference/` in your project.
4. The agent asks for your metric, your build and test commands, and the files it can change. Then
   it writes `.claude/autooptimize.toml`.
5. Optionally, the agent measures a baseline, profiles the code and writes the first spec.

## Optional scripts

The `scripts/` directory has two Python tools for eval runs. You need Python 3.10 or newer.

```bash
# Test if a skill description makes Claude Code use the skill. Needs the `claude` CLI on PATH.
python -m scripts.run_eval --eval-set path/to/eval-set.json --skill-path path/to/skill/

# Make summary statistics from many runs of grading.json files.
python -m scripts.aggregate_benchmark benchmarks/2026-01-15T10-30-00/

# Run the tests.
python -m unittest discover -s tests -v
```

## Layout

```text
*.md         the method: setup prompt and five reference documents
scripts/     optional eval runner and benchmark aggregator
tests/       tests for the scripts
```

## License

[MIT](LICENSE). Change history is in [CHANGELOG.md](CHANGELOG.md).
