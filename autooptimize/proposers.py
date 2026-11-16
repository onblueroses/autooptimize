"""Proposers return a complete new version of the target file.

ClaudeProposer calls the `claude` CLI in print mode with all tools turned
off, so the model can only answer with text. The loop writes the file.
ScriptedProposer replays files from a folder. Tests and the demo use it.
"""

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


class ProposalError(Exception):
    """The proposer failed or returned an answer the loop cannot use."""


@dataclass
class Proposal:
    arm: str
    rationale: str
    content: str


class ScriptedProposer:
    """Replay `*.py` files from a folder in name order.

    The first line of each file can name the arm: `# arm: <name>`.
    The second line can give the reason: `# why: <sentence>`.
    """

    def __init__(self, folder):
        self.files = sorted(Path(folder).glob("*.py"))
        if not self.files:
            raise ProposalError(f"{folder} contains no proposal files.")
        self.index = 0

    def propose(self, current, history):
        if self.index >= len(self.files):
            return None
        path = self.files[self.index]
        self.index += 1
        content = path.read_text()
        arm = re.search(r"^# arm: *(.+)$", content, re.M)
        why = re.search(r"^# why: *(.+)$", content, re.M)
        return Proposal(
            arm=arm.group(1).strip() if arm else path.stem,
            rationale=why.group(1).strip() if why else "",
            content=content,
        )


PROMPT = """You propose one change to the file {target}.
The goal is a {direction} benchmark metric. The outputs on the frozen test set must stay identical.

Rules:
- Change only this file. Keep the public functions and their results.
- Return the complete new file, not a diff.
- Prefer a change of algorithm or data structure over a micro-optimization.
- Do not repeat an idea that the past trials show as DISCARD or FAILED.

Ideas to consider: {arms}

Past trials (arm, verdict, gain, reason):
{history}

Answer format:
ARM: <a short name for the idea>
WHY: <one sentence>
Then the complete file in one fenced code block.

The current file:
```
{current}
```
"""

_ARM = re.compile(r"^ARM:\s*(.+)$", re.M)
_WHY = re.compile(r"^WHY:\s*(.+)$", re.M)
_CODE = re.compile(r"```[\w.+-]*\n(.*?)```", re.S)


def parse_answer(text):
    arm, why, code = _ARM.search(text), _WHY.search(text), _CODE.findall(text)
    if not arm or not code:
        raise ProposalError("The answer has no ARM line or no code block.")
    if len(code) != 1:
        raise ProposalError(f"The answer has {len(code)} code blocks. It must have exactly one.")
    return Proposal(arm.group(1).strip(), why.group(1).strip() if why else "", code[0])


def format_history(history):
    if not history:
        return "none"
    lines = []
    for t in history:
        gain = "n/a" if t.get("gain") is None else f"{t['gain']:+.1%}"
        lines.append(f"- {t.get('arm')}: {t.get('verdict')}, {gain}, {t.get('reason')}")
    return "\n".join(lines)


class ClaudeProposer:
    def __init__(self, target, direction, arms=(), model=None, binary="claude", timeout_s=None):
        self.target, self.direction, self.arms = target, direction, list(arms)
        self.model, self.binary, self.timeout_s = model, binary, timeout_s

    def command(self):
        cmd = [self.binary, "-p", "--tools", "", "--output-format", "text"]
        if self.model:
            cmd += ["--model", self.model]
        return cmd

    def prompt(self, current, history):
        return PROMPT.format(
            target=self.target,
            direction=self.direction,
            arms=", ".join(self.arms) or "any",
            history=format_history(history),
            current=current,
        )

    def propose(self, current, history):
        try:
            proc = subprocess.run(
                self.command(),
                input=self.prompt(current, history),
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ProposalError(f"claude did not answer: {exc}") from exc
        if proc.returncode != 0:
            raise ProposalError(f"claude exited with status {proc.returncode}: {proc.stderr.strip()[:300]}")
        return parse_answer(proc.stdout)
