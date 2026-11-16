"""Rule: a null states its detection limit, and every number states its kind."""

import unittest

import helpers  # noqa: F401
from autooptimize.report import KINDS, ReportError, build, render

RULE = {
    "min_gain": {"value": 0.05, "source": "ruling: test"},
    "confidence": {"value": 0.95, "source": "ruling: test"},
    "runs_per_side": {"value": 5, "source": "ruling: test"},
}


def ledger(*trials):
    rows = [
        (1, {"kind": "start", "contract": "c", "run": "r", "keep_rule": RULE, "direction": "lower",
             "arms": ["tidy", "algorithm"]}),
        (2, {"kind": "preflight", "contract": "c", "ok": True, "baseline_median": 1.0, "detection_limit": 0.02}),
        (3, {"kind": "control", "contract": "c", "control": "null", "expected": "INCONCLUSIVE",
             "got": "INCONCLUSIVE", "fired": True}),
    ]
    for i, t in enumerate(trials, start=4):
        rows.append((i, dict({"kind": "trial", "contract": "c", "trial": i - 3, "reason": "r",
                              "gain_low": None, "gain_high": None, "detection_limit": 0.03}, **t)))
    return rows


class NullReport(unittest.TestCase):
    def test_null_states_its_limit_controls_arms_and_route(self):
        rep = build(ledger({"arm": "tidy", "verdict": "INCONCLUSIVE", "gain": 0.01}))
        self.assertEqual(rep["outcome"], "no effect found")
        text = render(rep)
        self.assertIn("Detection limit: 3.0% (measured)", text)
        self.assertIn("Controls fired: 1 of 1", text)
        self.assertIn("Untried arms: algorithm", text)
        self.assertIn("Next route:", text)

    def test_null_without_a_detection_limit_is_not_printed(self):
        for field in ("detection_limit", "controls_fired", "untried_arms", "next_route"):
            with self.subTest(field):
                rep = build(ledger({"arm": "tidy", "verdict": "INCONCLUSIVE", "gain": 0.01}))
                rep["null"][field] = None
                with self.assertRaisesRegex(ReportError, field):
                    render(rep)

    def test_kept_run_is_not_a_null(self):
        rep = build(ledger({"arm": "algorithm", "verdict": "KEEP", "gain": 0.5}))
        self.assertEqual(rep["outcome"], "improved")
        self.assertNotIn("null", rep)
        render(rep)


class NumberKinds(unittest.TestCase):
    def test_every_number_has_a_kind_and_measured_ones_point_to_the_ledger(self):
        rows = ledger({"arm": "algorithm", "verdict": "KEEP", "gain": 0.5})
        lines = {line for line, _ in rows}
        rep = build(rows)
        kinds = {n["kind"] for n in rep["numbers"]}
        self.assertTrue(kinds <= set(KINDS))
        self.assertTrue({"measured", "estimate", "required", "unknown"} <= kinds)
        for n in rep["numbers"]:
            if n["kind"] == "measured":
                self.assertRegex(n["source"], r"^ledger\.jsonl:\d+$")
                self.assertIn(int(n["source"].split(":")[1]), lines)

    def test_total_gain_is_labelled_an_estimate(self):
        rep = build(ledger({"arm": "a", "verdict": "KEEP", "gain": 0.5}, {"arm": "b", "verdict": "KEEP", "gain": 0.5}))
        total = next(n for n in rep["numbers"] if n["name"] == "total gain over the run")
        self.assertEqual(total["kind"], "estimate")
        self.assertEqual(total["value"], "+75.0%")


if __name__ == "__main__":
    unittest.main()
