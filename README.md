# autooptimize

autooptimize is a loop that makes code faster with Claude Code. It measures the code, asks for one
change, measures again and then keeps or discards the change. The loop can say no. It refuses to
start when it cannot see the effects that it must judge.

## What it does

You give it one target file, a benchmark and a keep threshold. The loop then repeats four steps:

1. The `claude` CLI proposes a new version of the target file. Its tools are off, so it can only
   answer with text.
2. The loop runs the benchmark on the current best version and on the candidate. The runs
   alternate, so drift on the machine hits both sides equally.
3. The keep rule gives one verdict: KEEP, DISCARD, INCONCLUSIVE or FAILED.
4. The loop writes the verdict to a ledger. A KEEP becomes a commit on a run branch.

Your own checkout does not change. The kept commits are on the branch `autooptimize/<run-id>`.

## The loop

```text
config -> freeze contract -> preflight -> controls
                                              |
    +-----------------------------------------+
    v
 propose -> verify contract -> measure best and candidate -> decide -> ledger
    ^                                                          |
    +------------- past verdicts, gains and reasons -----------+
                                                               |
                                    KEEP: commit on the run branch
```

## The rules

| Rule | What the loop does | Why it exists |
|---|---|---|
| Frozen contract | Before the first run, the loop hashes the benchmark files, the test inputs, the config and the scorer code. It refuses when one of them changes during the run. | A rule that changes after the results arrive measures the results. Numbers under two contracts are not comparable. |
| Preflight | The loop refuses a dirty tree, a missing benchmark and a benchmark that is too noisy for the keep threshold. | A noisy benchmark cannot see the gain that it must judge. The refusal comes before any proposer call. |
| Controls | Before real trials, the loop judges five known cases built from real baseline runs. It refuses when one verdict is wrong. | The loop must detect known effects before a pass or a null provides useful evidence. |
| Keep rule | KEEP needs a gain outside the noise interval, a gain at or above the threshold, and outputs identical to the baseline on the test set. | A faster change with different outputs is a bug. A gain inside the noise is luck. |
| Nulls state their limit | An INCONCLUSIVE verdict states the smallest effect that the trial could detect. A run without a KEEP must state its detection limit, controls, untried arms and next route. | "No effect" without a detection limit is a guess. Further tests may be necessary after a null result. |
| Every number has a kind | The report labels each number `measured`, `estimate`, `required` or `unknown`. Measured numbers point to their ledger line. | A measurement and an estimate look the same in a table. |
| Fail closed | A crash, a timeout, a bad output line or an error in the scorer is a failed trial. Every abnormal end of the program is exit status 2. | A failure that reads as a pass keeps a broken change. |
| No unmeasured limits | The config loader refuses a number without a source. [LIMITS.md](LIMITS.md) lists every limit with its source. A test checks the table. | A cap with no source fails later, for someone else, and looks like safety until then. |
| Durable record | Every step appends to a JSONL ledger and calls fsync. Trial artifacts stay when a later check fails. | A result that exists only in a terminal is lost. Evidence of a failed run is the most useful evidence. |

## The demo

The demo needs Python 3.10 or newer and git. It needs no API key, because a scripted proposer
replays five prepared changes to a slow prime counter.

```bash
git clone https://github.com/onblueroses/autooptimize.git
cd autooptimize
python3 -m autooptimize demo
```

Output of one run (shortened):

```text
preflight: baseline 0.0467, detection limit 2.7%, keep threshold 20.0%
controls (shift 25.4%): null=fired, improvement=fired, regression=fired, changed_output=fired, failed_run=fired
trial 1 [tidy]: INCONCLUSIVE gain +1.2% (limit 11.4%): difference inside the noise: no effect larger than 11.4% detected
trial 2 [algorithm]: DISCARD gain +99.0% (limit 21.6%): outputs differ from the baseline on the test set
trial 3 [algorithm]: KEEP gain +98.9% (limit 11.7%): gain beyond the noise and outputs identical
trial 4 [data structure]: DISCARD gain -1817.5% (limit 670.4%): regression beyond the noise
trial 5 [caching]: FAILED: candidate run failed: exit status 1
```

Trial 1 only renames variables, so the loop sees no effect. Trial 2 is 99% faster but counts 1 as a
prime, so the identity check discards it. Trial 3 is a correct sieve and becomes a commit. Trial 4
is correct but slower than the kept sieve. Trial 5 crashes. The run prints a full report and keeps all
artifacts under `.autooptimize/runs/` in the demo folder.

The verdicts come from real timings. On a busy machine the preflight can refuse the run as too
noisy. That refusal is the loop working as designed.

## Use it on your project

```bash
pip install .
cd your-project
autooptimize check-config autooptimize.json
autooptimize run --iterations 5
```

The run needs a clean git tree, a logged-in `claude` CLI and a config file. The benchmark prints
one JSON line with a metric and a digest of the outputs. [docs/details.md](docs/details.md) describes
the config, the benchmark protocol, the statistics and the ledger.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

The tests use a scripted proposer and a fake `claude` CLI, so they need no key. One live test calls
the real CLI. It runs only when `AUTOOPTIMIZE_LIVE_CLAUDE=1` is set. A green offline run is not a
green live run.

## Layout

```text
autooptimize/          the loop
  contract.py          freeze and verify the contract
  preflight.py         refusal checks before any trial
  controls.py          known cases that the scorer must judge correctly
  decide.py            the keep rule (the scorer)
  stats.py             exact rank interval for a shift
  bench.py             benchmark runner that fails closed
  ledger.py            append-only JSONL ledger
  report.py            report with number kinds and null fields
  proposers.py         claude CLI proposer and scripted proposer
  loop.py, cli.py      the run and the command line
  demo/                demo project and scripted proposals
tests/                 one test file per rule
docs/details.md        config, protocol, statistics, ledger
LIMITS.md              every limit and its source
```

## License

[MIT](LICENSE). The change history is in [CHANGELOG.md](CHANGELOG.md).
