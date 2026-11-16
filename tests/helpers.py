"""Shared fixtures: a tiny git project with a synthetic benchmark."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autooptimize.bench import Run  # noqa: E402

TARGET = '''COST = {cost}


def solve(xs):
    return [x * {factor} for x in xs]
'''

# The metric is COST times uniform noise. NOISE is part of the frozen benchmark.
# The default noise is 0, so the loop tests are exact. The noise tests set it.
BENCH = '''import hashlib, json, random
import target

xs = json.load(open("inputs.json"))
out = target.solve(xs)
metric = target.COST * (1 + random.uniform(-{noise}, {noise}))
print(json.dumps({{"metric": metric, "outputs": hashlib.sha256(json.dumps(out).encode()).hexdigest()}}))
'''


def target(cost=1.0, factor=2):
    return TARGET.format(cost=cost, factor=factor)


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


def config(runs=5, min_gain=0.05, **extra):
    cfg = {
        "target": "target.py",
        "benchmark": {"command": ["{python}", "bench.py"], "frozen": ["bench.py", "inputs.json"]},
        "direction": "lower",
        "keep_rule": {
            "min_gain": {"value": min_gain, "source": "ruling: test threshold"},
            "confidence": {"value": 0.95, "source": "ruling: test convention"},
            "runs_per_side": {"value": runs, "source": "ruling: test size"},
        },
        "arms": ["speed", "wrong", "same", "slower", "crash"],
    }
    cfg.update(extra)
    return cfg


def make_project(root, noise=0.0, bench=None, cfg=None):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    (root / "target.py").write_text(target())
    (root / "bench.py").write_text(bench if bench is not None else BENCH.format(noise=noise))
    (root / "inputs.json").write_text("[1, 2, 3]\n")
    (root / "autooptimize.json").write_text(json.dumps(cfg or config(), indent=2))
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.name", "test")
    git(root, "config", "user.email", "test@example.invalid")
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "Baseline")
    return root


def proposals(folder, *contents):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    for i, (arm, text) in enumerate(contents, start=1):
        (folder / f"{i:02d}.py").write_text(f"# arm: {arm}\n{text}")
    return folder


def runs(metrics, outputs="same"):
    return [Run(True, metric=m, outputs=outputs) for m in metrics]


class TempCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()


class RecordingProposer:
    """Counts calls. Used to prove that a refusal comes before any proposer call."""

    def __init__(self):
        self.calls = 0

    def propose(self, current, history):
        self.calls += 1
        return None


def quiet(*_args, **_kwargs):
    pass
