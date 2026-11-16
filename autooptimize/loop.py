"""The loop: freeze, preflight, controls, then propose, measure and decide.

Layout of one run under <project>/.autooptimize/runs/<run-id>/:

  contract.json    frozen before the first measurement
  ledger.jsonl     one record per step, fsynced
  preflight/       raw baseline runs (sides a and b), reused by the controls
  trial-NNN/       proposal, candidate file, diff and raw runs
  report.md        written from the ledger
  manifest.json    sha256 of every artifact
  DONE             written after the manifest checks out

Kept changes are commits on the branch autooptimize/<run-id>. The project's
own checkout is never changed.
"""

import json
import os
import shutil
import statistics
import time
from pathlib import Path

from . import contract as contract_mod
from . import report as report_mod
from .bench import run_once
from .config import load_config
from .controls import run_controls
from .decide import FAILED, KEEP, KeepRule, Verdict, decide
from .errors import Refusal
from .ledger import Ledger, read
from .preflight import check_files, check_noise, check_tree, git
from .proposers import ProposalError

WORKDIR = ".autooptimize"


def _ensure_excluded(project):
    exclude = Path(git(project, "rev-parse", "--git-path", "info/exclude").stdout.strip())
    exclude = exclude if exclude.is_absolute() else Path(project) / exclude
    exclude.parent.mkdir(parents=True, exist_ok=True)
    text = exclude.read_text() if exclude.exists() else ""
    if f"/{WORKDIR}/" not in text.split():
        with open(exclude, "a") as handle:
            handle.write(("" if text.endswith("\n") or not text else "\n") + f"/{WORKDIR}/\n")


def _save_run(folder, name, run):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}.json").write_text(json.dumps(run.to_dict(), indent=2) + "\n")


def _measure(cfg, sides, folder):
    """Run each side runs_per_side times, interleaved. Stop a side's trial at its first failure."""
    results = {name: [] for name in sides}
    for i in range(cfg.runs_per_side):
        for name, cwd in sides.items():
            run = run_once(cfg.command, cwd, cfg.benchmark_timeout_s)
            _save_run(folder, f"{name}-{i + 1}", run)
            results[name].append(run)
            if not run.ok:
                return results
    return results


def _write_manifest(run_dir):
    files = sorted(
        p for p in run_dir.rglob("*")
        if p.is_file()
        and p.name not in ("manifest.json", "DONE")
        and p.relative_to(run_dir).parts[0] not in ("best", "cand")  # scratch worktrees
    )
    manifest = {str(p.relative_to(run_dir)): contract_mod.sha256_file(p) for p in files}
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    for name, sha in manifest.items():
        if contract_mod.sha256_file(run_dir / name) != sha:
            raise Refusal(f"The artifact {name} does not match its manifest entry.")
    (run_dir / "DONE").write_text(f"{len(manifest)} artifacts verified\n")


