#!/usr/bin/env python3
"""Isolated tests for the configurable session-inbox Stop hook."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "hooks" / "inbox-stop.py"


class InboxStopTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="inbox-stop-contract-")
        self.base = Path(self.temp.name)
        self.root = self.base / "external-workspace"
        (self.root / "bin").mkdir(parents=True)
        self.home = self.base / "home"
        self.home.mkdir()
        self.config = self.base / "private-config.json"
        self.command = self.root / "bin" / "session-inbox"
        self.write_command('{"text":"synthetic message"}\n')
        self.write_config()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_command(self, output: str, exit_code: int = 0) -> None:
        code = "import sys\nsys.stdout.write(" + repr(output) + ")\nsys.exit(" + str(exit_code) + ")\n"
        self.command.write_text(code, encoding="utf-8")

    def write_config(self) -> None:
        self.config.write_text(json.dumps({
            "inbox": {
                "root": str(self.root),
                "command": ["python3", "bin/session-inbox", "--drain", "--root", "{root}"],
            },
        }), encoding="utf-8")

    def call(self, payload: dict | None, *, raw: str | None = None,
             cwd: str | None = None, config: bool = True) -> tuple[int, str]:
        env = dict(os.environ)
        env["HOME"] = str(self.home)
        if config:
            env["AI_TOOLKIT_CONFIG"] = str(self.config)
        else:
            env.pop("AI_TOOLKIT_CONFIG", None)
        stdin = raw if raw is not None else json.dumps(payload or {})
        if cwd is not None:
            data = json.loads(stdin)
            data["cwd"] = cwd
            stdin = json.dumps(data)
        result = subprocess.run([sys.executable, str(HOOK)], input=stdin,
                                capture_output=True, text=True, env=env, timeout=10)
        return result.returncode, result.stdout

    @staticmethod
    def decision(output: str) -> dict | None:
        return json.loads(output) if output.strip() else None

    def test_configured_external_root_delivers_message(self) -> None:
        code, output = self.call({"cwd": str(self.root)})
        decision = self.decision(output)
        self.assertEqual(code, 0)
        self.assertEqual(decision["decision"], "block")
        self.assertIn("synthetic message", decision["reason"])

    def test_configured_root_can_be_any_explicit_path(self) -> None:
        nested = self.root / "nested"
        nested.mkdir()
        code, output = self.call({"cwd": str(self.root)}, cwd=str(nested))
        self.assertEqual(code, 0)
        self.assertEqual(self.decision(output)["decision"], "block")

    def test_turn_outside_configured_root_is_silent(self) -> None:
        outside = self.base / "outside"
        outside.mkdir()
        code, output = self.call({"cwd": str(outside)})
        self.assertEqual((code, output), (0, ""))

    def test_no_private_config_is_a_silent_optional_feature(self) -> None:
        code, output = self.call({"cwd": str(self.root)}, config=False)
        self.assertEqual((code, output), (0, ""))

    def test_empty_queue_is_silent(self) -> None:
        self.write_command("")
        self.assertEqual(self.call({"cwd": str(self.root)}), (0, ""))

    def test_card_identifier_is_preserved_as_data(self) -> None:
        self.write_command('{"text":"check the totals","card":"TASK-9"}\n')
        _, output = self.call({"cwd": str(self.root)})
        self.assertIn("[TASK-9] check the totals", self.decision(output)["reason"])

    def test_multiple_messages_are_all_delivered(self) -> None:
        self.write_command('{"text":"first message"}\n{"text":"second message"}\n')
        _, output = self.call({"cwd": str(self.root)})
        reason = self.decision(output)["reason"]
        self.assertIn("first message", reason)
        self.assertIn("second message", reason)

    def test_whitespace_message_is_ignored(self) -> None:
        self.write_command('{"text":"   "}\n')
        self.assertEqual(self.call({"cwd": str(self.root)}), (0, ""))

    def test_non_json_line_is_carried_verbatim(self) -> None:
        self.write_command("plain synthetic line\n")
        _, output = self.call({"cwd": str(self.root)})
        self.assertIn("plain synthetic line", self.decision(output)["reason"])

    def test_utf8_text_is_preserved(self) -> None:
        self.write_command('{"text":"café review"}\n')
        _, output = self.call({"cwd": str(self.root)})
        self.assertIn("café review", self.decision(output)["reason"])

    def test_malformed_input_fails_open(self) -> None:
        self.assertEqual(self.call(None, raw="not JSON"), (0, ""))

    def test_empty_input_fails_open(self) -> None:
        self.assertEqual(self.call(None, raw=""), (0, ""))

    def test_missing_cwd_fails_open(self) -> None:
        self.assertEqual(self.call({}), (0, ""))

    def test_missing_working_directory_fails_open(self) -> None:
        self.assertEqual(self.call({"cwd": str(self.base / "missing")}), (0, ""))

    def test_missing_command_fails_open(self) -> None:
        self.command.unlink()
        self.assertEqual(self.call({"cwd": str(self.root)}), (0, ""))

    def test_nonzero_command_fails_open(self) -> None:
        self.write_command('{"text":"not delivered"}\n', exit_code=3)
        self.assertEqual(self.call({"cwd": str(self.root)}), (0, ""))

    def test_bad_private_config_fails_open(self) -> None:
        self.config.write_text("{broken", encoding="utf-8")
        self.assertEqual(self.call({"cwd": str(self.root)}), (0, ""))


if __name__ == "__main__":
    unittest.main()
