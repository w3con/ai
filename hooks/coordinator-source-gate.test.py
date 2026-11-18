#!/usr/bin/env python3
"""Full synthetic decision matrix for configured coordinator source roots."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "hooks" / "coordinator-source-gate.sh"


class CoordinatorSourceGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="source-gate-contract-")
        self.base = Path(self.temp.name)
        self.workspace = self.base / "workspace"
        self.roots = [self.workspace / "service" / "src",
                      self.workspace / "client" / "src",
                      self.workspace / "viewer" / "src",
                      self.workspace / ".claude" / "worktrees" / "sample" / "service" / "src"]
        config_path = self.base / "private-config.json"
        config_path.write_text(json.dumps({
            "coordinator_source_roots": [str(path) for path in self.roots],
        }), encoding="utf-8")
        self.config_path = config_path

    def tearDown(self) -> None:
        self.temp.cleanup()

    def call(self, tool: str, path: str = "", *, agent_id: str | None = None,
             cwd: Path | None = None, env_extra: dict[str, str] | None = None,
             raw: str | None = None) -> tuple[str, str]:
        payload = {"tool_name": tool,
                   "tool_input": {"notebook_path" if tool == "NotebookEdit" else "file_path": path},
                   "cwd": str(cwd or self.workspace)}
        if agent_id:
            payload["agent_id"] = agent_id
        env = dict(os.environ)
        env["AI_TOOLKIT_CONFIG"] = str(self.config_path)
        env.pop("CLAUDE_GATE_BYPASS", None)
        env.pop("TOOLKIT_EXECUTOR", None)
        if env_extra:
            env.update(env_extra)
        result = subprocess.run(["bash", str(HOOK)],
                                input=raw if raw is not None else json.dumps(payload),
                                capture_output=True, text=True, env=env, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        decision = json.loads(result.stdout)["hookSpecificOutput"]
        return decision["permissionDecision"], decision.get("permissionDecisionReason", "")

    def test_coordinator_source_paths_are_denied_by_tool_and_root(self) -> None:
        cases = [
            ("Edit", self.roots[0] / "module" / "source.py"),
            ("Write", self.roots[0] / "main.py"),
            ("Write", self.roots[1] / "vendor" / "library.js"),
            ("Edit", self.roots[2] / "App.vue"),
            ("NotebookEdit", self.roots[0] / "scratch.ipynb"),
            ("Edit", "service/src/main.py"),
            ("Write", self.roots[3] / "main.py"),
        ]
        for tool, path in cases:
            with self.subTest(tool=tool, path=path):
                decision, reason = self.call(tool, str(path))
                self.assertEqual(decision, "deny")
                self.assertIn("executor", reason.lower())
                self.assertTrue(reason.strip().endswith("."))

    def test_denial_names_the_resolved_target(self) -> None:
        target = self.roots[0] / "nested" / "module.py"
        decision, reason = self.call("Edit", str(target))
        self.assertEqual(decision, "deny")
        self.assertIn(str(target), reason)

    def test_executor_agent_identity_allows_configured_source_edits(self) -> None:
        for tool, path in (("Edit", self.roots[0] / "module.py"),
                           ("Write", self.roots[1] / "main.ts"),
                           ("NotebookEdit", self.roots[2] / "scratch.ipynb")):
            with self.subTest(tool=tool):
                self.assertEqual(self.call(tool, str(path), agent_id="agent-synthetic")[0],
                                 "allow")

    def test_non_source_coordinator_paths_remain_allowed(self) -> None:
        paths = [
            self.workspace / "docs" / "tasks" / "TASK-1.md",
            self.workspace / "docs" / "features" / "feature.md",
            self.workspace / "kb" / "domain" / "topic.md",
            self.workspace / "bin" / "report",
            self.workspace / ".githooks" / "pre-commit",
            self.workspace / "hooks" / "README.md",
            self.workspace / "client" / "dist" / "index.html",
            self.workspace / "client" / "config.js",
            self.base / "another-workspace" / "src" / "main.py",
            self.workspace / "service" / "source" / "appendix.md",
            self.workspace / "viewer" / "srcfoo" / "main.js",
        ]
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(self.call("Edit", str(path))[0], "allow")

    def test_non_mutating_tools_are_not_gated(self) -> None:
        for tool in ("Bash", "Read", "Grep", "Glob"):
            with self.subTest(tool=tool):
                self.assertEqual(self.call(tool, str(self.roots[0] / "main.py"))[0], "allow")

    def test_bypass_requires_exact_value(self) -> None:
        path = str(self.roots[0] / "main.py")
        self.assertEqual(self.call("Edit", path, env_extra={"CLAUDE_GATE_BYPASS": "1"})[0],
                         "allow")
        self.assertEqual(self.call("Edit", path, env_extra={"CLAUDE_GATE_BYPASS": "true"})[0],
                         "deny")

    def test_private_executor_marker_is_optional_and_blank_is_not_identity(self) -> None:
        path = str(self.roots[0] / "main.py")
        self.assertEqual(self.call("Edit", path,
                                  env_extra={"TOOLKIT_EXECUTOR": "TASK-31"})[0], "allow")
        self.assertEqual(self.call("Edit", path,
                                  env_extra={"TOOLKIT_EXECUTOR": ""})[0], "deny")

    def test_fail_open_cases_always_emit_one_allow_decision(self) -> None:
        for raw in ("", "{}", "null", "[1,2,3]", '{"tool_name": 5}',
                    '{"tool_name":"Edit","tool_input":9}'):
            with self.subTest(raw=raw):
                decision, _ = self.call("Edit", raw=raw)
                self.assertEqual(decision, "allow")

    def test_no_private_source_roots_means_portable_noop(self) -> None:
        self.config_path.write_text("{}", encoding="utf-8")
        self.assertEqual(self.call("Edit", str(self.roots[0] / "main.py"))[0], "allow")


if __name__ == "__main__":
    unittest.main()
