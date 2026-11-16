"""Rule: install no limit without its source."""

import ast
import json
import re
import unittest

from helpers import ROOT
from autooptimize.config import check_limits, load_config
from autooptimize.errors import Refusal

DEMO_CONFIG = ROOT / "autooptimize" / "demo" / "project" / "autooptimize.json"


def limits_table():
    """Names in the first column of LIMITS.md."""
    names = set()
    for line in (ROOT / "LIMITS.md").read_text().splitlines():
        match = re.match(r"\|\s*`([^`]+)`\s*\|", line)
        if match:
            names.add(match.group(1))
    return names


def config_numbers(node, path=""):
    if isinstance(node, dict):
        if "value" in node:
            yield path
            return
        for key, child in node.items():
            yield from config_numbers(child, f"{path}.{key}" if path else key)
    elif isinstance(node, list):
        for child in node:
            yield from config_numbers(child, path)


def code_constants():
    """Module-level UPPER_CASE names bound to a number in the package."""
    found = set()
    for path in (ROOT / "autooptimize").glob("*.py"):
        for node in ast.parse(path.read_text()).body:
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
                value = node.value.value
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    for t in node.targets:
                        if isinstance(t, ast.Name) and t.id.isupper():
                            found.add(t.id)
    return found


def missing(names):
    return sorted(set(names) - limits_table())


class SourcedLimits(unittest.TestCase):
    def test_bare_number_is_refused(self):
        with self.assertRaises(Refusal):
            check_limits({"benchmark": {"timeout_s": 60}})

    def test_number_without_source_is_refused(self):
        with self.assertRaises(Refusal):
            check_limits({"timeout_s": {"value": 60}})

    def test_source_of_an_unknown_kind_is_refused(self):
        for source in ("guess: feels safe", "measured:", "60 seconds", ""):
            with self.subTest(source), self.assertRaises(Refusal):
                check_limits({"timeout_s": {"value": 60, "source": source}})

    def test_sourced_numbers_pass(self):
        for kind in ("measured", "system", "ruling"):
            check_limits({"timeout_s": {"value": 60, "source": f"{kind}: reason"}})

    def test_demo_config_loads(self):
        load_config(DEMO_CONFIG)


class LimitsTable(unittest.TestCase):
    def test_every_config_number_has_a_row(self):
        names = list(config_numbers(json.loads(DEMO_CONFIG.read_text())))
        self.assertTrue(names)
        self.assertEqual(missing(names), [])

    def test_every_code_constant_has_a_row(self):
        names = code_constants()
        self.assertIn("MIN_RUNS_PER_SIDE", names)
        self.assertEqual(missing(names), [])

    def test_the_check_finds_an_unlisted_limit(self):
        self.assertEqual(missing(["keep_rule.min_gain", "MAX_TRIALS_NOBODY_MEASURED"]),
                         ["MAX_TRIALS_NOBODY_MEASURED"])


if __name__ == "__main__":
    unittest.main()
