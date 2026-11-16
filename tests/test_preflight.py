"""Rule: run refusal checks before spend, and refuse before the proposer is called."""

import json
import unittest

from helpers import BENCH, RecordingProposer, TempCase, config, git, make_project, quiet
from autooptimize import loop
from autooptimize.errors import Refusal


class Preflight(TempCase):
    def run_loop(self, project):
        proposer = RecordingProposer()
        try:
            loop.run(project, project / "autooptimize.json", proposer, out=quiet)
        finally:
            self.assertEqual(proposer.calls, 0, "the proposer ran before the refusal")

    def test_quiet_benchmark_passes(self):
        project = make_project(self.tmp / "p")
        run_dir = loop.run(project, project / "autooptimize.json", RecordingProposer(), out=quiet)
        self.assertTrue((run_dir / "DONE").exists())

    def test_dirty_tree_is_refused(self):
        project = make_project(self.tmp / "p")
        (project / "target.py").write_text("COST = 0.1\n")
        with self.assertRaisesRegex(Refusal, "uncommitted"):
            self.run_loop(project)

    def test_untracked_file_is_refused(self):
        project = make_project(self.tmp / "p")
        (project / "notes.txt").write_text("x")
        with self.assertRaisesRegex(Refusal, "uncommitted"):
            self.run_loop(project)

    def test_missing_benchmark_is_refused(self):
        project = make_project(self.tmp / "p")
        git(project, "rm", "-q", "bench.py")
        git(project, "commit", "-qm", "Remove the benchmark")
        with self.assertRaisesRegex(Refusal, "bench.py does not exist"):
            self.run_loop(project)

    def test_missing_benchmark_program_is_refused(self):
        cfg = config()
        cfg["benchmark"]["command"] = ["no-such-benchmark-program"]
        project = make_project(self.tmp / "p", cfg=cfg)
        with self.assertRaisesRegex(Refusal, "does not exist"):
            self.run_loop(project)

    def test_noise_above_the_keep_threshold_is_refused(self):
        project = make_project(self.tmp / "p", noise=0.4)
        with self.assertRaisesRegex(Refusal, "too noisy"):
            self.run_loop(project)

    def test_varying_outputs_are_refused(self):
        bench = BENCH.format(noise=0.0).replace("out = target.solve(xs)", "out = random.random()")
        project = make_project(self.tmp / "p", bench=bench)
        with self.assertRaisesRegex(Refusal, "outputs vary"):
            self.run_loop(project)

    def test_failing_benchmark_is_refused(self):
        project = make_project(self.tmp / "p", bench="raise SystemExit(3)\n")
        with self.assertRaisesRegex(Refusal, "failed"):
            self.run_loop(project)

    def test_too_few_runs_are_refused(self):
        project = make_project(self.tmp / "p", cfg=config(runs=2))
        with self.assertRaisesRegex(Refusal, "at least 3"):
            self.run_loop(project)

    def test_runs_too_few_for_the_confidence_are_refused(self):
        project = make_project(self.tmp / "p", cfg=config(runs=3))
        with self.assertRaisesRegex(Refusal, "at least 4 runs per side"):
            self.run_loop(project)

    def test_refusal_is_recorded_in_the_ledger(self):
        project = make_project(self.tmp / "p", noise=0.4)
        with self.assertRaises(Refusal):
            self.run_loop(project)
        ledger = next((project / ".autooptimize" / "runs").glob("*/ledger.jsonl"))
        kinds = [json.loads(line)["kind"] for line in ledger.read_text().splitlines()]
        self.assertEqual(kinds[-2:], ["preflight", "refusal"])


if __name__ == "__main__":
    unittest.main()
