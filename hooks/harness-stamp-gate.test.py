#!/usr/bin/env python3
"""Full scratch-only contract suite for the renderer-backed settings stamp gate."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HOOK = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "hooks" / "harness-stamp-gate.sh"
RENDERER = ROOT / "bin" / "settings-render"
TEMPLATE = json.dumps({"hooks": {"PreToolUse": []},
                       "path": "__HOME__/toolkit"}, separators=(",", ":")).encode()


class StampGateContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="stamp-gate-contract-")
        self.root = Path(self.temp.name) / "checkout"
        (self.root / "bin").mkdir(parents=True)
        (self.root / "hooks").mkdir()
        shutil.copyfile(RENDERER, self.root / "bin" / "settings-render")
        (self.root / "lib").mkdir()
        shutil.copyfile(ROOT / "lib" / "__init__.py", self.root / "lib" / "__init__.py")
        shutil.copyfile(ROOT / "lib" / "private_config.py", self.root / "lib" / "private_config.py")
        self.template = self.root / "settings.json.template"
        self.template.write_bytes(TEMPLATE)
        (self.root / "bootstrap.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        self.home = Path(self.temp.name) / "home"
        self.home.mkdir()
        self.settings = self.home / ".claude" / "settings.json"
        self.stamp = Path(self.temp.name) / "stamp"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def install_settings(self) -> bytes:
        self.settings.parent.mkdir(parents=True, exist_ok=True)
        output = self.home / "rendered-settings.json"
        cmd = [sys.executable, str(self.root / "bin" / "settings-render"),
               "--template", str(self.template), "--home", str(self.home.resolve()),
               "--output", str(output)]
        overlay = self.root / ".private" / "settings.json"
        if overlay.exists():
            cmd.extend(("--overlay", str(overlay)))
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = output.read_bytes()
        self.settings.write_bytes(payload)
        output.unlink()
        return payload

    def digest(self) -> str:
        return hashlib.sha256(self.install_settings()).hexdigest()

    def call(self, tool: str, command: str = "", *, bypass: bool = False,
             stamp_path: Path | None = None) -> tuple[str, str | None]:
        env = dict(os.environ)
        env.update({"HOME": str(self.home),
                    "HARNESS_STAMP_GATE_REPO_DIR": str(self.root),
                    "HARNESS_STAMP_GATE_STAMP_FILE": str(stamp_path or self.stamp)})
        if bypass:
            env["CLAUDE_HARNESS_BYPASS"] = "1"
        else:
            env.pop("CLAUDE_HARNESS_BYPASS", None)
        payload = json.dumps({"tool_name": tool, "tool_input": {"command": command}})
        result = subprocess.run(["bash", str(HOOK)], input=payload, capture_output=True,
                                text=True, env=env, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)["hookSpecificOutput"]
        return output["permissionDecision"], output.get("permissionDecisionReason")

    def set_stamp(self, digest: str | None = None) -> None:
        actual = self.install_settings()
        self.stamp.write_text((digest or hashlib.sha256(actual).hexdigest()) + "\n", encoding="utf-8")

    def test_matching_stamp_allows_silently(self) -> None:
        self.set_stamp()
        decision, reason = self.call("Bash", "echo safe")
        self.assertEqual((decision, reason), ("allow", None))

    def test_different_stamp_denies_and_names_repair_and_bypass(self) -> None:
        self.set_stamp("0" * 64)
        decision, reason = self.call("Bash", "echo work")
        self.assertEqual(decision, "deny")
        self.assertIn("harness-stamp-gate", reason)
        self.assertIn(str(self.root / "bootstrap.sh"), reason)
        self.assertIn("CLAUDE_HARNESS_BYPASS=1", reason)

    def test_missing_stamp_denies(self) -> None:
        self.install_settings()
        decision, reason = self.call("Bash", "echo work")
        self.assertEqual(decision, "deny")
        self.assertIn("no settings stamp", reason)

    def test_missing_template_disables_this_gate(self) -> None:
        self.settings.parent.mkdir(parents=True, exist_ok=True)
        self.settings.write_text("{}", encoding="utf-8")
        self.template.unlink()
        self.stamp.write_text("0" * 64 + "\n", encoding="utf-8")
        self.assertEqual(self.call("Bash", "echo work")[0], "allow")

    def test_matching_stamp_rejects_changed_installed_settings(self) -> None:
        self.set_stamp()
        self.settings.write_text('{"changed":true}\n', encoding="utf-8")
        decision, reason = self.call("Bash", "echo work")
        self.assertEqual(decision, "deny")
        self.assertIn("installed settings bytes do not match", reason)

    def test_matching_stamp_rejects_malformed_or_missing_settings(self) -> None:
        self.set_stamp()
        self.settings.write_text("not JSON", encoding="utf-8")
        decision, reason = self.call("Bash", "echo work")
        self.assertEqual(decision, "deny")
        self.assertIn("malformed", reason)
        self.set_stamp()
        self.settings.unlink()
        decision, reason = self.call("Bash", "echo work")
        self.assertEqual(decision, "deny")
        self.assertIn("installed settings file is missing", reason)

    def test_settings_and_stamp_symlinks_are_rejected(self) -> None:
        self.set_stamp()
        external_settings = self.home / "external-settings.json"
        external_settings.write_bytes(self.settings.read_bytes())
        self.settings.unlink()
        self.settings.symlink_to(external_settings)
        decision, reason = self.call("Bash", "echo work")
        self.assertEqual(decision, "deny")
        self.assertIn("settings path is a symlink", reason)
        self.settings.unlink()
        self.settings.write_bytes(external_settings.read_bytes())
        self.stamp.unlink()
        external_stamp = self.home / "external-stamp"
        external_stamp.write_text(self.digest() + "\n", encoding="utf-8")
        self.stamp.symlink_to(external_stamp)
        decision, reason = self.call("Bash", "echo work")
        self.assertEqual(decision, "deny")
        self.assertIn("stamp path is a symlink", reason)

    def test_diagnostic_allowlist_passes_when_stale(self) -> None:
        self.set_stamp("0" * 64)
        for tool in ("Read", "Glob", "Grep", "NotebookRead", "TodoWrite"):
            with self.subTest(tool=tool):
                self.assertEqual(self.call(tool)[0], "allow")

    def test_mutating_editor_is_denied_when_stale(self) -> None:
        self.set_stamp("0" * 64)
        self.assertEqual(self.call("Edit")[0], "deny")

    def test_only_bootstrap_bash_repair_is_allowed(self) -> None:
        self.set_stamp("0" * 64)
        self.assertEqual(self.call("Bash", "bash ./bootstrap.sh")[0], "allow")
        self.assertEqual(self.call("Bash", "echo unrelated")[0], "deny")

    def test_explicit_bypass_allows_same_stale_call(self) -> None:
        self.set_stamp("0" * 64)
        self.assertEqual(self.call("Bash", "echo work")[0], "deny")
        self.assertEqual(self.call("Bash", "echo work", bypass=True)[0], "allow")

    def test_renderer_digest_matches_exact_output_bytes(self) -> None:
        output = self.root / "rendered.json"
        cmd = [sys.executable, str(self.root / "bin" / "settings-render"),
               "--template", str(self.template), "--home", str(self.home),
               "--output", str(output), "--digest"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), hashlib.sha256(output.read_bytes()).hexdigest())

    def test_stamp_from_shared_renderer_is_accepted(self) -> None:
        self.set_stamp()
        self.assertEqual(self.call("Bash", "echo safe")[0], "allow")

    def test_template_change_refuses_until_new_stamp_is_installed(self) -> None:
        self.set_stamp()
        self.assertEqual(self.call("Bash", "echo safe")[0], "allow")
        self.template.write_bytes(TEMPLATE.replace(b'"path"', b'"paths"'))
        decision, reason = self.call("Bash", "echo safe")
        self.assertEqual(decision, "deny")
        self.assertIn("bootstrap.sh", reason)
        self.set_stamp()
        self.assertEqual(self.call("Bash", "echo safe")[0], "allow")

    def test_private_overlay_changes_the_expected_stamp(self) -> None:
        overlay = self.root / ".private" / "settings.json"
        overlay.parent.mkdir()
        overlay.write_text('{"model":"machine-choice"}', encoding="utf-8")
        self.set_stamp()
        self.assertEqual(self.call("Bash", "echo safe")[0], "allow")
        overlay.write_text('{"model":"new-machine-choice"}', encoding="utf-8")
        self.assertEqual(self.call("Bash", "echo safe")[0], "deny")

    def test_invalid_overlay_denies_work_but_keeps_repair_available(self) -> None:
        overlay = self.root / ".private" / "settings.json"
        overlay.parent.mkdir()
        overlay.write_text("invalid", encoding="utf-8")
        decision, reason = self.call("Bash", "echo safe")
        self.assertEqual(decision, "deny")
        self.assertIn("renderer failed", reason)
        self.assertEqual(self.call("Bash", "bash bootstrap.sh")[0], "allow")


if __name__ == "__main__":
    unittest.main()
