#!/usr/bin/env python3
"""No-network tests for deterministic paths through relation-build."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin" / "relation-build"


class RelationBuildTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="relation-build-test-")
        self.root = Path(self.temp.name)
        self.kb = self.root / "kb"
        self.kb.mkdir()
        self.doc = self.kb / "example.md"
        self.doc.write_text("---\ntitle: Example\ntype: note\nsource: synthetic\n---\nShort synthetic content.\n",
                            encoding="utf-8")
        self.logs = self.root / "logs"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_builder(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = dict(os.environ)
        env["AI_TOOLKIT_LOG_DIR"] = str(self.logs)
        env.pop("AI_TOOLKIT_CONFIG", None)
        return subprocess.run([str(SCRIPT), "--root", str(self.root), "--no-index",
                               "--ids", "kb/example.md", *args], capture_output=True,
                              text=True, env=env, check=False, timeout=20)

    def test_short_document_uses_deterministic_no_network_path(self) -> None:
        result = self.run_builder()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        content = self.doc.read_text(encoding="utf-8")
        self.assertIn("title: Example", content)
        self.assertIn("source: synthetic", content)
        self.assertIn("summary:", content)
        self.assertIn("<!-- relation-build:related-start -->", content)

    def test_checksum_makes_repeat_run_idempotent(self) -> None:
        self.assertEqual(self.run_builder().returncode, 0)
        first = self.doc.read_bytes()
        second = self.run_builder()
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertEqual(self.doc.read_bytes(), first)
        self.assertIn("skipped", second.stdout + second.stderr)

    def test_force_reprocesses_stored_checksum_without_network_for_short_doc(self) -> None:
        self.assertEqual(self.run_builder().returncode, 0)
        result = self.run_builder("--force")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("trivial", result.stdout + result.stderr)

    def test_external_configuration_can_skip_declared_collection(self) -> None:
        folder = self.kb / "internal"
        folder.mkdir()
        skipped = folder / "skip.md"
        skipped.write_text("---\ntitle: Skip\ntype: note\n---\nShort.\n", encoding="utf-8")
        private = self.root / ".private"
        private.mkdir()
        config = private / "config.json"
        config.write_text(json.dumps({
            "knowledge_base": {"skip_folders": ["internal"]},
        }), encoding="utf-8")
        result = self.run_builder()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("ai:", skipped.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
