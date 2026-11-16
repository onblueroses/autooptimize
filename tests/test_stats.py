import math
import unittest

import helpers  # noqa: F401
from autooptimize import stats


class MannWhitney(unittest.TestCase):
    def test_counts_sum_to_all_orderings(self):
        for n, m in ((1, 1), (3, 4), (7, 7)):
            self.assertEqual(sum(stats.u_counts(n, m)), math.comb(n + m, n))

    def test_interval_ranks_match_published_critical_values(self):
        # Two-sided 5% critical U for equal sides: 5 -> 2, 7 -> 8, 10 -> 23. The rank is U + 1.
        for n, critical in ((5, 2), (7, 8), (10, 23)):
            self.assertEqual(stats.interval_rank(n, n, 0.95), critical + 1, msg=f"n={n}")
        # Two-sided 1% critical U: 7 -> 4, 10 -> 16.
        for n, critical in ((7, 4), (10, 16)):
            self.assertEqual(stats.interval_rank(n, n, 0.99), critical + 1, msg=f"n={n}")

    def test_too_few_runs_give_no_interval(self):
        self.assertEqual(stats.interval_rank(3, 3, 0.95), 0)
        self.assertEqual(stats.min_runs(0.95), 4)
        self.assertEqual(stats.min_runs(0.99), 5)
        _, low, high = stats.shift_interval([1, 2, 3], [1, 2, 3], 0.95)
        self.assertEqual((low, high), (-math.inf, math.inf))


class ShiftInterval(unittest.TestCase):
    def test_same_samples_contain_zero(self):
        _, low, high = stats.shift_interval([1.0, 1.1, 0.9, 1.05, 1.0], [1.02, 0.95, 1.08, 0.97, 1.0], 0.95)
        self.assertLess(low, 0)
        self.assertGreater(high, 0)

    def test_shifted_samples_exclude_zero(self):
        est, low, _ = stats.shift_interval([2.0, 2.1, 1.9, 2.05, 2.0], [1.0, 1.1, 0.9, 1.05, 1.0], 0.95)
        self.assertGreater(low, 0)
        self.assertAlmostEqual(est, 1.0, places=1)

    def test_one_outlier_moves_the_interval_little(self):
        base = [1.00, 1.01, 0.99, 1.00, 1.02, 0.98, 1.00]
        _, low, high = stats.shift_interval(base, base, 0.95)
        _, low2, high2 = stats.shift_interval(base[:-1] + [5.0], base, 0.95)
        self.assertLess(high2 - low2, 2 * (high - low))


if __name__ == "__main__":
    unittest.main()
