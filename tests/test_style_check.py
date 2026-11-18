#!/usr/bin/env python3
"""Isolated style-check tests with synthetic public instruction files."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin" / "style-check"


def legacy_style_instruction() -> str:
    return "".join(chr(codepoint) for codepoint in (
        0x0421, 0x0442, 0x0438, 0x043B, 0x044C, 0x0020,
        0x043E, 0x0431, 0x0449, 0x0435, 0x043D, 0x0438, 0x044F,
    ))


class StyleCheckTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="style-check-test-")
        self.base = Path(self.temp.name)
        self.root = self.base / "checkout"
        (self.root / "bin").mkdir(parents=True)
        (self.root / "hooks").mkdir()
        (self.root / "lib").mkdir()
        shutil.copyfile(SCRIPT, self.root / "bin" / "style-check")
        shutil.copyfile(ROOT / "lib" / "__init__.py", self.root / "lib" / "__init__.py")
        shutil.copyfile(ROOT / "lib" / "private_config.py", self.root / "lib" / "private_config.py")
        (self.root / "STYLE.md").write_text("# Public writing guidance\n", encoding="utf-8")
        (self.root / "CLAUDE.md").write_text("# Toolkit\n\n@STYLE.md\n", encoding="utf-8")
        self.home = self.base / "home"
        self.home.mkdir()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_check(self) -> subprocess.CompletedProcess[str]:
        env = dict(os.environ, HOME=str(self.home))
        env.pop("AI_TOOLKIT_CONFIG", None)
        return subprocess.run([sys.executable, str(self.root / "bin" / "style-check"), "--quiet"],
                              capture_output=True, text=True, env=env, check=False)

    def test_style_source_and_import_are_accepted(self) -> None:
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_duplicate_style_rule_is_rejected_without_printing_source_text(self) -> None:
        finding = self.root / "hooks" / "example.md"
        finding.write_text("Use a complete sentence in this instruction.\n", encoding="utf-8")
        result = self.run_check()
        self.assertEqual(result.returncode, 3)
        self.assertIn("hooks/example.md:1", result.stderr)
        self.assertNotIn("Use a complete sentence", result.stderr)

    def test_legacy_input_marker_still_matches(self) -> None:
        finding = self.root / "hooks" / "legacy-input.md"
        finding.write_text(legacy_style_instruction() + "\n", encoding="utf-8")
        result = self.run_check()
        self.assertEqual(result.returncode, 3)
        self.assertIn("hooks/legacy-input.md:1", result.stderr)
        self.assertNotIn(legacy_style_instruction(), result.stderr)


if __name__ == "__main__":
    unittest.main()
