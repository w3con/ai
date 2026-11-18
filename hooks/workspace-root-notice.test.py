#!/usr/bin/env python3
"""Configuration-driven workspace import notice tests using temporary files only."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


HOOK = Path(__file__).with_name("workspace-root-notice.sh")


class WorkspaceRootNoticeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="workspace-root-notice-")
        self.base = Path(self.temp.name)
        self.root = self.base / "workspace"
        (self.root / "source").mkdir(parents=True)
        (self.root / "knowledge").mkdir()
        self.pointer = self.root / "WORKSPACE.md"
        self.pointer.write_text("", encoding="utf-8")
        self.rules = self.root / "knowledge" / "rules.md"
        self.rules.write_text("Synthetic rules.\n", encoding="utf-8")
        self.config = self.base / "private-config.json"
        self.write_config()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_config(self, *, imports: list[str] | None = None,
                     cwd_environment: str | None = None,
                     disable_environment: str | None = None) -> None:
        workspace = {
            "markers": ["source", "knowledge"],
            "pointer": "WORKSPACE.md",
            "imports": imports if imports is not None else ["@knowledge/rules.md"],
            "rules_file": "knowledge/rules.md",
        }
        if cwd_environment:
            workspace["cwd_environment"] = cwd_environment
        if disable_environment:
            workspace["disable_environment"] = disable_environment
        data = {"workspaces": [workspace]}
        self.config.write_text(json.dumps(data), encoding="utf-8")

    def call(self, cwd: Path, *, config: Path | None = None,
             extra_env: dict[str, str] | None = None,
             generic_cwd: bool = True, payload: str = "{}") -> tuple[int, str]:
        env = dict(os.environ)
        if generic_cwd:
            env["WORKSPACE_ROOT_NOTICE_CWD"] = str(cwd)
        else:
            env.pop("WORKSPACE_ROOT_NOTICE_CWD", None)
        if config is None:
            env.pop("AI_TOOLKIT_CONFIG", None)
        else:
            env["AI_TOOLKIT_CONFIG"] = str(config)
        env.update(extra_env or {})
        result = subprocess.run(["bash", str(HOOK)], input=payload, capture_output=True,
                                text=True, env=env, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.returncode, result.stdout

    def test_no_optional_config_is_silent(self) -> None:
        _, output = self.call(self.root)
        self.assertEqual(output, "")

    def test_configured_root_with_imports_is_silent(self) -> None:
        self.pointer.write_text("@knowledge/rules.md\n", encoding="utf-8")
        _, output = self.call(self.root, config=self.config)
        self.assertEqual(output, "")

    def test_nested_session_warns_and_names_configured_rules(self) -> None:
        nested = self.root / "source" / "module"
        nested.mkdir()
        _, output = self.call(nested, config=self.config)
        self.assertIn("not the configured workspace root", output)
        self.assertIn("Restart the session from the configured workspace root", output)
        self.assertIn(str(self.rules), output)

    def test_missing_import_at_workspace_root_is_named(self) -> None:
        _, output = self.call(self.root, config=self.config)
        self.assertIn("missing required import entries", output)
        self.assertIn("@knowledge/rules.md", output)
        self.assertIn("Add the listed imports", output)

    def test_unrelated_directory_is_silent(self) -> None:
        other = self.base / "other"
        other.mkdir()
        _, output = self.call(other, config=self.config)
        self.assertEqual(output, "")

    def test_missing_pointer_warns_without_failing_session(self) -> None:
        self.pointer.unlink()
        _, output = self.call(self.root, config=self.config)
        self.assertIn("missing required import entries", output)

    def test_malformed_optional_config_fails_open_with_no_private_path_output(self) -> None:
        self.config.write_text("{invalid", encoding="utf-8")
        _, output = self.call(self.root, config=self.config)
        self.assertEqual(output, "")

    def test_explicit_disable_is_silent(self) -> None:
        self.write_config(imports=[])
        env = dict(os.environ, WORKSPACE_ROOT_NOTICE_OFF="1",
                   WORKSPACE_ROOT_NOTICE_CWD=str(self.root), AI_TOOLKIT_CONFIG=str(self.config))
        result = subprocess.run(["bash", str(HOOK)], input="{}", capture_output=True,
                                text=True, env=env, check=False)
        self.assertEqual((result.returncode, result.stdout), (0, ""))

    def test_configured_legacy_environment_aliases_are_honored(self) -> None:
        self.write_config(cwd_environment="SYNTHETIC_OLD_CWD",
                          disable_environment="SYNTHETIC_OLD_OFF")
        nested = self.root / "source" / "nested"
        nested.mkdir()
        _, output = self.call(self.base / "outside", config=self.config,
                              generic_cwd=False,
                              extra_env={"SYNTHETIC_OLD_CWD": str(nested)})
        self.assertIn("not the configured workspace root", output)
        _, output = self.call(self.root, config=self.config,
                              extra_env={"SYNTHETIC_OLD_OFF": "silence"})
        self.assertEqual(output, "")

    def test_non_object_json_payload_fails_open(self) -> None:
        _, output = self.call(self.base, config=self.config, generic_cwd=False, payload="[]")
        self.assertEqual(output, "")


if __name__ == "__main__":
    unittest.main()
