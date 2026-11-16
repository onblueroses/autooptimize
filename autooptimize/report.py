"""Build the run report from the ledger.

Every number carries a kind: measured, estimate, required or unknown.
Measured numbers point to the ledger line that holds them.
A run without a KEEP is a null. The report refuses to call it "no effect"
unless it states the detection limit, the controls, the untried arms and the
next route.
"""

from .decide import INCONCLUSIVE, KEEP

KINDS = ("measured", "estimate", "required", "unknown")
NULL_FIELDS = ("detection_limit", "controls_fired", "untried_arms", "next_route")


class ReportError(Exception):
    pass


def _pct(x):
    return "n/a" if x is None else f"{x:+.1%}"


def build(rows):
    """rows: [(line_number, record)] from ledger.read()."""
    if not rows:
        raise ReportError("The ledger is empty.")
    hashes = {r.get("contract") for _, r in rows}
    if len(hashes) != 1:
        raise ReportError(
            f"The ledger mixes {len(hashes)} contract hashes. Results under different contracts "
            f"are not comparable."
        )
    by_kind = {}
    for line, rec in rows:
        by_kind.setdefault(rec["kind"], []).append((line, rec))
    start = by_kind.get("start", [(None, {})])[0][1]
    rule = start.get("keep_rule", {})
    controls = [rec for _, rec in by_kind.get("control", [])]
    trials = by_kind.get("trial", [])

    numbers = []

    def number(name, value, kind, source):
        if kind not in KINDS:
            raise ReportError(f"{name} has kind {kind}. Allowed: {', '.join(KINDS)}.")
        numbers.append({"name": name, "value": value, "kind": kind, "source": source})

    for key in ("min_gain", "confidence", "runs_per_side"):
        if key in rule:
            number(f"keep_rule.{key}", rule[key]["value"], "required", rule[key]["source"])
    preflight_limit = None
    for line, rec in by_kind.get("preflight", []):
        preflight_limit = rec["detection_limit"]
        number("baseline median metric", f"{rec['baseline_median']:.6g}", "measured", f"ledger.jsonl:{line}")
        number("baseline detection limit", f"{preflight_limit:.1%}", "measured", f"ledger.jsonl:{line}")
    kept_factor = 1.0
    trial_rows = []
    for line, rec in trials:
        trial_rows.append(dict(rec, line=line))
        if rec["verdict"] == KEEP:
            kept_factor *= 1.0 - rec["gain"] if start.get("direction") == "lower" else 1.0 + rec["gain"]
            number(f"trial {rec['trial']} gain", _pct(rec["gain"]), "measured", f"ledger.jsonl:{line}")
    keeps = [t for t in trial_rows if t["verdict"] == KEEP]
    if keeps:
        total = 1.0 - kept_factor if start.get("direction") == "lower" else kept_factor - 1.0
        number(
            "total gain over the run", f"{total:+.1%}", "estimate",
            "product of the kept gains, each measured against its own baseline",
        )
    number("gain on inputs outside the frozen test set", "not measured", "unknown", "the run uses only the frozen inputs")
    number("behaviour outside the frozen test set", "not checked", "unknown", "the identity check covers only the frozen inputs")

    report = {
        "run": start.get("run"),
        "contract": hashes.pop(),
        "outcome": "improved" if keeps else "no effect found",
        "controls": controls,
        "trials": trial_rows,
        "numbers": numbers,
        "refusal": next((rec["reason"] for _, rec in by_kind.get("refusal", [])), None),
    }
    if not keeps:
        tried = {t.get("arm") for t in trial_rows}
        arms = start.get("arms") or []
        untried = [a for a in arms if a not in tried]
        limits = [t["detection_limit"] for t in trial_rows if t.get("detection_limit") is not None]
        limit = max(limits) if limits else preflight_limit
        runs = rule.get("runs_per_side", {}).get("value")
        report["null"] = {
            "detection_limit": None if limit is None else f"{limit:.1%} (measured)",
            "controls_fired": f"{sum(c['fired'] for c in controls)} of {len(controls)}" if controls else None,
            "untried_arms": ", ".join(untried) if untried else (
                "none of the listed arms remain" if arms else "unknown: the config lists no arms"
            ),
            "next_route": (
                f"try the untried arms, or raise runs_per_side from {runs} to {4 * runs} "
                f"to halve the detection limit (estimate)" if runs else None
            ),
        }
    return report


def render(report):
    out = [f"# autooptimize run {report['run']}", ""]
    out.append(f"Outcome: {report['outcome']}.")
    out.append(f"Contract: `{report['contract'][:16]}`.")
    if report.get("refusal"):
        out.append(f"Refused: {report['refusal']}")
    out += ["", "## Controls", "", "| control | expected | got | fired |", "|---|---|---|---|"]
    for c in report["controls"]:
        out.append(f"| {c['control']} | {c['expected']} | {c['got']} | {'yes' if c['fired'] else 'NO'} |")
    out += [
        "", "## Trials", "",
        "| trial | arm | verdict | gain | interval | detection limit | reason | ledger |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for t in report["trials"]:
        interval = "n/a" if t.get("gain_low") is None else f"{_pct(t['gain_low'])} to {_pct(t['gain_high'])}"
        limit = "n/a" if t.get("detection_limit") is None else f"{t['detection_limit']:.1%}"
        out.append(
            f"| {t['trial']} | {t['arm']} | {t['verdict']} | {_pct(t.get('gain'))} | {interval} "
            f"| {limit} | {t['reason']} | line {t['line']} |"
        )
    out += ["", "## Numbers", "", "| quantity | value | kind | source |", "|---|---|---|---|"]
    for n in report["numbers"]:
        out.append(f"| {n['name']} | {n['value']} | {n['kind']} | {n['source']} |")
    if report["outcome"] == "no effect found":
        null = report.get("null") or {}
        missing = [f for f in NULL_FIELDS if not null.get(f)]
        if missing:
            raise ReportError(f"A null report needs {', '.join(missing)}. The report is not printed.")
        out += [
            "", "## Null", "",
            "No trial was kept. This is a checkpoint, not a conclusion.", "",
            f"- Detection limit: {null['detection_limit']}. A smaller effect can exist.",
            f"- Controls fired: {null['controls_fired']}.",
            f"- Untried arms: {null['untried_arms']}.",
            f"- Next route: {null['next_route']}.",
        ]
    inconclusive = [t for t in report["trials"] if t["verdict"] == INCONCLUSIVE]
    if inconclusive:
        out += ["", "INCONCLUSIVE means the trial could not see an effect above its detection limit."]
    return "\n".join(out) + "\n"
