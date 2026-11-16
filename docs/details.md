# autooptimize in detail

This page describes the config, the benchmark protocol, the statistics, the controls, the ledger
and the limits of the method. The [README](../README.md) gives the overview.

## Config

The config is one JSON file in the project, by default `autooptimize.json`. The demo config is in
[`autooptimize/demo/project/autooptimize.json`](../autooptimize/demo/project/autooptimize.json).
The values and sources below are examples. Write your own sources.

```json
{
  "target": "target.py",
  "benchmark": {
    "command": ["{python}", "bench.py"],
    "frozen": ["bench.py", "inputs.json"],
    "timeout_s": {"value": 120, "source": "measured: the slowest of 20 baseline runs took 41 s"}
  },
  "direction": "lower",
  "keep_rule": {
    "min_gain": {"value": 0.05, "source": "ruling: a gain under 5% is not worth a commit here"},
    "confidence": {"value": 0.95, "source": "ruling: a two-sided 95% interval"},
    "runs_per_side": {"value": 10, "source": "measured: 10 runs gave a detection limit of 2%"}
  },
  "proposer": {
    "timeout_s": {"value": 600, "source": "measured: ..."}
  },
  "arms": ["algorithm", "data structure", "caching"]
}
```

| Key | Meaning |
|---|---|
| `target` | The one file that the proposer may change. It cannot be a frozen file. |
| `benchmark.command` | The command, as a list. `{python}` becomes the running Python interpreter. It runs in the worktree root. |
| `benchmark.frozen` | The benchmark files and the test inputs. The contract hashes them. |
| `benchmark.timeout_s` | Optional. A run that takes longer is a failed run. |
| `direction` | `lower` or `higher`: the better direction of the metric. |
| `keep_rule.min_gain` | The smallest relative gain that the loop keeps. |
| `keep_rule.confidence` | The confidence of the interval. |
| `keep_rule.runs_per_side` | Benchmark runs for each side of each comparison. |
| `proposer.timeout_s` | Optional. A `claude` call that takes longer is a failed trial. |
| `arms` | Optional. The directions of change to try. The prompt names them. A null report lists the untried ones. |

Every number is an object with `value` and `source`. The source starts with `measured:`,
`system:` or `ruling:` and then says where the value comes from. The loader refuses a bare number.
The optional limits have no defaults. Without `timeout_s`, the loop waits for the benchmark to
end. [LIMITS.md](../LIMITS.md) gives the reason.

## Benchmark protocol

The benchmark is a command that exits with status 0. Its last non-empty line on stdout is one JSON
object:

```json
{"metric": 0.0471, "outputs": "e48b944f7c21fa7b..."}
```

- `metric` is a finite number. Use CPU time or a count when you can. Wall time on a shared machine
  is noisy.
- `outputs` is a digest of every output on the frozen test set. The identity check compares it.

Everything else is a failed run. Examples are a nonzero status, a signal, a timeout and no output.
A line that is not JSON, a bad metric and a missing digest are failed runs too. A failed run never becomes a pass.
The loop sets `PYTHONDONTWRITEBYTECODE=1`, so a stale bytecode file cannot hide a change.

## A run, step by step

1. **Static preflight.** The loop refuses a project that is not a git repository and a dirty tree.
   It also refuses an uncommitted target or frozen file and a missing benchmark program.
2. **Contract.** The loop writes `contract.json`. It holds the hashes of the config, the frozen
   files and the scorer code (`decide.py` and `stats.py`). It also holds the keep rule and the
   baseline commit. Each ledger
   record carries the contract hash.
3. **Worktrees.** The loop adds two git worktrees under the run folder: `best` on the branch
   `autooptimize/<run-id>` and a detached `cand`. Your checkout stays as it is.
4. **Noise preflight.** The loop runs the baseline `2 × runs_per_side` times in two interleaved sets,
   A and B. It refuses when a run fails, when the outputs vary, or when the detection limit of A
   against B is above `min_gain`. The refusal estimates the number of runs that would be enough.
5. **Controls.** The loop judges known cases built from A and B (see below). It refuses when one
   verdict is wrong.
6. **Trials.** Each trial verifies the contract and asks the proposer. It checks that the proposer
   did not change the project. Then it writes the candidate into `cand`, measures `best` and `cand`
   in turn and decides. A KEEP copies the candidate into `best` and commits it.
7. **End.** The loop writes the report and a manifest with the hash of every artifact. It checks the
   manifest, writes `DONE` and then removes the two worktrees. The branch keeps the commits.

A refusal at any step writes a `refusal` record and exits with status 2. It deletes nothing. The
worktrees and the artifacts stay for inspection.

## The keep rule

For one comparison the loop has `n` baseline metrics and `n` candidate metrics.

- The estimate is the Hodges-Lehmann shift: the median of all `n × n` differences.
- The interval comes from the exact Mann-Whitney distribution of the ranks. It assumes no shape for
  the noise. One slow outlier run moves it very little, and timing noise has such outliers.
