# Limits

Every cap, threshold, timeout or stop condition in autooptimize is in this table with its source.
A number with no source is not installed. `tests/test_limits.py` fails when a config number or a
numeric code constant has no row here.

Source kinds: **measured** (a measurement), **system** (the limit of the system itself) and
**ruling** (a decision by the operator, with its reason). The config loader refuses a number
without one of these sources.

## Config values

The config has no defaults for these values. The operator sets each one with its source.

| Name | Required | Kind of source | What it does |
|---|---|---|---|
| `keep_rule.min_gain` | yes | ruling | The smallest relative gain worth a commit. The preflight refuses a benchmark that cannot detect it. |
| `keep_rule.confidence` | yes | ruling | Two-sided confidence of the interval for the difference of means. |
| `keep_rule.runs_per_side` | yes | measured or ruling | Benchmark runs per side for each comparison. It must pass the preflight noise check. |
| `benchmark.timeout_s` | no | measured | A benchmark run that takes longer is a failed run. Absent means no timeout. |
| `proposer.timeout_s` | no | measured | A proposer call that takes longer is a failed trial. Absent means no timeout. |
| `--iterations` | for `--proposer claude` | ruling | The number of trials. The operator gives it on the command line. The scripted proposer stops when its files end. |

The demo config sets `min_gain` to 20%, `confidence` to 0.99 and `runs_per_side` to 10. Each
value carries its source in the file. The run count is measured: in 15 demo runs on a shared
cloud VM, 14 passed the preflight and 1 refused as too noisy.

## Code constants

| Name | Value | Kind of source | Source |
|---|---|---|---|
| `MIN_RUNS_PER_SIDE` | 3 | ruling | Three runs per side are the floor for judging a difference against its uncertainty. |
| `REFUSED` | 2 | system | Exit status of every end that is not a normal end. |

## Not installed

These limits are absent because nothing measured them:

- No default timeout for the benchmark or the proposer.
- No default number of trials.
- No cap on consecutive failures. Each failed trial is in the ledger. The operator stops the run.
