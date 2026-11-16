"""Run the benchmark command. Every failure is a failed run, never a pass.

Protocol: the command exits 0 and its last non-empty stdout line is a JSON
object {"metric": <finite number>, "outputs": "<digest of all outputs>"}.
"""

import json
import math
import os
import subprocess
from dataclasses import asdict, dataclass


@dataclass
class Run:
    ok: bool
    metric: float = None
    outputs: str = None
    error: str = None
    returncode: int = None
    stdout: str = ""
    stderr: str = ""

    def to_dict(self):
        return asdict(self)


def _text(data):
    if data is None:
        return ""
    return data.decode(errors="replace") if isinstance(data, bytes) else data


def run_once(command, cwd, timeout_s=None):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    try:
        proc = subprocess.run(
            command, cwd=cwd, capture_output=True, text=True, timeout=timeout_s, env=env
        )
    except subprocess.TimeoutExpired as exc:
        return Run(False, error=f"timeout after {timeout_s} s", stdout=_text(exc.stdout), stderr=_text(exc.stderr))
    except OSError as exc:
        return Run(False, error=f"cannot start the benchmark: {exc}")
    run = Run(False, returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)
    if proc.returncode != 0:
        run.error = f"exit status {proc.returncode}"
        return run
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    if not lines:
        run.error = "no output"
        return run
    try:
        record = json.loads(lines[-1])
    except ValueError:
        run.error = "last output line is not JSON"
        return run
    if not isinstance(record, dict):
        run.error = "last output line is not a JSON object"
        return run
    metric, outputs = record.get("metric"), record.get("outputs")
    if isinstance(metric, bool) or not isinstance(metric, (int, float)) or not math.isfinite(metric):
        run.error = "metric is missing or not a finite number"
        return run
    if not isinstance(outputs, str) or not outputs:
        run.error = "outputs digest is missing"
        return run
    run.ok, run.metric, run.outputs = True, float(metric), outputs
    return run
