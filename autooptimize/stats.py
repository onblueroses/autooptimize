"""Exact rank interval for a shift between two samples. Standard library only.

The estimate is the Hodges-Lehmann shift: the median of all pairwise
differences. The interval comes from the exact Mann-Whitney distribution.
It assumes nothing about the shape of the noise, and one slow outlier run
moves it very little. Timing noise has such outliers.
"""

import math
import statistics
from functools import lru_cache


@lru_cache(maxsize=None)
def u_counts(n, m):
    """Number of orderings of n and m values for each Mann-Whitney U from 0 to n*m."""
    if n == 0 or m == 0:
        return (1,) + (0,) * (n * m)
    counts = [0] * (n * m + 1)
    for u, c in enumerate(u_counts(n - 1, m)):  # the largest value is from the first sample
        counts[u + m] += c
    for u, c in enumerate(u_counts(n, m - 1)):  # the largest value is from the second sample
        counts[u] += c
    return tuple(counts)


def interval_rank(n, m, confidence):
    """1-based rank k of the interval [d(k), d(n*m+1-k)]. 0 when no interval reaches the confidence."""
    counts = u_counts(n, m)
    total = math.comb(n + m, n)
    tail = (1.0 - confidence) / 2.0
    cumulative, k = 0, 0
    for u, c in enumerate(counts):
        cumulative += c
        if cumulative / total > tail:
            break
        k = u + 1
    return k


def min_runs(confidence):
    """Smallest equal number of runs per side for which an interval exists."""
    n = 1
    while interval_rank(n, n, confidence) == 0:
        n += 1
    return n


def shift_interval(a, b, confidence):
    """Return (estimate, low, high) for the shift a - b. Bounds are infinite when n is too small."""
    if not a or not b:
        raise ValueError("each side needs at least one value")
    diffs = sorted(x - y for x in a for y in b)
    estimate = statistics.median(diffs)
    k = interval_rank(len(a), len(b), confidence)
    if k == 0:
        return estimate, -math.inf, math.inf
    return estimate, diffs[k - 1], diffs[len(diffs) - k]
