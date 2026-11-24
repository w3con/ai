#!/usr/bin/env python3
"""Full scratch-only contract suite for the renderer-backed settings stamp gate."""

from __future__ import annotations

import hashlib
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib import settings_policy as policy
HOOK = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "hooks" / "harness-stamp-gate.sh"
RENDERER = ROOT / "bin" / "settings-render"
TEMPLATE = json.dumps({"hooks": {"PreToolUse": [{"matcher": "*", "hooks": [
                           {"type": "command", "command": "synthetic-managed-hook"}]}]},
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
        shutil.copyfile(ROOT / "lib" / "settings_policy.py", self.root / "lib" / "settings_policy.py")
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
             stamp_path: Path | None = None, cwd: Path | None = None) -> tuple[str, str | None]:
        env = dict(os.environ)
        env.pop("AI_TOOLKIT_CONFIG", None)
        env.update({"HOME": str(self.home),
                    "HARNESS_STAMP_GATE_REPO_DIR": str(self.root),
                    "HARNESS_STAMP_GATE_STAMP_FILE": str(stamp_path or self.stamp)})
        if bypass:
            env["CLAUDE_HARNESS_BYPASS"] = "1"
        else:
            env.pop("CLAUDE_HARNESS_BYPASS", None)
        payload = json.dumps({"tool_name": tool, "tool_input": {"command": command}})
        result = subprocess.run(["bash", str(HOOK)], input=payload, capture_output=True,
                                text=True, env=env, cwd=cwd, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)["hookSpecificOutput"]
        return output["permissionDecision"], output.get("permissionDecisionReason")

    def set_stamp(self, digest: str | None = None) -> None:
        actual = self.install_settings()
        self.stamp.write_text((digest or policy.managed_stamp(json.loads(actual))) + "\n", encoding="utf-8")

    def test_matching_stamp_allows_silently(self) -> None:
        self.set_stamp()
        decision, reason = self.call("Bash", "echo safe")
        self.assertEqual((decision, reason), ("allow", None))

    def test_different_stamp_denies_and_names_owner_repair(self) -> None:
        self.set_stamp("0" * 64)
        decision, reason = self.call("Bash", "echo work")
        self.assertEqual(decision, "deny")
        self.assertIn("harness-stamp-gate", reason)
        self.assertIn(str(self.root / "bootstrap.sh"), reason)
        self.assertIn("--dry-run", reason)
        self.assertIn("owner", reason)
        self.assertNotIn("BYPASS", reason)

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
        self.assertIn('added: "changed"', reason)
        self.assertIn('removed: "path"', reason)
        self.assertIn('hooks event "PreToolUse" source entry 1', reason)

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

    def test_private_preference_defaults_do_not_stale_stamp(self) -> None:
        overlay = self.root / ".private" / "settings.json"
        overlay.parent.mkdir()
        overlay.write_text('{"model":"machine-choice"}', encoding="utf-8")
        self.set_stamp()
        self.assertEqual(self.call("Bash", "echo safe")[0], "allow")
        overlay.write_text('{"model":"new-machine-choice"}', encoding="utf-8")
        self.assertEqual(self.call("Bash", "echo safe")[0], "allow")

    def test_invalid_overlay_denies_work_but_keeps_repair_available(self) -> None:
        overlay = self.root / ".private" / "settings.json"
        overlay.parent.mkdir()
        overlay.write_text("invalid", encoding="utf-8")
        decision, reason = self.call("Bash", "echo safe")
        self.assertEqual(decision, "deny")
        self.assertIn("renderer failed", reason)
        self.assertEqual(self.call("Bash", "bash bootstrap.sh")[0], "allow")

    def test_semantic_reorder_and_preference_add_change_remove_are_allowed(self) -> None:
        self.template.write_text(json.dumps({"theme": "dark", "model": "initial",
                                            "hooks": {"PreToolUse": []}, "env": {"A": "a", "B": "b"}}))
        self.set_stamp()
        stamp_before = self.stamp.read_bytes()
        settings = json.loads(self.settings.read_bytes())
        settings.pop("model")
        settings.update({"theme": "light", "voice": {"enabled": True, "autoSubmit": False, "mode": "hold"},
                         "modelSettings": {"example-model": {"effortLevel": "xhigh", "maxEffortLevel": "high",
                                                              "autoCompactWindow": 100000}},
                         "tui": "fullscreen"})
        self.settings.write_text(json.dumps(settings, sort_keys=True, separators=(",", ":")))
        self.assertEqual(self.call("Edit")[0], "allow")
        self.template.write_text(json.dumps({"env": {"B": "b", "A": "a"}, "hooks": {"PreToolUse": []},
                                            "theme": "auto", "model": "different-default"}, indent=4))
        self.assertEqual(self.call("Edit")[0], "allow")
        self.assertEqual(self.stamp.read_bytes(), stamp_before)

    def test_bypass_dialog_preference_does_not_block_tools_in_other_projects(self) -> None:
        settings = self.add_independent_hooks(self.owned_hook_fixture())
        stamp_before = self.stamp.read_bytes()
        for project in ("first-project", "second-project"):
            cwd = self.home / project
            cwd.mkdir()
            for value in (True, False, None):
                if value is None:
                    settings.pop("skipDangerousModePermissionPrompt", None)
                else:
                    settings["skipDangerousModePermissionPrompt"] = value
                self.settings.write_text(json.dumps(settings))
                for tool in ("Bash", "Skill", "Write", "Edit"):
                    with self.subTest(project=project, value=value, tool=tool):
                        self.assertEqual(self.call(tool, "true", cwd=cwd), ("allow", None))
        self.assertEqual(self.stamp.read_bytes(), stamp_before)

    def test_protected_unknown_and_auto_prompt_changes_are_denied(self) -> None:
        cases = {
            "hooks": {}, "permissions": {"allow": ["Bash"]}, "env": {"EXAMPLE": "hidden-value"},
            "disableAllHooks": True, "enabledPlugins": {"example@market": True},
            "extraKnownMarketplaces": {}, "sandbox": {"enabled": False},
            "skipAutoPermissionPrompt": True,
            "voiceCommand": "hidden-value", "apiKeyHelper": "hidden-value", "unknown": True,
        }
        for key, value in cases.items():
            with self.subTest(key=key):
                self.set_stamp()
                settings = json.loads(self.settings.read_bytes())
                settings.update({key: value, "theme": "light", "skipDangerousModePermissionPrompt": True})
                self.settings.write_text(json.dumps(settings))
                decision, reason = self.call("Edit")
                self.assertEqual(decision, "deny")
                self.assertIn('hooks event "PreToolUse" source entry 1' if key == "hooks" else json.dumps(key), reason)
                self.assertNotIn("hidden-value", reason)
                self.assertNotIn("BYPASS", reason)

    def test_unknown_nested_fields_and_invalid_preference_shapes_fail_closed(self) -> None:
        cases = [
            ("voice", {"enabled": True, "command": "hidden-value"}),
            ("voice", {"enabled": 1}), ("voice", {"mode": "other"}),
            ("modelSettings", {"example": {"command": "hidden-value"}}),
            ("modelSettings", {"example": {"autoCompactWindow": 99999}}),
            ("modelSettings", {"example": {"effortLevel": "max"}}),
            ("modelSettings", []), ("verbose", 1), ("theme", {"command": "hidden-value"}),
            *(("skipDangerousModePermissionPrompt", value) for value in (None, 0, 1, "true", {}, [])),
        ]
        for key, value in cases:
            with self.subTest(key=key, value=value):
                self.set_stamp()
                settings = json.loads(self.settings.read_bytes())
                settings[key] = value
                self.settings.write_text(json.dumps(settings))
                decision, reason = self.call("Edit")
                self.assertEqual(decision, "deny")
                self.assertIn(key, reason)
                self.assertNotIn("hidden-value", reason)

    def test_strict_json_rejects_duplicates_and_non_finite_values(self) -> None:
        for text in ('{"hooks":{},"hooks":{}}', '{"unknown":NaN}', '{"unknown":Infinity}',
                     '{"unknown":-Infinity}', '{"unknown":1e999}', '[]'):
            with self.subTest(text=text):
                self.set_stamp()
                self.settings.write_text(text)
                self.assertEqual(self.call("Edit")[0], "deny")
        for name in ("settings.json", "config.json"):
            self.set_stamp()
            private = self.root / ".private"
            private.mkdir(exist_ok=True)
            path = private / name
            path.write_text('{"duplicate":1,"duplicate":2}')
            self.assertEqual(self.call("Edit")[0], "deny")
            path.unlink()

    def test_controlled_boolean_number_and_array_order_are_significant(self) -> None:
        for before, after in [(True, 1), (["a", "b"], ["b", "a"])]:
            self.template.write_text(json.dumps({"unknown": before}))
            self.set_stamp()
            self.settings.write_text(json.dumps({"unknown": after}))
            self.assertEqual(self.call("Edit")[0], "deny")

    def test_legacy_upgrade_requires_current_renderer_digest_and_controlled_match(self) -> None:
        rendered = self.install_settings()
        self.stamp.write_text(hashlib.sha256(rendered).hexdigest())
        settings = json.loads(rendered)
        settings["theme"] = "light"
        self.settings.write_text(json.dumps(settings, sort_keys=True))
        self.assertEqual(self.call("Edit")[0], "allow")
        settings["disableAllHooks"] = True
        self.settings.write_text(json.dumps(settings))
        self.assertEqual(self.call("Edit")[0], "deny")
        self.install_settings()
        self.stamp.write_text("f" * 64)
        self.assertEqual(self.call("Edit")[0], "deny")

    def test_versioned_stamp_stales_on_controlled_source_change_even_if_installed_matches(self) -> None:
        self.set_stamp()
        self.template.write_text('{"hooks":{"PreToolUse":[]},"newControlled":true}')
        self.install_settings()
        decision, reason = self.call("Edit")
        self.assertEqual(decision, "deny")
        self.assertIn("stamp is stale", reason)
        self.assertIn("newControlled", reason)

    def test_malformed_stamps_are_rejected(self) -> None:
        for value in ("", "managed-v2:" + "f" * 64, "managed-v1:bad", "F" * 64):
            self.set_stamp(value + "\n")
            self.assertEqual(self.call("Edit")[0], "deny")

    def owned_hook_fixture(self):
        hooks = {"PreToolUse": [
            {"matcher": "Read", "timeout": 30, "hooks": [
                {"type": "command", "command": "synthetic-owned-one", "timeout": 10},
                {"type": "command", "command": "synthetic-owned-two"}]},
            {"matcher": "Edit", "hooks": [{"type": "prompt", "prompt": "synthetic-owned-prompt"}]},
        ]}
        self.template.write_text(json.dumps({"hooks": hooks, "permissions": {"allow": ["Read"]}}))
        self.set_stamp()
        return json.loads(self.settings.read_bytes())

    def add_independent_hooks(self, settings):
        settings["hooks"]["PreToolUse"][0]["hooks"].insert(1, {
            "type": "command", "command": "synthetic-independent-inline", "async": True})
        settings["hooks"]["PreToolUse"].insert(1, {"hooks": [
            {"type": "command", "command": "synthetic-independent-group", "timeout": 15}]})
        settings["hooks"]["PermissionRequest"] = [{"hooks": [
            {"type": "http", "url": "http://127.0.0.1:49000/synthetic"}]}]
        return settings

    def test_anonymous_additions_at_groups_events_and_within_groups_are_allowed(self) -> None:
        settings = self.add_independent_hooks(self.owned_hook_fixture())
        source_stamp = self.stamp.read_bytes()
        self.settings.write_text(json.dumps(settings))
        self.assertEqual(self.call("Edit"), ("allow", None))
        settings["hooks"]["PermissionRequest"][0]["hooks"][0]["url"] = "http://127.0.0.1:49001/changed"
        settings["hooks"]["PreToolUse"][1]["hooks"][0]["command"] = "synthetic-independent-update"
        self.settings.write_text(json.dumps(settings))
        self.assertEqual(self.call("Edit")[0], "allow")
        del settings["hooks"]["PermissionRequest"]
        settings["hooks"]["PreToolUse"].pop(1)
        settings["hooks"]["PreToolUse"][0]["hooks"].pop(1)
        self.settings.write_text(json.dumps(settings))
        self.assertEqual(self.call("Edit")[0], "allow")
        self.assertEqual(self.stamp.read_bytes(), source_stamp)

    def test_required_hook_removal_options_matcher_metadata_and_order_are_protected(self) -> None:
        original = self.add_independent_hooks(self.owned_hook_fixture())
        original["skipDangerousModePermissionPrompt"] = True
        for change in ("remove", "command", "type", "option", "matcher", "metadata", "reorder", "group-order"):
            with self.subTest(change=change):
                settings = copy.deepcopy(original)
                group = settings["hooks"]["PreToolUse"][0]
                if change == "remove":
                    group["hooks"].pop(0)
                elif change in {"command", "type"}:
                    group["hooks"][0][change] = "synthetic-changed-value"
                elif change == "option":
                    group["hooks"][0]["timeout"] = 11
                elif change == "matcher":
                    group["matcher"] = "Write"
                elif change == "metadata":
                    group["timeout"] = 31
                elif change == "reorder":
                    group["hooks"].reverse()
                else:
                    settings["hooks"]["PreToolUse"].reverse()
                self.settings.write_text(json.dumps(settings))
                decision, reason = self.call("Edit")
                self.assertEqual(decision, "deny")
                self.assertIn('hooks event "PreToolUse" source entry', reason)
                for value in ("synthetic-owned", "synthetic-independent", "synthetic-changed-value"):
                    self.assertNotIn(value, reason)

    def test_nonhook_controlled_drift_is_denied_alongside_external_additions(self) -> None:
        original = self.add_independent_hooks(self.owned_hook_fixture())
        original["skipDangerousModePermissionPrompt"] = True
        for key, value in {"permissions": {}, "env": {"EXAMPLE": "hidden-value"},
                           "disableAllHooks": True, "sandbox": {}, "enabledPlugins": {}, "unknown": True}.items():
            settings = copy.deepcopy(original)
            settings[key] = value
            self.settings.write_text(json.dumps(settings))
            decision, reason = self.call("Edit")
            self.assertEqual(decision, "deny")
            self.assertIn(json.dumps(key), reason)
            self.assertNotIn("hidden-value", reason)

    def test_dialog_preference_cannot_authorize_permission_mode_changes(self) -> None:
        original = self.owned_hook_fixture()
        for option, value in (("defaultMode", "bypassPermissions"),
                              ("disableBypassPermissionsMode", "disable")):
            settings = copy.deepcopy(original)
            settings["skipDangerousModePermissionPrompt"] = True
            settings["permissions"][option] = value
            self.settings.write_text(json.dumps(settings))
            decision, reason = self.call("Bash", "true")
            self.assertEqual(decision, "deny")
            self.assertIn('"permissions"', reason)

    def test_malformed_external_hook_shapes_are_not_exempted(self) -> None:
        original = self.owned_hook_fixture()
        for groups in ({}, [None], [{"hooks": {}}], [{"matcher": 1, "hooks": []}],
                       [{"hooks": [None]}], [{"hooks": [{}]}],
                       [{"hooks": [{"type": "command"}]}], [{"hooks": [{"type": "http", "url": False}]}]):
            settings = copy.deepcopy(original)
            settings["hooks"]["PermissionRequest"] = groups
            self.settings.write_text(json.dumps(settings))
            decision, reason = self.call("Edit")
            self.assertEqual(decision, "deny")
            self.assertIn('hooks event "PermissionRequest"', reason)

    def test_source_owned_duplicates_require_exact_multiplicity(self) -> None:
        source = self.owned_hook_fixture()
        group = source["hooks"]["PreToolUse"][0]
        group["hooks"].insert(0, copy.deepcopy(group["hooks"][0]))
        self.template.write_text(json.dumps(source))
        self.set_stamp()
        self.assertEqual(self.call("Edit")[0], "allow")
        source["hooks"]["PreToolUse"][0]["hooks"].pop(0)
        self.settings.write_text(json.dumps(source))
        self.assertEqual(self.call("Edit")[0], "deny")
        source["hooks"]["PreToolUse"][0]["hooks"].extend([copy.deepcopy(group["hooks"][0])] * 2)
        self.settings.write_text(json.dumps(source))
        decision, reason = self.call("Edit")
        self.assertEqual(decision, "deny")
        self.assertIn("ambiguous duplicate ownership", reason)

    def test_source_update_stales_stamp_even_when_external_hook_already_supplies_new_entry(self) -> None:
        settings = self.add_independent_hooks(self.owned_hook_fixture())
        self.settings.write_text(json.dumps(settings))
        source = json.loads(self.template.read_bytes())
        source["hooks"]["PermissionRequest"] = settings["hooks"]["PermissionRequest"]
        self.template.write_text(json.dumps(source))
        decision, reason = self.call("Edit")
        self.assertEqual(decision, "deny")
        self.assertIn("stamp is stale", reason)

    def test_legacy_renderer_digest_accepts_external_hooks_only_with_required_entries_intact(self) -> None:
        self.owned_hook_fixture()
        self.stamp.write_text(hashlib.sha256(self.settings.read_bytes()).hexdigest())
        settings = self.add_independent_hooks(json.loads(self.settings.read_bytes()))
        self.settings.write_text(json.dumps(settings))
        self.assertEqual(self.call("Edit")[0], "allow")
        settings["hooks"]["PreToolUse"][0]["hooks"].pop(0)
        self.settings.write_text(json.dumps(settings))
        self.assertEqual(self.call("Edit")[0], "deny")


if __name__ == "__main__":
    unittest.main()
