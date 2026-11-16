# Changelog

## v3.0 - A loop that can reject a change (2026-11)

Version 3 replaces the method documents with a small runnable loop that enforces its rules in code.

- **Frozen contract.** The loop hashes the benchmark, the test inputs, the config and the scorer
  before the first run. It refuses when one of them changes during the run.
- **Preflight.** The loop refuses a dirty tree, a missing benchmark and a benchmark that is too
  noisy for the keep threshold. The refusal comes before any proposer call.
- **Controls.** Before real trials, the scorer must judge five known cases correctly. The cases
  are no change, a known gain, a known regression, changed outputs and a failed run.
- **Keep rule.** KEEP needs a gain outside an exact rank interval and at or above the threshold.
  The outputs on the test set must be identical. The Hodges-Lehmann estimate replaces the mean
  and signal-to-noise ratio (SNR) rule of v2 because timing noise has outliers.
- **Null reports.** INCONCLUSIVE states its detection limit. A run without a KEEP must state its
  limit, controls, untried arms and next route. Every number in the report has a kind.
- **Fail closed.** Every failure is a failed trial. Every abnormal end is exit status 2.
- **No unmeasured limits.** Every number in the config carries its source. `LIMITS.md` lists them,
  and a test checks the table. The v2 defaults with no source (failure caps, experiment caps, run
  counts) are gone.
- **Durable record.** An fsynced JSONL ledger, artifacts for every trial, and a hash manifest that
  the loop checks before it removes its worktrees.
- **Demo.** `python3 -m autooptimize demo` shows KEEP, DISCARD, INCONCLUSIVE and FAILED without an
  API key.
- **Removed.** The method documents (`SETUP.md`, the methodology, hypothesis engine, spec format,
  eval methodology and evaluator framings) and the skill-trigger eval scripts. They are in the git
  history before this release.

## v2.0 - Spec Engine (2026-04-04)

Autooptimize now generates optimization specs instead of expecting you to follow methodology docs manually.

- **`spec-format.md`** - Spec template with completeness checklist, antipatterns, executor interface, multi-agent workflow.
- **`hypothesis-engine.md`** - Hypothesis generation protocol: T0-T4 tiers with explicit exhaustion conditions, experiment log synthesis, quality rubric, lightweight feedback logging.
- **Statistical additions** to `eval-methodology.md` - Paired bootstrap CI, adaptive sample sizing, SPRT early stopping, evaluation composition, noise floor detection.
- **Feedback logging** - `hypothesis_feedback` entries in the enrichment log track predicted vs actual impact and discovered constraints.
- **SETUP.md rewrite** - Bootstrap generates a spec on first run.
- **Cross-references** between new and existing docs.

## v1.0 - Methodology Docs (2026-03-31)

Initial release. Core optimization loop, eval methodology, evaluator framings, Python eval scripts.
