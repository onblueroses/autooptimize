"""The Claude Code proposer, tested with a fake CLI. A live contract test runs only on request."""

import os
import shutil
import stat
import unittest

from helpers import TempCase
from autooptimize.proposers import ClaudeProposer, ProposalError, parse_answer

ANSWER = "ARM: algorithm\nWHY: A sieve is faster.\n```python\nCOST = 0.5\n```\n"


class Parse(unittest.TestCase):
    def test_good_answer(self):
        p = parse_answer(ANSWER)
        self.assertEqual((p.arm, p.rationale, p.content), ("algorithm", "A sieve is faster.", "COST = 0.5\n"))

    def test_bad_answers_are_errors(self):
        for text in ("no format at all", "ARM: x\nno code", "```\na\n```", ANSWER + "```\nb\n```"):
            with self.subTest(text), self.assertRaises(ProposalError):
                parse_answer(text)


class FakeCli(TempCase):
    def fake(self, body):
        path = self.tmp / "claude"
        path.write_text("#!/bin/sh\n" + body)
        path.chmod(path.stat().st_mode | stat.S_IEXEC)
        return str(path)

    def test_prompt_goes_to_stdin_and_tools_are_off(self):
        binary = self.fake(f'cat > "{self.tmp}/prompt.txt"\necho "$@" > "{self.tmp}/args.txt"\n'
                           f"cat <<'EOF'\n{ANSWER}EOF\n")
        proposer = ClaudeProposer("target.py", "lower", ["algorithm"], binary=binary)
        p = proposer.propose("COST = 1.0\n", [{"arm": "tidy", "verdict": "INCONCLUSIVE", "gain": 0.0, "reason": "r"}])
        self.assertEqual(p.arm, "algorithm")
        prompt = (self.tmp / "prompt.txt").read_text()
        self.assertIn("COST = 1.0", prompt)
        self.assertIn("tidy: INCONCLUSIVE", prompt)
        self.assertEqual(proposer.command()[1:4], ["-p", "--tools", ""])

    def test_cli_failure_is_a_proposal_error(self):
        proposer = ClaudeProposer("target.py", "lower", binary=self.fake("exit 1\n"))
        with self.assertRaises(ProposalError):
            proposer.propose("x", [])

    def test_missing_cli_is_a_proposal_error(self):
        proposer = ClaudeProposer("target.py", "lower", binary=str(self.tmp / "missing"))
        with self.assertRaises(ProposalError):
            proposer.propose("x", [])


LIVE = os.environ.get("AUTOOPTIMIZE_LIVE_CLAUDE") == "1"


@unittest.skipUnless(LIVE and shutil.which("claude"),
                     "live contract test: set AUTOOPTIMIZE_LIVE_CLAUDE=1 with a logged-in claude CLI. "
                     "A green offline run is not a green live run.")
class LiveClaude(unittest.TestCase):
    def test_real_cli_returns_a_usable_proposal(self):
        from helpers import ROOT
        current = (ROOT / "autooptimize" / "demo" / "project" / "target.py").read_text()
        p = ClaudeProposer("target.py", "lower", ["algorithm"]).propose(current, [])
        self.assertIn("def solve", p.content)


if __name__ == "__main__":
    unittest.main()
