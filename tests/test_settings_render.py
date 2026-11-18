#!/usr/bin/env python3
"""Isolated contract tests for bin/settings-render; no home settings are read."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RENDERER = ROOT / "bin" / "settings-render"


class SettingsRenderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="settings-render-test-")
        self.root = Path(self.temp.name)
        self.template = self.root / "template.json"
        self.overlay = self.root / "private.json"
        self.output = self.root / "home" / ".claude" / "settings.json"
        self.template.write_text(json.dumps({
            "model": "shared-model",
            "hooks": {"SessionStart": [{"command": "__HOME__/.claude/hooks/start"}]},
            "preferences": {"theme": "auto", "extensions": ["shared"]},
        }), encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(RENDERER), "--template", str(self.template),
             "--home", str(self.root / "home"), *args],
            capture_output=True, text=True, check=False,
        )

    def test_render_expands_home_and_preserves_shared_hooks(self) -> None:
        result = self.run_cli("--output", str(self.output))
        self.assertEqual(result.returncode, 0, result.stderr)
        rendered = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual(rendered["model"], "shared-model")
        self.assertEqual(rendered["hooks"]["SessionStart"][0]["command"],
                         str(self.root / "home" / ".claude" / "hooks" / "start"))

    def test_private_overlay_changes_preferences_not_shared_hooks(self) -> None:
        self.overlay.write_text(json.dumps({
            "model": "local-model",
            "preferences": {"theme": "dark", "fontSize": 14},
        }), encoding="utf-8")
        result = self.run_cli("--overlay", str(self.overlay), "--output", str(self.output))
        self.assertEqual(result.returncode, 0, result.stderr)
        rendered = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual(rendered["model"], "local-model")
        self.assertEqual(rendered["preferences"],
                         {"theme": "dark", "extensions": ["shared"], "fontSize": 14})
        self.assertTrue(rendered["hooks"]["SessionStart"])

    def test_missing_overlay_is_optional(self) -> None:
        result = self.run_cli("--overlay", str(self.root / "absent.json"),
                              "--output", str(self.output))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(self.output.read_text(encoding="utf-8"))["model"],
                         "shared-model")

    def test_digest_matches_exact_written_bytes(self) -> None:
        written = self.run_cli("--output", str(self.output))
        digest = self.run_cli("--digest")
        self.assertEqual(written.returncode, 0, written.stderr)
        self.assertEqual(digest.returncode, 0, digest.stderr)
        self.assertEqual(digest.stdout.strip(), hashlib.sha256(self.output.read_bytes()).hexdigest())

    def test_invalid_overlay_does_not_replace_existing_output(self) -> None:
        self.output.parent.mkdir(parents=True)
        before = b"previous-installation\n"
        self.output.write_bytes(before)
        self.overlay.write_text("not-json", encoding="utf-8")
        result = self.run_cli("--overlay", str(self.overlay), "--output", str(self.output))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.output.read_bytes(), before)

    def test_non_object_overlay_is_rejected(self) -> None:
        self.overlay.write_text("[]", encoding="utf-8")
        result = self.run_cli("--overlay", str(self.overlay), "--digest")
        self.assertEqual(result.returncode, 1)
        self.assertIn("root must be a JSON object", result.stderr)

    def test_empty_home_placeholder_is_not_left_behind(self) -> None:
        self.template.write_text('{"path":"__HOME__/tool"}', encoding="utf-8")
        result = self.run_cli("--home", "", "--digest")
        self.assertEqual(result.returncode, 1)
        self.assertIn("non-empty directory", result.stderr)


if __name__ == "__main__":
    unittest.main()
