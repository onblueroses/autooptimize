"""Rule: freeze the target, the benchmark, the scorer and the keep rule before the run."""

import json
import unittest
from unittest import mock

import helpers
from helpers import TempCase, git, make_project, quiet
from autooptimize import contract, loop
from autooptimize.config import load_config
from autooptimize.errors import Refusal
from autooptimize.ledger import read
from autooptimize.proposers import Proposal
from autooptimize.report import ReportError, build


class Freeze(TempCase):
    def setUp(self):
        super().setUp()
        self.project = make_project(self.tmp / "p")
        self.cfg = load_config(self.project / "autooptimize.json")
        self.path = self.tmp / "contract.json"
        _, self.digest = contract.freeze(self.project, self.cfg, "HEAD", self.path)

    def verify(self):
        return contract.verify(self.path, self.digest, [self.project])

    def test_unchanged_contract_verifies(self):
        c = self.verify()
        self.assertEqual(set(c["benchmark"]["frozen"]), {"bench.py", "inputs.json"})

    def test_changed_benchmark_is_refused(self):
        (self.project / "bench.py").write_text("print('fast')\n")
        with self.assertRaises(Refusal):
            self.verify()

    def test_changed_test_inputs_are_refused(self):
        (self.project / "inputs.json").write_text("[1]\n")
        with self.assertRaises(Refusal):
            self.verify()

    def test_changed_config_is_refused(self):
        (self.project / "autooptimize.json").write_text("{}")
        with self.assertRaises(Refusal):
            self.verify()

    def test_changed_scorer_is_refused(self):
        with mock.patch.object(contract, "scorer_sha256", return_value="0" * 64):
            with self.assertRaises(Refusal):
                self.verify()

    def test_edited_contract_file_is_refused(self):
        data = json.loads(self.path.read_text())
        data["contract"]["keep_rule"]["min_gain"]["value"] = 0.0001
        self.path.write_text(json.dumps(data))
        with self.assertRaises(Refusal):
            self.verify()


class ConfigEditor:
    """Edits and commits the config during the run, so the tree stays clean."""

    def __init__(self, project):
        self.project, self.calls = project, 0

    def propose(self, current, history):
        self.calls += 1
        if self.calls == 2:
            cfg = json.loads((self.project / "autooptimize.json").read_text())
            cfg["keep_rule"]["min_gain"]["value"] = 0.001
            (self.project / "autooptimize.json").write_text(json.dumps(cfg))
            git(self.project, "commit", "-qam", "Lower the threshold mid-run")
        return Proposal("same", "", current)


class MidRun(TempCase):
    def test_config_change_mid_run_stops_the_run(self):
        project = make_project(self.tmp / "p")
        with self.assertRaisesRegex(Refusal, "config changed"):
            loop.run(project, project / "autooptimize.json", ConfigEditor(project), out=quiet)

    def test_report_refuses_two_contract_hashes(self):
        rows = [(1, {"kind": "start", "contract": "a"}), (2, {"kind": "start", "contract": "b"})]
        with self.assertRaisesRegex(ReportError, "contract hashes"):
            build(rows)


if __name__ == "__main__":
    unittest.main()
