#!/usr/bin/env python3
"""Private-config-only tests for safe style-setting migration."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin" / "style-migrate"


class StyleMigrateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="style-migrate-test-")
        self.root = Path(self.temp.name)
        self.settings = self.root / "project" / ".claude" / "settings.local.json"
        self.settings.parent.mkdir(parents=True)
        self.settings.write_text('{"theme":"dark","outputStyle":"legacy"}\n',
                                 encoding="utf-8")
        self.config = self.root / "config.json"
        self.recovery = self.root / "recovery"
        self.write_config()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_config(self, style_settings: list[str] | None = None) -> None:
        self.config.write_text(json.dumps({
            "style_settings": style_settings if style_settings is not None else [str(self.settings)],
            "style_recovery_root": str(self.recovery),
        }), encoding="utf-8")

    def run_tool(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = dict(os.environ, AI_TOOLKIT_CONFIG=str(self.config))
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True,
                              text=True, env=env, check=False)

    def test_default_is_non_mutating_preview(self) -> None:
        before = self.settings.read_bytes()
        result = self.run_tool()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("would preserve a backup", result.stdout)
        self.assertEqual(self.settings.read_bytes(), before)
        self.assertFalse(self.recovery.exists())

    def test_apply_backs_up_and_removes_only_legacy_style_key(self) -> None:
        before = self.settings.read_bytes()
        result = self.run_tool("--apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.settings.exists() and
                         "outputStyle" in self.settings.read_text(encoding="utf-8"))
        data = json.loads(self.settings.read_text(encoding="utf-8"))
        self.assertEqual(data, {"theme": "dark"})
        backups = list(self.recovery.glob("*.backup"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), before)

    def test_no_configured_paths_means_no_home_scan(self) -> None:
        self.write_config([])
        result = self.run_tool("--apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("no declared settings", result.stdout)
        self.assertIn("outputStyle", self.settings.read_text(encoding="utf-8"))

    def test_invalid_settings_are_preserved_and_reported(self) -> None:
        self.settings.write_text("not-json", encoding="utf-8")
        result = self.run_tool("--apply")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.settings.read_text(encoding="utf-8"), "not-json")


if __name__ == "__main__":
    unittest.main()