def _try(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except Exception:
        pass  # The refusal stands even when its record cannot be written.


def run(project, config_path, proposer, iterations=None, out=print, decide_fn=decide):
    """Run the loop. Return the run folder. Raise Refusal on every stop that is not a normal end."""
    project = Path(project).resolve()
    cfg = load_config(Path(config_path).resolve())
    _ensure_excluded(project)
    check_tree(project)
    check_files(project, cfg)

    run_id = time.strftime("%Y%m%dT%H%M%S") + "-" + os.urandom(3).hex()
    run_dir = project / WORKDIR / "runs" / run_id
    run_dir.mkdir(parents=True)
    head = git(project, "rev-parse", "HEAD").stdout.strip()
    contract_path = run_dir / "contract.json"
    _, chash = contract_mod.freeze(project, cfg, head, contract_path)
    ledger = Ledger(run_dir / "ledger.jsonl", run_id, chash)
    try:
        return _run(project, cfg, proposer, iterations, out, decide_fn, run_id, run_dir, head,
                    contract_path, chash, ledger)
    except Refusal as exc:
        _try(ledger.append, "refusal", reason=str(exc))
        raise
    except Exception as exc:
        _try(ledger.append, "refusal", reason=f"internal error: {type(exc).__name__}: {exc}")
        raise Refusal(f"internal error: {type(exc).__name__}: {exc}") from exc


def _run(project, cfg, proposer, iterations, out, decide_fn, run_id, run_dir, head,
         contract_path, chash, ledger):
    branch = f"autooptimize/{run_id}"
    best, cand = run_dir / "best", run_dir / "cand"
    git(project, "worktree", "add", "-q", "-b", branch, str(best), head)
    git(project, "worktree", "add", "-q", "--detach", str(cand), head)
    rule = KeepRule(cfg.min_gain, cfg.confidence, cfg.direction)
    ledger.append("start", branch=branch, baseline_commit=head, target=cfg.target,
                  direction=cfg.direction, keep_rule=cfg.raw["keep_rule"], arms=cfg.arms)
    out(f"run {run_id}: contract {chash[:12]} frozen, branch {branch}")

    def verify():
        contract_mod.verify(contract_path, chash, [project, best, cand])

    verify()
    pair = _measure(cfg, {"a": best, "b": best}, run_dir / "preflight")
    try:
        limit = check_noise(pair["a"], pair["b"], cfg)
    except Refusal as exc:
        ledger.append("preflight", ok=False, reason=str(exc),
                      runs={k: [r.to_dict() for r in v] for k, v in pair.items()})
        raise
    base_median = statistics.median(r.metric for r in pair["a"])
    ledger.append("preflight", ok=True, baseline_median=base_median, detection_limit=limit,
                  metrics={k: [r.metric for r in v] for k, v in pair.items()})
    out(f"preflight: baseline {base_median:.4g}, detection limit {limit:.1%}, "
        f"keep threshold {cfg.min_gain:.1%}")

    results = run_controls(pair["a"], pair["b"], rule, decide_fn=decide_fn)
    for r in results:
        ledger.append("control", **r)
    out(f"controls (shift {results[0]['shift']:.1%}): "
        + ", ".join(f"{r['control']}={'fired' if r['fired'] else 'MISSED'}" for r in results))
    missed = [r["control"] for r in results if not r["fired"]]
    if missed:
        raise Refusal(f"The controls {', '.join(missed)} did not fire. The rig cannot judge changes.")

    target_sha = contract_mod.sha256_file(best / cfg.target)
    history, trial = [], 0
    while iterations is None or trial < iterations:
        verify()
        if contract_mod.sha256_file(best / cfg.target) != target_sha:
            raise Refusal(f"{cfg.target} changed on the run branch outside the loop.")
        current = (best / cfg.target).read_text()
        try:
            proposal = proposer.propose(current, history)
            error = None
        except ProposalError as exc:
            proposal, error = None, str(exc)
        if proposal is None and error is None:
            break
        trial += 1
        tdir = run_dir / f"trial-{trial:03d}"
        tdir.mkdir()
        check_tree(project)  # the proposer must not touch the project
        if error is not None:
            verdict, arm, why = Verdict(FAILED, f"proposal failed: {error}"), "unknown", ""
            commit = None
        else:
            arm, why = proposal.arm, proposal.rationale
            (tdir / "proposal.json").write_text(json.dumps({"arm": arm, "why": why}, indent=2) + "\n")
            (tdir / Path(cfg.target).name).write_text(proposal.content)
            best_head = git(best, "rev-parse", "HEAD").stdout.strip()
            git(cand, "reset", "-q", "--hard", best_head)
            git(cand, "clean", "-q", "-fdx")
            (cand / cfg.target).write_text(proposal.content)
            (tdir / "diff.patch").write_text(git(cand, "diff").stdout)
            verify()
            sides = _measure(cfg, {"base": best, "cand": cand}, tdir / "runs")
            verdict = decide_fn(sides["base"], sides["cand"], rule)
            commit = None
            if verdict.verdict == KEEP:
                shutil.copyfile(cand / cfg.target, best / cfg.target)
                git(best, "commit", "-q", "-am", f"Keep trial {trial}: {arm}")
                git(best, "clean", "-q", "-fdx")
                target_sha = contract_mod.sha256_file(best / cfg.target)
                if target_sha != contract_mod.sha256_file(tdir / Path(cfg.target).name):
                    raise Refusal("The kept commit does not hold the measured candidate.")
                commit = git(best, "rev-parse", "HEAD").stdout.strip()
        record = dict(trial=trial, arm=arm, why=why, commit=commit, **verdict.to_dict())
        line = ledger.append("trial", **record)
        history.append(record)
        gain = "" if verdict.gain is None else f" gain {verdict.gain:+.1%} (limit {verdict.detection_limit:.1%})"
        out(f"trial {trial} [{arm}]: {verdict.verdict}{gain}: {verdict.reason} (ledger line {line})")

    ledger.append("end", trials=trial, branch=branch)
    text = report_mod.render(report_mod.build(read(ledger.path)))
    (run_dir / "report.md").write_text(text)
    _write_manifest(run_dir)
    git(project, "worktree", "remove", "--force", str(cand))
    git(project, "worktree", "remove", "--force", str(best))
    out("")
    out(text)
    out(f"artifacts: {run_dir}")
    out(f"kept commits: git log {branch}")
    return run_dir
