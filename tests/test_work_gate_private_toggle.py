#!/usr/bin/env python3
"""The complex task gate is opt-in; public-only installs have no task assumptions."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "hooks" / "work-gate.sh"


class WorkGatePrivateToggleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="work-gate-config-")
        self.root = Path(self.temp.name)
        self.config = self.root / "private.json"
        self.config.write_text('{"work_management":{"enabled":false}}', encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def call(self, *, config: bool = True) -> dict:
        env = dict(os.environ, HOME=str(self.root), WORK_GATE_STATE_DIR=str(self.root / "state"))
        if config:
            env["AI_TOOLKIT_CONFIG"] = str(self.config)
        else:
            env.pop("AI_TOOLKIT_CONFIG", None)
        env.pop("CLAUDE_GATE_BYPASS", None)
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "echo public task"},
                              "agent_id": "public-agent"})
        result = subprocess.run(["bash", str(HOOK)], input=payload, capture_output=True,
                                text=True, env=env, check=False, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)["hookSpecificOutput"]

    def test_no_private_task_config_allows_without_card_system_refusal(self) -> None:
        self.assertEqual(self.call(config=False)["permissionDecision"], "allow")

    def test_explicitly_disabled_private_task_config_allows(self) -> None:
        self.assertEqual(self.call()["permissionDecision"], "allow")

    def test_malformed_private_config_fails_open(self) -> None:
        self.config.write_text("{invalid", encoding="utf-8")
        self.assertEqual(self.call()["permissionDecision"], "allow")


if __name__ == "__main__":
    unittest.main()
