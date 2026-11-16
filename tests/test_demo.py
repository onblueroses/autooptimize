"""The bundled demo shows KEEP, DISCARD, INCONCLUSIVE and FAILED without an API key."""

import unittest
from unittest import mock

from helpers import TempCase
from autooptimize import cli
from autooptimize.ledger import read


class Demo(TempCase):
    def test_demo_run(self):
        folder = self.tmp / "demo"
        with mock.patch("sys.stdout"), mock.patch("sys.stderr"):
            status = cli.main(["demo", "--dir", str(folder)])
        ledger = next((folder / ".autooptimize" / "runs").glob("*/ledger.jsonl"))
        rows = [r for _, r in read(ledger)]
        refusals = [r["reason"] for r in rows if r["kind"] == "refusal"]
        if status == 2 and refusals and "too noisy" in refusals[0]:
            # A correct refusal on a busy machine. tests/test_preflight.py covers this path.
            self.skipTest(f"the machine is too noisy for the demo now: {refusals[0]}")
        self.assertEqual(status, 0, refusals)
        self.assertTrue(all(r["fired"] for r in rows if r["kind"] == "control"))
        verdicts = {r["trial"]: r for r in rows if r["kind"] == "trial"}
        # Trial 1 changes only names. A timing rig can at worst misjudge it, never keep it.
        self.assertNotEqual(verdicts[1]["verdict"], "KEEP")
        self.assertEqual(verdicts[2]["verdict"], "DISCARD")
        self.assertIn("outputs differ", verdicts[2]["reason"])
        self.assertGreater(verdicts[2]["gain"], 0.5)
        self.assertEqual(verdicts[3]["verdict"], "KEEP")
        self.assertEqual(verdicts[4]["verdict"], "DISCARD")
        self.assertIn("regression", verdicts[4]["reason"])
        self.assertEqual(verdicts[5]["verdict"], "FAILED")


if __name__ == "__main__":
    unittest.main()
