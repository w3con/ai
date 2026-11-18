#!/usr/bin/env python3
"""Synthetic checkout tests for the generic Markdown knowledge-base indexer."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin" / "kb-index"


class KnowledgeIndexTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="kb-index-test-")
        self.root = Path(self.temp.name)
        self.kb = self.root / "kb"
        (self.kb / "zeta").mkdir(parents=True)
        (self.kb / "alpha").mkdir()
        (self.kb / "zeta" / "second.md").write_text(
            "---\ntitle: Second\ntype: note\nai:\n  summary: Second synthetic item\n  domains: [architecture]\n---\nText.\n",
            encoding="utf-8")
        (self.kb / "alpha" / "first.md").write_text(
            "---\ntitle: First\ntype: note\nai:\n  summary: First synthetic item\n  domains: [process]\n---\nText.\n",
            encoding="utf-8")
        (self.kb / "_private.md").write_text("not indexed", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_index(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = dict(os.environ)
        env.pop("AI_TOOLKIT_CONFIG", None)
        return subprocess.run([str(SCRIPT), "--root", str(self.root), *args],
                              capture_output=True, text=True, env=env, check=False)

    def test_generate_index_from_arbitrary_checkout_root(self) -> None:
        result = self.run_index()
        self.assertEqual(result.returncode, 0, result.stderr)
        content = (self.kb / "_index.md").read_text(encoding="utf-8")
        self.assertIn("# Knowledge Base — Index", content)
        self.assertIn("[[first|First]]", content)
        self.assertIn("[[second|Second]]", content)
        self.assertNotIn("_private", content)

    def test_check_mode_reports_stale_index_without_writing(self) -> None:
        old = "old-index\n"
        (self.kb / "_index.md").write_text(old, encoding="utf-8")
        result = self.run_index("--check")
        self.assertEqual(result.returncode, 1)
        self.assertEqual((self.kb / "_index.md").read_text(encoding="utf-8"), old)

    def test_check_mode_passes_after_generation(self) -> None:
        self.assertEqual(self.run_index().returncode, 0)
        check = self.run_index("--check")
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)

    def test_private_collection_order_is_optional(self) -> None:
        private = self.root / ".private"
        private.mkdir()
        (private / "config.json").write_text(json.dumps({
            "knowledge_base": {"collection_order": ["zeta", "alpha"]},
        }), encoding="utf-8")
        result = self.run_index()
        self.assertEqual(result.returncode, 0, result.stderr)
        content = (self.kb / "_index.md").read_text(encoding="utf-8")
        self.assertLess(content.index("## zeta"), content.index("## alpha"))


if __name__ == "__main__":
    unittest.main()
