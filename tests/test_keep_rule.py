"""Rule: keep a change only when it beats noise and keeps outputs identical."""

import unittest

from helpers import runs
from autooptimize.bench import Run
from autooptimize.decide import DISCARD, FAILED, INCONCLUSIVE, KEEP, KeepRule, decide

RULE = KeepRule(min_gain=0.05, confidence=0.95, direction="lower")
BASE = [1.00, 1.01, 0.99, 1.00, 1.02, 0.98, 1.00]


class KeepRuleTest(unittest.TestCase):
    def test_keep_when_gain_beats_noise_and_outputs_match(self):
        v = decide(runs(BASE), runs([m * 0.8 for m in BASE]), RULE)
        self.assertEqual(v.verdict, KEEP)
        self.assertAlmostEqual(v.gain, 0.2, places=2)

    def test_same_gain_with_changed_outputs_is_discarded(self):
        v = decide(runs(BASE), runs([m * 0.8 for m in BASE], outputs="different"), RULE)
        self.assertEqual(v.verdict, DISCARD)
        self.assertIn("outputs differ", v.reason)

    def test_difference_inside_noise_is_inconclusive_with_its_limit(self):
        v = decide(runs(BASE), runs(list(reversed(BASE))), RULE)
        self.assertEqual(v.verdict, INCONCLUSIVE)
        self.assertGreater(v.detection_limit, 0)
        self.assertIn("no effect larger than", v.reason)

    def test_real_gain_below_threshold_is_inconclusive(self):
        base = [1.0, 1.001, 0.999, 1.0, 1.0005]
        v = decide(runs(base), runs([m * 0.98 for m in base]), RULE)
        self.assertEqual(v.verdict, INCONCLUSIVE)
        self.assertIn("below the keep threshold", v.reason)

    def test_regression_is_discarded(self):
        v = decide(runs(BASE), runs([m * 1.2 for m in BASE]), RULE)
        self.assertEqual(v.verdict, DISCARD)
        self.assertIn("regression", v.reason)

    def test_direction_higher(self):
        rule = KeepRule(0.05, 0.95, "higher")
        self.assertEqual(decide(runs(BASE), runs([m * 1.2 for m in BASE]), rule).verdict, KEEP)
        self.assertEqual(decide(runs(BASE), runs([m * 0.8 for m in BASE]), rule).verdict, DISCARD)


class FailClosedVerdicts(unittest.TestCase):
    def test_failed_candidate_run(self):
        cand = runs([0.5] * 6) + [Run(False, error="exit status 1")]
        self.assertEqual(decide(runs(BASE), cand, RULE).verdict, FAILED)

    def test_failed_baseline_run(self):
        base = [Run(False, error="timeout")] + runs(BASE[1:])
        self.assertEqual(decide(base, runs([0.5] * 7), RULE).verdict, FAILED)

    def test_no_candidate_runs(self):
        self.assertEqual(decide(runs(BASE), [], RULE).verdict, FAILED)

    def test_baseline_outputs_that_vary(self):
        base = runs(BASE[:3]) + runs(BASE[3:], outputs="other")
        self.assertEqual(decide(base, runs(BASE), RULE).verdict, FAILED)

    def test_scorer_error_is_failed_not_keep(self):
        broken = [Run(True, metric=None, outputs="same") for _ in BASE]
        v = decide(runs(BASE), broken, RULE)
        self.assertEqual(v.verdict, FAILED)
        self.assertIn("scorer error", v.reason)


if __name__ == "__main__":
    unittest.main()
