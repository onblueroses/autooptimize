"""Controls: prove the rig can see a known effect before it judges real changes.

The loop measures the unchanged baseline twice (sides A and B). Then it judges
known cases built from those real runs:

- null: A against B. Same code, so the verdict must be INCONCLUSIVE.
- improvement: B moved better by `shift`. The verdict must be KEEP.
- regression: B moved worse by `shift`. The verdict must be DISCARD.
- changed_output: B with a different outputs digest. The verdict must be DISCARD.
- failed_run: B with one failed run. The verdict must be FAILED.

The shift is the keep threshold plus the full width of the null interval of
these same runs (two detection limits). With this shift a correct scorer
fires both known-effect controls whenever the null control holds. A blind
scorer, a scorer with the sign wrong or a scorer without the identity check
misses them. The shift is added to real, noisy runs, so the controls test the
judgement against real noise. They do not test that the proposer's change
reaches the benchmark. The end-to-end tests cover that coupling.
"""

import math
import statistics
from dataclasses import replace

from .decide import DISCARD, FAILED, INCONCLUSIVE, KEEP, decide

EXPECTED = {
    "null": INCONCLUSIVE,
    "improvement": KEEP,
    "regression": DISCARD,
    "changed_output": DISCARD,
    "failed_run": FAILED,
}


def _moved(runs, delta):
    return [replace(r, metric=r.metric + delta) for r in runs]


def build_cases(a, b, shift, direction):
    # Move B by a constant. A constant keeps the noise of B as it was measured.
    step = shift * statistics.median(r.metric for r in a)
    better, worse = (-step, step) if direction == "lower" else (step, -step)
    changed = [replace(r, outputs="control-changed:" + r.outputs) for r in b]
    failed = [replace(b[0], ok=False, metric=None, error="injected failure")] + list(b[1:])
    return {
        "null": (a, b),
        "improvement": (a, _moved(b, better)),
        "regression": (a, _moved(b, worse)),
        "changed_output": (a, changed),
        "failed_run": (a, failed),
    }


def control_shift(a, b, rule):
    """Keep threshold plus the width of the null interval of A against B."""
    null = decide(a, b, rule)
    if null.gain_low is None or not math.isfinite(null.gain_high - null.gain_low):
        return rule.min_gain
    return rule.min_gain + (null.gain_high - null.gain_low)


def run_controls(a, b, rule, shift=None, decide_fn=decide):
    """Return one result per control. `fired` is True when the verdict matches."""
    shift = control_shift(a, b, rule) if shift is None else shift
    results = []
    for name, (base, cand) in build_cases(a, b, shift, rule.direction).items():
        verdict = decide_fn(base, cand, rule)
        results.append(
            {
                "control": name,
                "expected": EXPECTED[name],
                "got": verdict.verdict,
                "fired": verdict.verdict == EXPECTED[name],
                "shift": shift,
                "verdict": verdict.to_dict(),
            }
        )
    return results
