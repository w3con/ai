#!/usr/bin/env python3
"""Tests for the generic relation-config helper against synthetic state."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin" / "relation-config-helper"


class RelationConfigHelperTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="relation-config-helper-")
        self.root = Path(self.temp.name)
        metadata = self.root / ".ai"
        (metadata / "relations").mkdir(parents=True)
        (metadata / ".sync-state.json").write_text(json.dumps({
            "DOC-1": {"collection": "zeta", "parent_id": None},
            "DOC-2": {"collection": "zeta", "parent_id": "DOC-1"},
            "DOC-3": {"collection": "alpha", "parent_id": None},
        }), encoding="utf-8")
        (metadata / "relations" / "DOC-1.json").write_text(
            json.dumps({"doc_id": "DOC-1", "title": "Parent document"}), encoding="utf-8")
        (metadata / "relations" / "DOC-2.json").write_text(
            json.dumps({"doc_id": "DOC-2", "title": "Child document"}), encoding="utf-8")
        (metadata / "relation-config.json").write_text(json.dumps({
            "skip_collections": ["alpha"], "skip_doc_ids": ["DOC-3"],
            "skip_subtrees": ["DOC-1"],
            "force_sonnet": {"collections": ["zeta"], "parents": ["DOC-1"]},
        }), encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_helper(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, str(SCRIPT), "--root", str(self.root), *args],
                              capture_output=True, text=True, check=False)

    def test_tree_defaults_to_branches_and_displays_private_config(self) -> None:
        result = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        tree = result.stdout.split("=== Current relation configuration ===", 1)[0]
        self.assertIn("DOC-1", tree)
        self.assertNotIn("DOC-3", tree)
        self.assertIn("skip_collections", result.stdout)

    def test_full_mode_includes_leaf_documents(self) -> None:
        result = self.run_helper("--full")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("DOC-2", result.stdout)

    def test_missing_state_reports_clear_cli_error(self) -> None:
        (self.root / ".ai" / ".sync-state.json").unlink()
        result = self.run_helper()
        self.assertEqual(result.returncode, 2)
        self.assertIn("relation state is not present", result.stderr)


if __name__ == "__main__":
    unittest.main()
