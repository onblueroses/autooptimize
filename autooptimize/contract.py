"""The frozen contract: what a run may not change while it runs."""

import hashlib
import json
from pathlib import Path

from .decide import SCORER_VERSION, scorer_sha256
from .errors import Refusal


def sha256_file(path):
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError as exc:
        raise Refusal(f"Cannot read {path}: {exc}") from exc


def canonical(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def freeze(project, cfg, baseline_commit, out_path):
    """Write the contract and return (contract, its hash)."""
    project = Path(project)
    contract = {
        "version": 1,
        "target": cfg.target,
        "baseline": {"commit": baseline_commit, "target_sha256": sha256_file(project / cfg.target)},
        "benchmark": {
            "command": cfg.raw["benchmark"]["command"],
            "frozen": {f: sha256_file(project / f) for f in cfg.frozen},
        },
        "config": {"path": str(cfg.path), "sha256": sha256_file(cfg.path)},
        "scorer": {"version": SCORER_VERSION, "sha256": scorer_sha256()},
        "direction": cfg.direction,
        "keep_rule": cfg.raw["keep_rule"],
        "limits": {k: cfg.raw[k] for k in ("benchmark", "proposer") if k in cfg.raw},
    }
    digest = hashlib.sha256(canonical(contract).encode()).hexdigest()
    Path(out_path).write_text(json.dumps({"sha256": digest, "contract": contract}, indent=2) + "\n")
    return contract, digest


def verify(contract_path, expected_hash, roots):
    """Refuse when the contract file, the config, the scorer or a frozen file changed."""
    try:
        stored = json.loads(Path(contract_path).read_text())
        contract = stored["contract"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise Refusal(f"Cannot read the contract {contract_path}: {exc}") from exc
    digest = hashlib.sha256(canonical(contract).encode()).hexdigest()
    if digest != expected_hash or stored.get("sha256") != expected_hash:
        raise Refusal("The contract file changed during the run.")
    if sha256_file(contract["config"]["path"]) != contract["config"]["sha256"]:
        raise Refusal("The config changed during the run. Start a new run with a new contract.")
    if scorer_sha256() != contract["scorer"]["sha256"]:
        raise Refusal("The scorer code changed during the run. Start a new run with a new contract.")
    for root in roots:
        for name, sha in contract["benchmark"]["frozen"].items():
            if sha256_file(Path(root) / name) != sha:
                raise Refusal(f"{name} changed in {root} during the run. The contract freezes it.")
    return contract
