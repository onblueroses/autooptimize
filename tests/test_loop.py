"""End to end on a synthetic project: the verdicts, the ledger and the kept artifacts."""

import json
import unittest

import helpers
from helpers import TempCase, git, make_project, quiet, target
from autooptimize import loop
from autooptimize.errors import Refusal
from autooptimize.ledger import read
from autooptimize.proposers import Proposal, ProposalError, ScriptedProposer


def trials(run_dir):
    return [r for _, r in read(run_dir / "ledger.jsonl") if r["kind"] == "trial"]


class EndToEnd(TempCase):
    def test_verdicts_ledger_branch_and_artifacts(self):
        project = make_project(self.tmp / "p")
        head = git(project, "rev-parse", "HEAD")
        folder = helpers.proposals(
            self.tmp / "props",
            ("speed", target(cost=0.5)),
            ("wrong", target(cost=0.25, factor=3)),
            ("same", target(cost=0.5) + "\n# tidy\n"),
            ("slower", target(cost=1.0)),
            ("crash", "raise RuntimeError('boom')\n"),
        )
        run_dir = loop.run(project, project / "autooptimize.json", ScriptedProposer(folder), out=quiet)

        verdicts = [(t["arm"], t["verdict"]) for t in trials(run_dir)]
        self.assertEqual(verdicts, [("speed", "KEEP"), ("wrong", "DISCARD"), ("same", "INCONCLUSIVE"),
                                    ("slower", "DISCARD"), ("crash", "FAILED")])
        # The project's own checkout is untouched. The kept change is on the run branch.
        self.assertEqual(git(project, "rev-parse", "HEAD"), head)
        self.assertEqual((project / "target.py").read_text(), target())
        branch = f"autooptimize/{run_dir.name}"
        self.assertEqual(git(project, "show", f"{branch}:target.py"), "# arm: speed\n" + target(cost=0.5))
        self.assertEqual(len(git(project, "log", "--oneline", f"main..{branch}").splitlines()), 1)
        # Every trial kept its artifacts. The manifest checks out and the worktrees are gone.
        for n in range(1, 6):
            self.assertTrue((run_dir / f"trial-{n:03d}" / "target.py").exists())
        manifest = json.loads((run_dir / "manifest.json").read_text())
        self.assertIn("ledger.jsonl", manifest)
        self.assertIn("trial-005/runs/cand-1.json", manifest)
        self.assertTrue((run_dir / "DONE").exists())
        self.assertFalse((run_dir / "best").exists())
        self.assertIn("Outcome: improved.", (run_dir / "report.md").read_text())

    def test_proposal_error_is_a_failed_trial_and_the_loop_goes_on(self):
        class Flaky:
            calls = 0

            def propose(self, current, history):
                self.calls += 1
                if self.calls == 1:
                    raise ProposalError("no code block")
                if self.calls == 2:
                    return Proposal("speed", "", target(cost=0.5))
                return None

        project = make_project(self.tmp / "p")
        run_dir = loop.run(project, project / "autooptimize.json", Flaky(), out=quiet)
        self.assertEqual([t["verdict"] for t in trials(run_dir)], ["FAILED", "KEEP"])


class KeptWhenLaterCheckFails(TempCase):
    def test_artifacts_and_ledger_survive_a_refusal(self):
        class TouchesProject:
            calls = 0

            def propose(self, current, history):
                self.calls += 1
                if self.calls == 2:
                    (project / "stray.txt").write_text("the proposer wrote here")
                return Proposal("speed" if self.calls == 1 else "x", "", target(cost=0.5))

        project = make_project(self.tmp / "p")
        with self.assertRaisesRegex(Refusal, "uncommitted"):
            loop.run(project, project / "autooptimize.json", TouchesProject(), out=quiet)
        run_dir = next((project / ".autooptimize" / "runs").iterdir())
        kinds = [r["kind"] for _, r in read(run_dir / "ledger.jsonl")]
        self.assertEqual(kinds[-2:], ["trial", "refusal"])
        self.assertTrue((run_dir / "trial-001" / "target.py").exists())
        self.assertTrue(list((run_dir / "trial-001" / "runs").glob("cand-*.json")))
        self.assertFalse((run_dir / "DONE").exists())
        self.assertIn("speed", git(project, "log", "--format=%s", f"autooptimize/{run_dir.name}"))


if __name__ == "__main__":
    unittest.main()
