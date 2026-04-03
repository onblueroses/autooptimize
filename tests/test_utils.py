import tempfile
import unittest
from pathlib import Path

from scripts.utils import parse_skill_md


class ParseSkillMdTests(unittest.TestCase):
    def test_parses_single_line_frontmatter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp)
            content = """---
name: sample-skill
description: \"Runs a sample task\"
---

# sample-skill
"""
            (skill_dir / "SKILL.md").write_text(content)

            name, description, full_content = parse_skill_md(skill_dir)

            self.assertEqual(name, "sample-skill")
            self.assertEqual(description, "Runs a sample task")
            self.assertEqual(full_content, content)

    def test_parses_multiline_description_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp)
            (skill_dir / "SKILL.md").write_text(
                """---
name: sample-skill
description: |
  First line
  second line
---

# sample-skill
"""
            )

            name, description, _ = parse_skill_md(skill_dir)

            self.assertEqual(name, "sample-skill")
            self.assertEqual(description, "First line second line")

    def test_rejects_missing_frontmatter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp)
            (skill_dir / "SKILL.md").write_text("# sample-skill\n")

            with self.assertRaisesRegex(ValueError, "missing frontmatter"):
                parse_skill_md(skill_dir)
