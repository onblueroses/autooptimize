"""Rule: fail closed, and a failed read or timeout never becomes a clean verdict."""

import sys
import unittest
from pathlib import Path
from unittest import mock

import helpers
from helpers import TempCase, make_project
from autooptimize import cli, loop
from autooptimize.bench import run_once
from autooptimize.ledger import Ledger

GOOD = 'import json; print(json.dumps({"metric": 1.5, "outputs": "abc"}))'


class BenchmarkFailures(TempCase):
    def bench(self, code, timeout=None):
        script = self.tmp / "b.py"
        script.write_text(code)
        return run_once([sys.executable, str(script)], self.tmp, timeout)

    def test_good_benchmark_passes(self):
        run = self.bench(GOOD)
        self.assertTrue(run.ok)
        self.assertEqual(run.metric, 1.5)

    def test_each_failure_is_a_failed_run(self):
        cases = {
            "nonzero exit": GOOD + "\nraise SystemExit(1)",
            "crash": "raise RuntimeError('boom')",
            "killed": "import os, signal; os.kill(os.getpid(), signal.SIGKILL)",
            "no output": "pass",
            "not json": "print('fast!')",
            "json list": "print('[1, 2]')",
            "nan metric": 'print(\'{"metric": NaN, "outputs": "abc"}\')',
            "bool metric": 'print(\'{"metric": true, "outputs": "abc"}\')',
            "missing outputs": 'print(\'{"metric": 1.0}\')',
            "empty outputs": 'print(\'{"metric": 1.0, "outputs": ""}\')',
        }
        for name, code in cases.items():
            with self.subTest(name):
                run = self.bench(code)
                self.assertFalse(run.ok)
                self.assertTrue(run.error)

    def test_timeout_is_a_failed_run(self):
        # The timeout value is a test fixture, not a run limit.
        run = self.bench("import time; time.sleep(30)", timeout=0.5)
        self.assertFalse(run.ok)
        self.assertIn("timeout", run.error)

    def test_missing_program_is_a_failed_run(self):
        run = run_once([str(self.tmp / "no-such-program")], self.tmp)
        self.assertFalse(run.ok)


class ExitStatus(TempCase):
    def noisy_project(self):
        return make_project(self.tmp / "p", noise=0.5)

    def test_success_is_zero(self):
        project = make_project(self.tmp / "p")
        self.assertEqual(cli.main(["check-config", str(project / "autooptimize.json")]), 0)

    def test_refusal_is_two(self):
        project = self.noisy_project()
        folder = helpers.proposals(self.tmp / "props", ("same", helpers.target()))
        with mock.patch("sys.stdout"), mock.patch("sys.stderr"):
            status = cli.main(["run", "--project", str(project), "--proposer", "scripted",
                               "--proposals", str(folder)])
        self.assertEqual(status, 2)

    def test_refusal_stays_two_when_its_record_cannot_be_written(self):
        project = self.noisy_project()
        folder = helpers.proposals(self.tmp / "props", ("same", helpers.target()))
        real = Ledger.append

        def failing(self, kind, **fields):
            if kind == "refusal":
                raise OSError("disk full")
            return real(self, kind, **fields)

        with mock.patch.object(Ledger, "append", failing), mock.patch("sys.stdout"), mock.patch("sys.stderr"):
            status = cli.main(["run", "--project", str(project), "--proposer", "scripted",
                               "--proposals", str(folder)])
        self.assertEqual(status, 2)

    def test_internal_error_is_two(self):
        with mock.patch.object(cli, "_dispatch", side_effect=RuntimeError("bug")), mock.patch("sys.stderr"):
            self.assertEqual(cli.main([]), 2)

    def test_interrupt_is_two(self):
        with mock.patch.object(cli, "_dispatch", side_effect=KeyboardInterrupt), mock.patch("sys.stderr"):
            self.assertEqual(cli.main([]), 2)

    def test_broken_output_cannot_change_the_status(self):
        with mock.patch.object(cli, "_dispatch", side_effect=RuntimeError("bug")), \
                mock.patch("builtins.print", side_effect=OSError("closed pipe")):
            self.assertEqual(cli.main([]), 2)

    def test_bad_arguments_are_two(self):
        with mock.patch("sys.stderr"):
            self.assertEqual(cli.main(["no-such-command"]), 2)

    def test_internal_error_inside_the_loop_is_a_refusal(self):
        project = make_project(self.tmp / "p")
        folder = helpers.proposals(self.tmp / "props", ("same", helpers.target()))
        with mock.patch.object(loop, "check_noise", side_effect=ZeroDivisionError("bug")), \
                mock.patch("sys.stdout"), mock.patch("sys.stderr"):
            status = cli.main(["run", "--project", str(project), "--proposer", "scripted",
                               "--proposals", str(folder)])
        self.assertEqual(status, 2)
        ledger = next(Path(project, ".autooptimize", "runs").glob("*/ledger.jsonl"))
        self.assertIn("internal error", ledger.read_text())


if __name__ == "__main__":
    unittest.main()
