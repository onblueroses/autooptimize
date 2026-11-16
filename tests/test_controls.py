"""Rule: prove the instrument can see an effect before it judges real changes."""

import unittest

from helpers import RecordingProposer, TempCase, make_project, quiet, runs
from autooptimize import loop
from autooptimize.controls import run_controls
from autooptimize.decide import INCONCLUSIVE, KeepRule, Verdict, decide
from autooptimize.errors import Refusal

RULE = KeepRule(0.05, 0.95, "lower")
A = runs([1.00, 1.01, 0.99, 1.00, 1.02, 0.98, 1.00])
B = runs([1.01, 0.99, 1.00, 1.00, 0.98, 1.02, 1.00])


def blind(base, cand, rule):
    return Verdict(INCONCLUSIVE, "this scorer sees nothing")


def ignores_outputs(base, cand, rule):
    return decide(base, [r.__class__(r.ok, r.metric, base[0].outputs if r.ok else None, r.error) for r in cand], rule)


class Controls(TempCase):
    def fired(self, decide_fn):
        return {r["control"]: r["fired"] for r in run_controls(A, B, RULE, decide_fn=decide_fn)}

    def test_shift_is_threshold_plus_measured_interval_width(self):
        shift = run_controls(A, B, RULE)[0]["shift"]
        self.assertGreater(shift, RULE.min_gain)
        self.assertAlmostEqual(shift - RULE.min_gain, 2 * decide(A, B, RULE).detection_limit)

    def test_scorer_with_the_sign_wrong_misses_the_known_effects(self):
        flipped = KeepRule(RULE.min_gain, RULE.confidence, "higher")
        fired = {r["control"]: r["fired"] for r in run_controls(
            A, B, RULE, decide_fn=lambda base, cand, rule: decide(base, cand, flipped))}
        self.assertFalse(fired["improvement"])
        self.assertFalse(fired["regression"])

    def test_controls_fire_on_real_noisy_runs_too(self):
        import random
        rng = random.Random(1)
        for _ in range(200):
            a = runs([1 + rng.gauss(0, 0.03) for _ in range(7)])
            b = runs([1 + rng.gauss(0, 0.03) for _ in range(7)])
            fired = {r["control"]: r["fired"] for r in run_controls(a, b, KeepRule(0.05, 0.99, "lower"))}
            if fired["null"]:  # the known effects are judged against a null that held
                self.assertTrue(fired["improvement"] and fired["regression"])

    def test_working_scorer_fires_every_control(self):
        self.assertEqual(set(self.fired(decide).values()), {True})

    def test_blind_scorer_misses_the_known_effects(self):
        fired = self.fired(blind)
        self.assertFalse(fired["improvement"])
        self.assertFalse(fired["regression"])
        self.assertTrue(fired["null"])

    def test_scorer_without_identity_check_misses_the_output_control(self):
        self.assertFalse(self.fired(ignores_outputs)["changed_output"])

    def test_loop_refuses_when_a_control_misses(self):
        project = make_project(self.tmp / "p")
        proposer = RecordingProposer()
        with self.assertRaisesRegex(Refusal, "did not fire"):
            loop.run(project, project / "autooptimize.json", proposer, out=quiet, decide_fn=blind)
        self.assertEqual(proposer.calls, 0)


if __name__ == "__main__":
    unittest.main()
