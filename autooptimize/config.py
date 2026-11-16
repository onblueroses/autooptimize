"""Load the run config. Every number in it must carry its source."""

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .errors import Refusal

SOURCE_KINDS = ("measured", "system", "ruling")

# Three runs per side are the floor for judging a delta against its uncertainty.
MIN_RUNS_PER_SIDE = 3


def _check_source(path, node):
    extra = set(node) - {"value", "source"}
    if extra:
        raise Refusal(f"{path} has unknown keys {sorted(extra)}. A limit has only value and source.")
    value = node.get("value")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise Refusal(f"{path}.value must be a number.")
    source = node.get("source")
    kind, _, text = (source or "").partition(":")
    if kind.strip() not in SOURCE_KINDS or not text.strip():
        raise Refusal(
            f"{path} has no valid source. Write the source as 'measured: ...', "
            f"'system: ...' or 'ruling: ...', or remove the limit."
        )


def check_limits(node, path="config"):
    """Refuse a number that has no source beside it."""
    if isinstance(node, bool) or node is None or isinstance(node, str):
        return
    if isinstance(node, (int, float)):
        raise Refusal(
            f"{path} is a number without a source. Write it as "
            f'{{"value": ..., "source": "measured: ..."}}, or remove it.'
        )
    if isinstance(node, dict):
        if "value" in node:
            _check_source(path, node)
            return
        for key, child in node.items():
            check_limits(child, f"{path}.{key}")
        return
    if isinstance(node, list):
        for i, child in enumerate(node):
            check_limits(child, f"{path}[{i}]")
        return
    raise Refusal(f"{path} has an unsupported type {type(node).__name__}.")


def _limit(raw, *keys, required=True):
    node = raw
    for key in keys:
        if not isinstance(node, dict) or key not in node:
            if required:
                raise Refusal(f"The config has no {'.'.join(keys)}.")
            return None
        node = node[key]
    return node["value"]


@dataclass(frozen=True)
class Config:
    path: Path
    raw: dict
    target: str
    command: list
    frozen: list
    direction: str
    min_gain: float
    confidence: float
    runs_per_side: int
    benchmark_timeout_s: float = None
    proposer_timeout_s: float = None
    arms: list = field(default_factory=list)


def load_config(path):
    path = Path(path)
    try:
        raw = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise Refusal(f"Cannot read the config {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise Refusal("The config must be a JSON object.")
    check_limits(raw)

    target = raw.get("target")
    bench = raw.get("benchmark") or {}
    command = bench.get("command")
    frozen = bench.get("frozen")
    if not isinstance(target, str) or not target:
        raise Refusal("The config has no target file.")
    if not isinstance(command, list) or not command or not all(isinstance(c, str) for c in command):
        raise Refusal("benchmark.command must be a non-empty list of strings.")
    if not isinstance(frozen, list) or not frozen or not all(isinstance(f, str) for f in frozen):
        raise Refusal("benchmark.frozen must list the benchmark files and the test inputs.")
    if target in frozen:
        raise Refusal("The target cannot also be a frozen file.")
    direction = raw.get("direction")
    if direction not in ("lower", "higher"):
        raise Refusal("direction must be 'lower' or 'higher'.")

    min_gain = _limit(raw, "keep_rule", "min_gain")
    confidence = _limit(raw, "keep_rule", "confidence")
    runs = _limit(raw, "keep_rule", "runs_per_side")
    if not min_gain > 0:
        raise Refusal("keep_rule.min_gain must be above 0.")
    if not 0 < confidence < 1:
        raise Refusal("keep_rule.confidence must be between 0 and 1.")
    if int(runs) != runs or runs < MIN_RUNS_PER_SIDE:
        raise Refusal(f"keep_rule.runs_per_side must be a whole number of at least {MIN_RUNS_PER_SIDE}.")

    arms = raw.get("arms", [])
    if not isinstance(arms, list) or not all(isinstance(a, str) for a in arms):
        raise Refusal("arms must be a list of strings.")

    return Config(
        path=path,
        raw=raw,
        target=target,
        command=[sys.executable if c == "{python}" else c for c in command],
        frozen=list(frozen),
        direction=direction,
        min_gain=float(min_gain),
        confidence=float(confidence),
        runs_per_side=int(runs),
        benchmark_timeout_s=_limit(raw, "benchmark", "timeout_s", required=False),
        proposer_timeout_s=_limit(raw, "proposer", "timeout_s", required=False),
        arms=arms,
    )