- Gains are relative to the baseline median. For `direction: lower`, a gain of 20% means the
  candidate takes 20% less.
- The detection limit is the half width of the interval.

The verdicts, in order:

| Verdict | Condition |
|---|---|
| FAILED | A run failed, the baseline outputs vary, or the scorer raised an error. |
| DISCARD | The candidate outputs differ from the baseline, or the whole interval is below zero. |
| KEEP | The whole interval is above zero and the estimate is at or above `min_gain`. |
| INCONCLUSIVE | All other cases. The reason states the detection limit, or that the gain is real but below the threshold. |

With few runs no interval reaches the confidence. The exact test needs at least 4 runs per side
for 95% and 5 for 99%. The preflight refuses such a config and names the minimum.

## Controls

The loop measures the unchanged baseline twice (sets A and B). Then the scorer judges five cases:

| Control | Case | Expected |
|---|---|---|
| null | A against B | INCONCLUSIVE |
| improvement | B moved better by the shift | KEEP |
| regression | B moved worse by the shift | DISCARD |
| changed_output | B with a different outputs digest | DISCARD |
| failed_run | B with one failed run | FAILED |

The shift is `min_gain` plus the full width of the null interval. The loop adds it as a constant,
so the noise of B stays as it was measured. With this shift a correct scorer fires both known-effect
controls whenever the null holds. A blind scorer, a scorer with the sign wrong and a scorer without
the identity check miss them. The tests show each case.

The controls test the judgement against real noise. They do not test that a proposer's change
reaches the benchmark. The end-to-end tests check that coupling with a project whose metric
depends on the target file.

The null control can fail by chance. At 95% confidence this happens in at most 1 run of 20, and
at 99% in at most 1 run of 100. This is a bound from the confidence, not a measurement. A failed null stops the
run. Start it again, or use a higher confidence.

## The ledger and the run folder

Each run has a folder `.autooptimize/runs/<run-id>/` in the project. The loop adds
`/.autooptimize/` to `.git/info/exclude`, so the folder does not make the tree dirty.

```text
contract.json    the frozen contract and its hash
ledger.jsonl     one record per step
preflight/       raw baseline runs a-1.json ... b-N.json
trial-NNN/       proposal.json, the candidate file, diff.patch, runs/base-K.json and cand-K.json
report.md        the report
manifest.json    sha256 of every artifact
DONE             the loop writes this after it verifies the manifest
```

Record kinds in `ledger.jsonl`: `start`, `preflight`, `control`, `trial`, `refusal` and `end`.
Each record has `ts`, `run`, `contract` and `kind`. A trial record has the verdict, the reason,
the gain, the interval, the detection limit, the medians, the arm and the commit of a KEEP. The
loop fsyncs each record before it continues.

`autooptimize report <ledger>` rebuilds the report. It refuses a ledger with two contract hashes.

## The report

Each number in the report has a kind:

| Kind | Example |
|---|---|
| measured | the gain of a trial, with its ledger line |
| estimate | the total gain over the run, which multiplies the kept gains |
| required | the keep threshold from the config, with its source |
| unknown | the gain on inputs outside the frozen test set |

A run without a KEEP is a null. Its report must state the detection limit, the controls that
fired, the untried arms and the next route. The renderer refuses to print the null when one field
is empty.

## The Claude Code proposer

The loop calls `claude -p --tools "" --output-format text` and sends the prompt on stdin. With no
tools the model cannot edit files or run commands. The loop writes the file. The prompt contains the
current file, the arms and every past trial with its verdict, gain and reason. It asks for a change
of algorithm or data structure before micro-optimizations. It asks the model not to repeat an
idea that received DISCARD or FAILED.

The answer must have an `ARM:` line, an optional `WHY:` line and exactly one fenced code block. Any
other answer is a failed trial, and the loop continues with the next trial. Use `--model` to choose
the model. `--iterations` is required, because the loop sets no default number of trials.

## Exit status

| Status | Meaning |
|---|---|
| 0 | The run ended normally, or the command succeeded. |
| 2 | Any refusal, crash, interrupt or bad argument. |

The loop decides the status before it writes optional output. If the loop cannot write the
refusal record or message, the status stays 2.

## What it does not do

- It changes one file. A change that needs several files is out of scope.
- It checks identity only on the frozen test set. Behaviour on other inputs is unknown.
- It does not profile. The proposer sees the code and the history, not a profile.
- It does not judge code quality. A KEEP means faster and identical on the test set.
- It runs trials one after another. Parallel trials on one machine would add noise to each other.

## Changes from version 2

Version 2 was a set of method documents for a coding agent. It had a hypothesis engine, a spec
format and eval scripts. Version 3 replaces them with code that enforces the rules. Two ideas
survived. The proposer prompt puts algorithms before micro-optimizations and learns from past
verdicts. The keep rule judges a difference against measured noise. The old documents are in the git
history before version 3.
