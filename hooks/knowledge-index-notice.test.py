#!/usr/bin/env python3
"""Synthetic tests for configured knowledge-index notice behavior."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "hooks" / "knowledge-index-notice.py"


class KnowledgeNoticeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="knowledge-notice-")
        self.base = Path(self.temp.name)
        self.workspace = self.base / "workspace"
        (self.workspace / "code").mkdir(parents=True)
        (self.workspace / "knowledge" / "cards" / "TASK-1").mkdir(parents=True)
        tools = self.workspace / "bin"
        tools.mkdir()
        (tools / "indexer.py").write_text(
            "import pathlib,sys\nprint('Synthetic index entry')\n", encoding="utf-8")
        (tools / "paths-check.py").write_text(
            "import pathlib,sys\nprint(pathlib.Path(sys.argv[1]).read_text())\n", encoding="utf-8")
        self.count = self.workspace / "count.txt"
        self.count.write_text("0", encoding="utf-8")
        self.config = self.base / "private-config.json"
        self.write_config()
        self.state = self.base / "notice-state"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_config(self) -> None:
        self.config.write_text(json.dumps({
            "knowledge_base": {"notice": {
                "workspace_markers": ["code", "knowledge"],
                "code_roots": ["code"],
                "knowledge_roots": ["knowledge"],
                "work_commands": ["task-submit"],
                "card_path_pattern": r"/knowledge/cards/[^/]+/description\.md$",
                "index_command": [sys.executable, "bin/indexer.py", "--root", "{root}"],
                "path_check_command": [sys.executable, "bin/paths-check.py", "{root}/count.txt"],
            }},
        }), encoding="utf-8")

    def call(self, event: dict, *, prompt: str = "prompt-one", off: bool = False) -> tuple[int, str]:
        payload = dict(event)
        payload.setdefault("prompt_id", prompt)
        env = dict(os.environ)
        env["AI_TOOLKIT_CONFIG"] = str(self.config)
        env["KNOWLEDGE_INDEX_NOTICE_CWD"] = str(self.workspace)
        env["KNOWLEDGE_INDEX_NOTICE_STATE_DIR"] = str(self.state)
        if off:
            env["KNOWLEDGE_INDEX_NOTICE_OFF"] = "1"
        else:
            env.pop("KNOWLEDGE_INDEX_NOTICE_OFF", None)
        result = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload),
                                capture_output=True, text=True, env=env, timeout=10)
        return result.returncode, result.stdout

    @staticmethod
    def context(output: str) -> str:
        try:
            return json.loads(output).get("hookSpecificOutput", {}).get("additionalContext", "")
        except ValueError:
            return ""

    def grep(self, pattern: str, path: Path | None = None, **extra) -> dict:
        tool_input = {"pattern": pattern}
        if path is not None:
            tool_input["path"] = str(path)
        return {"hook_event_name": "PreToolUse", "tool_name": "Grep",
                "tool_input": tool_input, **extra}

    def test_session_start_adds_current_configured_index(self) -> None:
        code, output = self.call({"hook_event_name": "SessionStart", "cwd": str(self.workspace)})
        self.assertEqual(code, 0)
        self.assertIn("Synthetic index entry", output)

    def test_session_start_reports_only_nonzero_dangling_link_count(self) -> None:
        self.count.write_text("2", encoding="utf-8")
        _, output = self.call({"hook_event_name": "SessionStart", "cwd": str(self.workspace)})
        self.assertIn("2 unresolved links", output)
        self.count.write_text("0", encoding="utf-8")
        _, output = self.call({"hook_event_name": "SessionStart", "cwd": str(self.workspace)})
        self.assertNotIn("unresolved links", output)

    def test_prose_search_inside_knowledge_root_adds_context(self) -> None:
        _, output = self.call(self.grep("data model", self.workspace / "knowledge"))
        self.assertIn("Synthetic index entry", self.context(output))

    def test_repeated_search_in_one_prompt_adds_context_once(self) -> None:
        self.call(self.grep("data model", self.workspace / "knowledge"))
        _, output = self.call(self.grep("another question", self.workspace / "knowledge"))
        self.assertEqual(self.context(output), "")

    def test_new_prompt_receives_index_again(self) -> None:
        self.call(self.grep("data model", self.workspace / "knowledge"))
        _, output = self.call(self.grep("another question", self.workspace / "knowledge"),
                              prompt="prompt-two")
        self.assertIn("Synthetic index entry", self.context(output))

    def test_code_path_search_with_plain_language_query_adds_context(self) -> None:
        _, output = self.call(self.grep("why does this work", self.workspace / "code"))
        self.assertIn("Synthetic index entry", self.context(output))

    def test_code_identifier_search_is_not_classified_as_knowledge(self) -> None:
        _, output = self.call(self.grep("MaxRecordSize", self.workspace / "code"))
        self.assertEqual(self.context(output), "")

    def test_search_without_path_adds_context(self) -> None:
        _, output = self.call(self.grep("data model"))
        self.assertIn("Synthetic index entry", self.context(output))

    def test_configured_card_path_adds_context(self) -> None:
        path = self.workspace / "knowledge/cards/TASK-1/description.md"
        _, output = self.call({"hook_event_name": "PreToolUse", "tool_name": "Write",
                               "tool_input": {"file_path": str(path)}})
        self.assertIn("Synthetic index entry", self.context(output))

    def test_code_edit_and_ordinary_command_do_not_add_context(self) -> None:
        _, output = self.call({"hook_event_name": "PreToolUse", "tool_name": "Edit",
                               "tool_input": {"file_path": str(self.workspace / "code/a.py")}})
        self.assertEqual(self.context(output), "")
        _, output = self.call({"hook_event_name": "PreToolUse", "tool_name": "Bash",
                               "tool_input": {"command": "echo done"}})
        self.assertEqual(self.context(output), "")

    def test_configured_work_command_adds_context(self) -> None:
        _, output = self.call({"hook_event_name": "PreToolUse", "tool_name": "Bash",
                               "tool_input": {"command": "task-submit TASK-1"}})
        self.assertIn("Synthetic index entry", self.context(output))

    def test_shell_search_distinguishes_knowledge_and_code_paths(self) -> None:
        _, output = self.call({"hook_event_name": "PreToolUse", "tool_name": "Bash",
                               "tool_input": {"command": "rg 'term' knowledge/"}})
        self.assertIn("Synthetic index entry", self.context(output))
        self.call(self.grep("another", self.workspace / "knowledge"), prompt="reset")
        _, output = self.call({"hook_event_name": "PreToolUse", "tool_name": "Bash",
                               "tool_input": {"command": "rg 'term' code/"}}, prompt="code")
        self.assertEqual(self.context(output), "")

    def test_read_and_executor_calls_are_not_annotated(self) -> None:
        _, output = self.call({"hook_event_name": "PreToolUse", "tool_name": "Read",
                               "tool_input": {"file_path": str(self.workspace / "knowledge/a.md")}})
        self.assertEqual(self.context(output), "")
        _, output = self.call(self.grep("prose", self.workspace / "knowledge", agent_id="worker"))
        self.assertEqual(output.strip(), "")

    def test_outside_workspace_is_silent(self) -> None:
        other = self.base / "unrelated"
        other.mkdir()
        env = dict(os.environ, AI_TOOLKIT_CONFIG=str(self.config),
                   KNOWLEDGE_INDEX_NOTICE_CWD=str(other),
                   KNOWLEDGE_INDEX_NOTICE_STATE_DIR=str(self.state))
        result = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(self.grep("prose")),
                                capture_output=True, text=True, env=env)
        self.assertEqual((result.returncode, result.stdout), (0, ""))

    def test_disabled_hook_and_malformed_payload_fail_open(self) -> None:
        self.assertEqual(self.call(self.grep("prose"), off=True)[1], "")
        env = dict(os.environ, AI_TOOLKIT_CONFIG=str(self.config))
        result = subprocess.run([sys.executable, str(HOOK)], input="not JSON",
                                capture_output=True, text=True, env=env)
        self.assertEqual((result.returncode, result.stdout), (0, ""))

    def test_no_private_config_disables_optional_notice(self) -> None:
        env = dict(os.environ)
        env.pop("AI_TOOLKIT_CONFIG", None)
        env["KNOWLEDGE_INDEX_NOTICE_CWD"] = str(self.workspace)
        result = subprocess.run([sys.executable, str(HOOK)],
                                input=json.dumps({"hook_event_name": "SessionStart",
                                                  "cwd": str(self.workspace)}),
                                capture_output=True, text=True, env=env)
        self.assertEqual((result.returncode, result.stdout), (0, ""))


if __name__ == "__main__":
    unittest.main()
