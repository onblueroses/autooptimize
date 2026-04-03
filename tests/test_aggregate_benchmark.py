import unittest

from scripts.aggregate_benchmark import aggregate_results, calculate_stats, generate_markdown


class AggregateBenchmarkTests(unittest.TestCase):
    def test_calculate_stats_uses_sample_stddev(self) -> None:
        stats = calculate_stats([1.0, 2.0, 3.0])

        self.assertEqual(
            stats,
            {"mean": 2.0, "stddev": 1.0, "min": 1.0, "max": 3.0},
        )

    def test_aggregate_results_computes_config_deltas(self) -> None:
        summary = aggregate_results(
            {
                "with_skill": [
                    {"pass_rate": 0.75, "time_seconds": 10.0, "tokens": 120},
                    {"pass_rate": 0.5, "time_seconds": 14.0, "tokens": 80},
                ],
                "without_skill": [
                    {"pass_rate": 0.25, "time_seconds": 15.0, "tokens": 90},
                    {"pass_rate": 0.25, "time_seconds": 17.0, "tokens": 110},
                ],
            }
        )

        self.assertEqual(summary["with_skill"]["pass_rate"]["mean"], 0.625)
        self.assertEqual(summary["without_skill"]["pass_rate"]["mean"], 0.25)
        self.assertEqual(summary["delta"], {"pass_rate": "+0.38", "time_seconds": "-4.0", "tokens": "+0"})

    def test_generate_markdown_uses_human_labels(self) -> None:
        markdown = generate_markdown(
            {
                "metadata": {
                    "skill_name": "sample-skill",
                    "executor_model": "test-model",
                    "timestamp": "2026-04-03T00:00:00Z",
                    "evals_run": [1, 2],
                    "runs_per_configuration": 3,
                },
                "run_summary": {
                    "with_skill": {
                        "pass_rate": {"mean": 0.8, "stddev": 0.1},
                        "time_seconds": {"mean": 12.0, "stddev": 1.0},
                        "tokens": {"mean": 100.0, "stddev": 5.0},
                    },
                    "without_skill": {
                        "pass_rate": {"mean": 0.5, "stddev": 0.0},
                        "time_seconds": {"mean": 14.0, "stddev": 0.5},
                        "tokens": {"mean": 120.0, "stddev": 4.0},
                    },
                    "delta": {
                        "pass_rate": "+0.30",
                        "time_seconds": "-2.0",
                        "tokens": "-20",
                    },
                },
                "notes": [],
            }
        )

        self.assertIn("| Metric | With Skill | Without Skill | Delta |", markdown)
        self.assertIn("| Pass Rate | 80% +/- 10% | 50% +/- 0% | +0.30 |", markdown)
