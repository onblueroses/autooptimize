"""Refusal checks that run before any trial or proposer call."""

import math
import os
import shutil
import statistics
import subprocess
from pathlib import Path

from . import stats
from .decide import KeepRule, decide
from .errors import Refusal


def git(cwd, *args, check=True):
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise Refusal(f"git {' '.join(args)} failed in {cwd}: {proc.stderr.strip()}")
    return proc


def check_tree(project):
    """Refuse a dirty tree: uncommitted work would not be in the measured commit."""
    if git(project, "rev-parse", "--is-inside-work-tree", check=False).returncode != 0:
        raise Refusal(f"{project} is not a git repository.")
    status = git(project, "status", "--porcelain").stdout
    if status.strip():
        raise Refusal("The working tree has uncommitted changes. Commit or stash them first.")


def check_files(project, cfg):
    """Refuse a missing target or benchmark."""
    project = Path(project)
    for name in [cfg.target, *cfg.frozen]:
        if not (project / name).is_file():
            raise Refusal(f"{name} does not exist.")
        if git(project, "ls-files", "--error-unmatch", name, check=False).returncode != 0:
            raise Refusal(f"{name} is not committed. The run measures committed files only.")
    program = cfg.command[0]
    if not (shutil.which(program) or (project / program).is_file() or os.path.isfile(program)):
        raise Refusal(f"The benchmark program {program} does not exist.")


def check_noise(a, b, cfg):
    """Judge the baseline against itself. Return the detection limit, or refuse.

    `a` and `b` are two interleaved sets of baseline runs. The same runs feed
    the controls afterwards.
    """
    for runs in (a, b):
        failed = [r for r in runs if not r.ok]
        if failed:
            raise Refusal(f"The baseline benchmark failed: {failed[0].error}.")
    if len({r.outputs for r in [*a, *b]}) != 1:
        raise Refusal("The baseline outputs vary between identical runs. The identity check cannot work.")
    if statistics.median(r.metric for r in a) <= 0:
        raise Refusal("The baseline metric is not positive.")
    limit = decide(a, b, KeepRule(cfg.min_gain, cfg.confidence, cfg.direction)).detection_limit
    if limit is None or math.isinf(limit):
        raise Refusal(
            f"With {cfg.runs_per_side} runs per side no interval reaches a confidence of "
            f"{cfg.confidence}. Use at least {stats.min_runs(cfg.confidence)} runs per side."
        )
    if limit > cfg.min_gain:
        needed = math.ceil(cfg.runs_per_side * (limit / cfg.min_gain) ** 2)
        raise Refusal(
            f"The benchmark is too noisy. With {cfg.runs_per_side} runs per side it can detect "
            f"only {limit:.1%}, and the keep threshold is {cfg.min_gain:.1%}. Reduce the noise, "
            f"or raise runs_per_side to about {needed} (estimate)."
        )
    return limit
