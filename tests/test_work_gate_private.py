#!/usr/bin/env python3
"""Focused tests for optional activation of the private task-management adapter."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "hooks" / "work-gate.sh"


class PrivateWorkGateToggleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="private-work-gate-")
        self.home = Path(self.temp.name)
        self.config = self.home / "config.json"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def call(self, *, enabled: bool | None) -> str:
        env = dict(os.environ, HOME=str(self.home), TMPDIR=str(self.home),
                   WORK_GATE_STATE_DIR=str(self.home / "state"), WORK_GATE_SCOPE="on")
        if enabled is None:
            env.pop("AI_TOOLKIT_CONFIG", None)
        else:
            self.config.write_text(json.dumps({"work_management": {"enabled": enabled}}),
                                   encoding="utf-8")
            env["AI_TOOLKIT_CONFIG"] = str(self.config)
        env.pop("CLAUDE_GATE_BYPASS", None)
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "echo task"},
                              "agent_id": "synthetic-executor", "session_id": "synthetic-session"})
        result = subprocess.run(["bash", str(HOOK)], input=payload, capture_output=True,
                                text=True, env=env, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"]

    def test_public_only_install_does_not_enable_task_policy(self) -> None:
        self.assertEqual(self.call(enabled=None), "allow")

    def test_explicitly_disabled_private_adapter_allows(self) -> None:
        self.assertEqual(self.call(enabled=False), "allow")

    def test_enabled_private_adapter_keeps_missing_brief_refusal(self) -> None:
        self.assertEqual(self.call(enabled=True), "deny")


if __name__ == "__main__":
    unittest.main()
