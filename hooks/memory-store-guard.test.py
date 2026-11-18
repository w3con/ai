#!/usr/bin/env python3
"""Scratch-home tests for the configurable private-memory write guard."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "hooks" / "memory-store-guard.sh"


class MemoryStoreGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="memory-store-guard-")
        self.base = Path(self.temp.name)
        self.home = self.base / "home"
        self.home.mkdir()
        self.store = self.base / "private-memory"
        self.store.mkdir()
        self.projects = self.home / ".claude" / "projects"
        self.project = self.projects / "synthetic-project" / "memory"
        self.project.mkdir(parents=True)
        self.link_project = self.projects / "synthetic-link" / "memory"
        self.link_project.parent.mkdir(parents=True)
        self.link_project.symlink_to(self.store, target_is_directory=True)
        self.config = self.base / "config.json"
        self.config.write_text(json.dumps({"memory_root": str(self.store)}), encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def verdict(self, tool: str, path: str, *, bypass: bool = False) -> str:
        payload = json.dumps({"tool_name": tool, "tool_input": {"file_path": path}})
        env = dict(os.environ, HOME=str(self.home), AI_TOOLKIT_CONFIG=str(self.config))
        if bypass:
            env["CLAUDE_GATE_BYPASS"] = "1"
        else:
            env.pop("CLAUDE_GATE_BYPASS", None)
        result = subprocess.run(["bash", str(HOOK)], input=payload, capture_output=True,
                                text=True, env=env, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"]

    def test_direct_private_store_write_is_allowed(self) -> None:
        self.assertEqual(self.verdict("Write", str(self.store / "note.md")), "allow")

    def test_write_through_project_memory_link_resolves_to_private_store(self) -> None:
        self.assertEqual(self.verdict("Write", str(self.link_project / "note.md")), "allow")

    def test_real_project_memory_directory_is_denied(self) -> None:
        self.assertEqual(self.verdict("Edit", str(self.project / "note.md")), "deny")

    def test_nested_project_memory_is_denied(self) -> None:
        nested = self.project / "nested" / "note.md"
        self.assertEqual(self.verdict("Write", str(nested)), "deny")

    def test_dotdot_resolving_to_project_memory_is_denied(self) -> None:
        path = self.projects / "synthetic-project" / "memory" / ".." / "memory" / "x.md"
        self.assertEqual(self.verdict("Write", str(path)), "deny")

    def test_unrelated_path_is_allowed(self) -> None:
        self.assertEqual(self.verdict("Write", str(self.base / "unrelated.md")), "allow")

    def test_other_tool_is_not_gated(self) -> None:
        self.assertEqual(self.verdict("Bash", str(self.project / "note.md")), "allow")
        self.assertEqual(self.verdict("Read", str(self.project / "note.md")), "allow")

    def test_explicit_bypass_allows_a_project_memory_write(self) -> None:
        self.assertEqual(self.verdict("Write", str(self.project / "note.md"), bypass=True),
                         "allow")

    def test_invalid_payload_fails_closed(self) -> None:
        env = dict(os.environ, HOME=str(self.home), AI_TOOLKIT_CONFIG=str(self.config))
        result = subprocess.run(["bash", str(HOOK)], input="", capture_output=True,
                                text=True, env=env, check=False)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"],
                         "deny")

    def test_malformed_private_config_fails_closed_for_writes(self) -> None:
        self.config.write_text("{invalid", encoding="utf-8")
        self.assertEqual(self.verdict("Write", str(self.store / "note.md")), "deny")


if __name__ == "__main__":
    unittest.main()
