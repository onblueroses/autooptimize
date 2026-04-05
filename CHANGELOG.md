# Changelog

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
