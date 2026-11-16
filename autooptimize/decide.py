"""The scorer: the keep rule. Its source hash goes into the contract."""

import hashlib
import statistics
from dataclasses import asdict, dataclass
from pathlib import Path

from . import stats

SCORER_VERSION = "rank-shift-identity-1"

KEEP, DISCARD, INCONCLUSIVE, FAILED = "KEEP", "DISCARD", "INCONCLUSIVE", "FAILED"


@dataclass(frozen=True)
class KeepRule:
    min_gain: float
    confidence: float
    direction: str  # "lower" or "higher" is better


@dataclass
class Verdict:
    verdict: str
    reason: str
    gain: float = None
    gain_low: float = None
    gain_high: float = None
    detection_limit: float = None
    base_median: float = None
    cand_median: float = None

    def to_dict(self):
        return asdict(self)


def scorer_sha256():
    """Hash of the code that judges trials. A change mid-run breaks the contract."""
    digest = hashlib.sha256()
    here = Path(__file__).parent
    for name in ("decide.py", "stats.py"):
        digest.update((here / name).read_bytes())
    return digest.hexdigest()


def _judge(base, cand, rule):
    for side, runs in (("baseline", base), ("candidate", cand)):
        failed = [r for r in runs if not r.ok]
        if failed or not runs:
            error = failed[0].error if failed else "no runs"
            return Verdict(FAILED, f"{side} run failed: {error}")
    if len({r.outputs for r in base}) != 1:
        return Verdict(FAILED, "baseline outputs vary between identical runs")
    reference = base[0].outputs
    a = [r.metric for r in base]
    b = [r.metric for r in cand]
    base_median, cand_median = statistics.median(a), statistics.median(b)
    if base_median <= 0:
        return Verdict(FAILED, "baseline median is not positive")
    shift, low, high = stats.shift_interval(a, b, rule.confidence)  # base - cand
    if rule.direction == "higher":
        shift, low, high = -shift, -high, -low
    gain, gain_low, gain_high = shift / base_median, low / base_median, high / base_median
    limit = (gain_high - gain_low) / 2.0
    numbers = dict(
        gain=gain, gain_low=gain_low, gain_high=gain_high,
        detection_limit=limit, base_median=base_median, cand_median=cand_median,
    )
    if any(r.outputs != reference for r in cand):
        return Verdict(DISCARD, "outputs differ from the baseline on the test set", **numbers)
    if gain_high < 0:
        return Verdict(DISCARD, "regression beyond the noise", **numbers)
    if gain_low > 0 and gain >= rule.min_gain:
        return Verdict(KEEP, "gain beyond the noise and outputs identical", **numbers)
    if gain_low > 0:
        return Verdict(
            INCONCLUSIVE,
            f"gain is real but below the keep threshold of {rule.min_gain:.1%}",
            **numbers,
        )
    return Verdict(
        INCONCLUSIVE,
        f"difference inside the noise: no effect larger than {limit:.1%} detected",
        **numbers,
    )


def decide(base, cand, rule):
    """Judge a candidate. An error inside the judgement is a failed trial."""
    try:
        return _judge(base, cand, rule)
    except Exception as exc:  # fail closed: an error is never a keep
        return Verdict(FAILED, f"scorer error: {type(exc).__name__}: {exc}")
