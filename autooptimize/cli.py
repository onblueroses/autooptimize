"""Command line. Exit 0 means the run ended normally. Every other end is exit 2."""

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from . import loop
from . import report as report_mod
from .config import load_config
from .errors import Refusal
from .ledger import read
from .proposers import ClaudeProposer, ScriptedProposer

DEMO = Path(__file__).parent / "demo"
REFUSED = 2


def _say(text, stream=None):
    try:
        print(text, file=stream or sys.stdout, flush=True)
    except Exception:
        pass  # Output is optional work. It cannot change the exit status.


def _parser():
    p = argparse.ArgumentParser(prog="autooptimize", description="Measure, change, evaluate, keep or discard.")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="run the loop on a project")
    r.add_argument("--project", default=".", help="git repository to optimize")
    r.add_argument("--config", default="autooptimize.json", help="config file, relative to the project")
    r.add_argument("--proposer", choices=["claude", "scripted"], default="claude")
    r.add_argument("--proposals", help="folder of proposal files for --proposer scripted")
    r.add_argument("--model", help="model for the claude CLI")
    r.add_argument("--iterations", type=int, help="number of trials. Required for --proposer claude")

    d = sub.add_parser("demo", help="run the bundled demo with scripted proposals, no API key")
    d.add_argument("--dir", help="folder for the demo project (default: a new temporary folder)")

    c = sub.add_parser("check-config", help="validate a config, including the sources of its limits")
    c.add_argument("config")

    rep = sub.add_parser("report", help="print the report of a ledger")
    rep.add_argument("ledger")
    return p


def _run(args):
    project = Path(args.project).resolve()
    config = project / args.config
    if args.proposer == "scripted":
        if not args.proposals:
            raise Refusal("--proposer scripted needs --proposals.")
        proposer = ScriptedProposer(args.proposals)
    else:
        if args.iterations is None:
            raise Refusal("Give --iterations. autooptimize sets no default number of trials.")
        cfg = load_config(config)
        proposer = ClaudeProposer(cfg.target, cfg.direction, cfg.arms, args.model,
                                  timeout_s=cfg.proposer_timeout_s)
    loop.run(project, config, proposer, args.iterations, out=_say)


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _demo(args):
    folder = Path(args.dir) if args.dir else Path(tempfile.mkdtemp(prefix="autooptimize-demo-"))
    if folder.exists() and any(folder.iterdir()):
        raise Refusal(f"{folder} is not empty.")
    shutil.copytree(DEMO / "project", folder, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))
    _git(folder, "init", "-q", "-b", "main")
    _git(folder, "config", "user.name", "autooptimize demo")
    _git(folder, "config", "user.email", "demo@example.invalid")
    _git(folder, "add", ".")
    _git(folder, "commit", "-q", "-m", "Demo baseline")
    _say(f"demo project: {folder}")
    loop.run(folder, folder / "autooptimize.json", ScriptedProposer(DEMO / "proposals"), out=_say)


def _dispatch(argv):
    args = _parser().parse_args(argv)
    if args.cmd == "run":
        _run(args)
    elif args.cmd == "demo":
        _demo(args)
    elif args.cmd == "check-config":
        load_config(args.config)
        _say("config ok: every limit has a source")
    elif args.cmd == "report":
        _say(report_mod.render(report_mod.build(read(args.ledger))))
    return 0


def main(argv=None):
    status = REFUSED
    try:
        status = _dispatch(argv)
    except Refusal as exc:
        _say(f"REFUSED: {exc}", sys.stderr)
    except SystemExit as exc:  # argparse
        status = exc.code if exc.code == 0 else REFUSED
    except BaseException as exc:  # fail closed: a crash or an interrupt is a refusal
        _say(f"REFUSED: internal error: {type(exc).__name__}: {exc}", sys.stderr)
    return status
