#!/usr/bin/env python3
"""Isolated installer acceptance fixtures; never targets the real user HOME."""

from __future__ import annotations

import hashlib
import copy
import importlib.util
import contextlib
import io
import errno
import fcntl
import json
import os
import pty
import select
import shutil
import subprocess
import tempfile
import termios
import time
import unittest
from unittest import mock
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))
from lib import settings_policy as policy


class BootstrapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="toolkit-bootstrap-test-")
        self.base = Path(self.temp.name)
        self.repo = self.base / "checkout"
        self.home1 = self.base / "home-one"
        self.home2 = self.base / "home-two"
        self.make_fixture()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def make_fixture(self) -> None:
        subprocess.run(["git", "init", "--quiet", "--initial-branch=main", str(self.repo)],
                       check=True)
        (self.repo / "bin").mkdir(parents=True)
        (self.repo / "lib").mkdir()
        (self.repo / ".githooks").mkdir()
        (self.repo / ".gitignore").write_text(".private/\n", encoding="utf-8")
        for directory in ("agents", "hooks", "skills", "commands"):
            (self.repo / directory).mkdir()
            (self.repo / directory / "fixture.txt").write_text("fixture\n", encoding="utf-8")
        (self.repo / "CLAUDE.md").write_text("@STYLE.md\n@.private/rules.md\n", encoding="utf-8")
        (self.repo / "STYLE.md").write_text("Synthetic public style marker.\n", encoding="utf-8")
        (self.repo / "statusline-command.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        (self.repo / "hooks" / "workspace-root-notice.sh").write_text(
            "#!/bin/sh\nexit 0\n", encoding="utf-8")
        (self.repo / ".githooks" / "pre-commit").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        for src, dst in ((ROOT / "bootstrap.sh", self.repo / "bootstrap.sh"),
                         (ROOT / "bin" / "bootstrap.py", self.repo / "bin" / "bootstrap.py"),
                         (ROOT / "bin" / "settings-render", self.repo / "bin" / "settings-render"),
                         (ROOT / "settings.json.template", self.repo / "settings.json.template"),
                          (ROOT / "lib" / "__init__.py", self.repo / "lib" / "__init__.py"),
                          (ROOT / "lib" / "settings_policy.py", self.repo / "lib" / "settings_policy.py"),
                          (ROOT / "hooks" / "harness-stamp-gate.sh", self.repo / "hooks" / "harness-stamp-gate.sh"),
                         (ROOT / "lib" / "private_config.py", self.repo / "lib" / "private_config.py")):
            shutil.copyfile(src, dst)

    def run_bootstrap(self, home: Path, *args: str,
                      config: Path | None = None,
                      env_extra: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        env = dict(os.environ)
        env["HOME"] = str(home)
        if config:
            env["AI_TOOLKIT_CONFIG"] = str(config)
        else:
            env.pop("AI_TOOLKIT_CONFIG", None)
        if env_extra:
            env.update(env_extra)
        return subprocess.run(["bash", str(self.repo / "bootstrap.sh"), *args],
                              capture_output=True, text=True, env=env, check=False,
                              start_new_session=True)

    def test_empty_home_install_and_repeat_are_idempotent(self) -> None:
        result = self.run_bootstrap(self.home1)
        self.assertEqual(result.returncode, 0, result.stderr)
        claude = self.home1 / ".claude"
        for name in ("CLAUDE.md", "agents", "hooks", "skills", "commands", "statusline-command.sh", "memory"):
            self.assertTrue((claude / name).is_symlink(), name)
        settings = claude / "settings.json"
        stamp = claude / ".harness-stamp"
        self.assertEqual(policy.managed_stamp(json.loads(settings.read_bytes())), stamp.read_text().strip())
        self.assertTrue((self.repo / ".private" / "rules.md").is_file())
        first = settings.read_bytes()
        again = self.run_bootstrap(self.home1)
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertEqual(settings.read_bytes(), first)
        self.assertEqual(policy.managed_stamp(json.loads(settings.read_bytes())), stamp.read_text().strip())

    def test_dry_run_does_not_create_home_or_private_rules(self) -> None:
        result = self.run_bootstrap(self.home1, "--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.home1.exists())
        self.assertFalse((self.repo / ".private" / "rules.md").exists())

    def test_two_home_paths_render_separately(self) -> None:
        self.assertEqual(self.run_bootstrap(self.home1).returncode, 0)
        self.assertEqual(self.run_bootstrap(self.home2).returncode, 0)
        one = json.loads((self.home1 / ".claude/settings.json").read_text())
        two = json.loads((self.home2 / ".claude/settings.json").read_text())
        self.assertNotEqual(one, two)
        self.assertIn(str(self.home1), json.dumps(one))
        self.assertIn(str(self.home2), json.dumps(two))

    def test_machine_preferences_are_kept_in_private_overlay(self) -> None:
        private = self.repo / ".private"
        private.mkdir()
        (private / "settings.json").write_text(json.dumps({
            "model": "local-choice", "theme": "dark",
        }), encoding="utf-8")
        result = self.run_bootstrap(self.home1)
        self.assertEqual(result.returncode, 0, result.stderr)
        settings = json.loads((self.home1 / ".claude/settings.json").read_text())
        self.assertEqual(settings["model"], "local-choice")
        self.assertEqual(settings["theme"], "dark")
        self.assertIn("PreToolUse", settings["hooks"])

    def test_private_legacy_hook_alias_points_to_one_generic_implementation(self) -> None:
        config = self.base / "machine-config.json"
        config.write_text(json.dumps({
            "extensions": {
                "hooks/legacy-workspace-start.sh": "hooks/workspace-root-notice.sh",
            },
        }), encoding="utf-8")
        result = self.run_bootstrap(self.home1, config=config)
        self.assertEqual(result.returncode, 0, result.stderr)
        stored_config = self.repo / ".private/config.json"
        self.assertTrue(stored_config.is_symlink())
        self.assertEqual(stored_config.resolve(), config.resolve())
        alias = self.home1 / ".claude/hooks/legacy-workspace-start.sh"
        self.assertTrue(alias.is_symlink())
        self.assertEqual(alias.resolve(), (self.repo / "hooks/workspace-root-notice.sh").resolve())
        self.assertTrue((self.repo / "hooks/legacy-workspace-start.sh").is_symlink())
        ignored = subprocess.run(["git", "-C", str(self.repo), "check-ignore", "-q",
                                  "hooks/legacy-workspace-start.sh"], check=False)
        self.assertEqual(ignored.returncode, 0)
        self.assertFalse((self.home1 / ".zshenv").exists())

    def test_existing_empty_project_memory_directory_is_linked_to_private_store(self) -> None:
        project_memory = self.home1 / ".claude/projects/synthetic-project/memory"
        project_memory.mkdir(parents=True)
        result = self.run_bootstrap(self.home1)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(project_memory.is_symlink())
        self.assertEqual(project_memory.resolve(), (self.home1 / ".claude/memory").resolve())

    def test_nonempty_project_memory_is_preserved_without_changing_existing_install(self) -> None:
        installed = self.run_bootstrap(self.home1)
        self.assertEqual(installed.returncode, 0, installed.stderr)
        settings_path = self.home1 / ".claude/settings.json"
        stamp_path = self.home1 / ".claude/.harness-stamp"
        settings_before = settings_path.read_bytes()
        stamp_before = stamp_path.read_bytes()
        project_memory = self.home1 / ".claude/projects/synthetic-project/memory"
        project_memory.mkdir(parents=True)
        marker = project_memory / "existing.md"
        marker.write_text("synthetic private content\n", encoding="utf-8")
        result = self.run_bootstrap(self.home1)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(marker.read_text(encoding="utf-8"), "synthetic private content\n")
        self.assertEqual(settings_path.read_bytes(), settings_before)
        self.assertEqual(stamp_path.read_bytes(), stamp_before)

    def test_failed_render_preserves_existing_install(self) -> None:
        self.assertEqual(self.run_bootstrap(self.home1).returncode, 0)
        claude = self.home1 / ".claude"
        settings_before = (claude / "settings.json").read_bytes()
        stamp_before = (claude / ".harness-stamp").read_bytes()
        links_before = {name: os.readlink(claude / name) for name in
                        ("CLAUDE.md", "agents", "hooks", "skills", "commands", "statusline-command.sh", "memory")}
        template = self.repo / "settings.json.template"
        template.write_text("not-json", encoding="utf-8")
        failed = self.run_bootstrap(self.home1)
        self.assertNotEqual(failed.returncode, 0)
        self.assertEqual((claude / "settings.json").read_bytes(), settings_before)
        self.assertEqual((claude / ".harness-stamp").read_bytes(), stamp_before)
        self.assertEqual({name: os.readlink(claude / name) for name in links_before}, links_before)

    def test_missing_required_source_fails_before_any_install_mutation(self) -> None:
        shutil.rmtree(self.repo / "commands")
        failed = self.run_bootstrap(self.home1)
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("commands", failed.stderr)
        self.assertFalse(self.home1.exists())
        self.assertFalse((self.repo / ".private").exists())

    def test_late_failure_rolls_back_settings_links_stamp_and_git_config(self) -> None:
        installed = self.run_bootstrap(self.home1)
        self.assertEqual(installed.returncode, 0, installed.stderr)
        claude = self.home1 / ".claude"
        names = ("CLAUDE.md", "agents", "hooks", "skills", "commands", "statusline-command.sh", "memory")
        links_before = {name: os.readlink(claude / name) for name in names}
        settings_before = (claude / "settings.json").read_bytes()
        stamp_before = (claude / ".harness-stamp").read_bytes()
        git_config_before = (self.repo / ".git/config").read_bytes()
        failed = self.run_bootstrap(self.home1, env_extra={"AI_TOOLKIT_BOOTSTRAP_FAILPOINT": "after-settings"})
        self.assertNotEqual(failed.returncode, 0)
        self.assertEqual({name: os.readlink(claude / name) for name in names}, links_before)
        self.assertEqual((claude / "settings.json").read_bytes(), settings_before)
        self.assertEqual((claude / ".harness-stamp").read_bytes(), stamp_before)
        self.assertEqual((self.repo / ".git/config").read_bytes(), git_config_before)

    def test_full_candidate_shell_install_repeat_dry_run_and_failure_rollback(self) -> None:
        full_root = self.base / "full-candidate"
        shutil.copytree(ROOT, full_root, symlinks=True,
                        ignore=shutil.ignore_patterns(".git", ".private", "__pycache__", "*.pyc"))
        subprocess.run(["git", "init", "--quiet", "--initial-branch=main", str(full_root)], check=True)
        env = dict(os.environ)
        env.pop("AI_TOOLKIT_CONFIG", None)
        env["HOME"] = str(self.home1)
        install = subprocess.run(["bash", str(full_root / "bootstrap.sh")],
                                 capture_output=True, text=True, env=env, check=False)
        self.assertEqual(install.returncode, 0, install.stderr)
        claude = self.home1 / ".claude"
        self.assertTrue((claude / "commands").is_symlink())
        self.assertTrue((full_root / "commands/.gitkeep").is_file())
        settings_path = claude / "settings.json"
        stamp_path = claude / ".harness-stamp"
        settings_before = settings_path.read_bytes()
        stamp_before = stamp_path.read_bytes()
        links_before = {name: os.readlink(claude / name) for name in
                        ("CLAUDE.md", "agents", "hooks", "skills", "commands", "statusline-command.sh", "memory")}
        config_before = (full_root / ".git/config").read_bytes()

        repeat = subprocess.run(["bash", str(full_root / "bootstrap.sh")],
                                capture_output=True, text=True, env=env, check=False)
        self.assertEqual(repeat.returncode, 0, repeat.stderr)
        self.assertEqual(settings_path.read_bytes(), settings_before)

        dry_home = self.base / "full-dry-home"
        dry_env = {**env, "HOME": str(dry_home)}
        dry = subprocess.run(["bash", str(full_root / "bootstrap.sh"), "--dry-run"],
                             capture_output=True, text=True, env=dry_env, check=False)
        self.assertEqual(dry.returncode, 0, dry.stderr)
        self.assertFalse(dry_home.exists())

        failed = subprocess.run(["bash", str(full_root / "bootstrap.sh")],
                                capture_output=True, text=True,
                                env={**env, "AI_TOOLKIT_BOOTSTRAP_FAILPOINT": "after-settings"},
                                check=False)
        self.assertNotEqual(failed.returncode, 0)
        self.assertEqual(settings_path.read_bytes(), settings_before)
        self.assertEqual(stamp_path.read_bytes(), stamp_before)
        self.assertEqual({name: os.readlink(claude / name) for name in links_before}, links_before)
        self.assertEqual((full_root / ".git/config").read_bytes(), config_before)

        missing_root = self.base / "missing-command-candidate"
        shutil.copytree(ROOT, missing_root, symlinks=True,
                        ignore=shutil.ignore_patterns(".git", ".private", "__pycache__", "*.pyc"))
        shutil.rmtree(missing_root / "commands")
        missing_home = self.base / "missing-command-home"
        result = subprocess.run(["bash", str(missing_root / "bootstrap.sh")],
                                capture_output=True, text=True,
                                env={**env, "HOME": str(missing_home)}, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("commands", result.stderr)
        self.assertFalse(missing_home.exists())
        self.assertFalse((missing_root / ".private").exists())

    def test_existing_real_destination_is_preserved_and_not_stamped(self) -> None:
        agents = self.home1 / ".claude/agents"
        agents.mkdir(parents=True)
        marker = agents / "keep.txt"
        marker.write_text("user-owned\n", encoding="utf-8")
        result = self.run_bootstrap(self.home1)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(marker.read_text(), "user-owned\n")
        self.assertFalse((self.home1 / ".claude/.harness-stamp").exists())

    def settings_path(self) -> Path:
        return self.home1 / ".claude/settings.json"

    def baseline_path(self) -> Path:
        return self.home1 / ".claude/.harness-managed.json"

    def independent_installer(self, action="append") -> None:
        """A separate owner/process atomically rewrites only the scratch settings."""
        self.assertTrue(self.settings_path().is_relative_to(self.base))
        script = '''import json, os, sys
from pathlib import Path
path, action = Path(sys.argv[1]), sys.argv[2]
settings = json.loads(path.read_bytes())
groups = settings["hooks"]["PreToolUse"]
if action == "append":
    groups[0]["hooks"].append({"type":"command","command":"synthetic-independent-inline","async":True})
    groups.append({"matcher":"Read|Edit","hooks":[{"type":"command","command":"synthetic-independent-group","timeout":15}]})
    settings["hooks"]["PermissionRequest"] = [{"hooks":[{"type":"http","url":"http://127.0.0.1:49000/synthetic"}]}]
    settings["theme"] = "light"
    settings.pop("model", None)
elif action == "update":
    groups[-1]["hooks"][0]["command"] = "synthetic-independent-update"
    groups[0]["hooks"][-1]["timeout"] = 20
elif action == "delete":
    groups.pop()
    groups[0]["hooks"].pop()
    del settings["hooks"]["PermissionRequest"]
temporary = path.with_suffix(".independent-new")
temporary.write_text(json.dumps(settings))
temporary.chmod(0o600)
os.replace(temporary, path)
'''
        result = subprocess.run([sys.executable, "-c", script, str(self.settings_path()), action],
                                capture_output=True, text=True, env={**os.environ, "HOME": str(self.home1)})
        self.assertEqual(result.returncode, 0, result.stderr)

    def gate(self) -> str:
        env = {**os.environ, "HOME": str(self.home1)}
        env.pop("AI_TOOLKIT_CONFIG", None)
        env.pop("CLAUDE_HARNESS_BYPASS", None)
        env.pop("HARNESS_STAMP_GATE_REPO_DIR", None)
        env.pop("HARNESS_STAMP_GATE_STAMP_FILE", None)
        result = subprocess.run(["bash", str(self.repo / "hooks/harness-stamp-gate.sh")],
                                input='{"tool_name":"Edit"}', capture_output=True, text=True, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"]

    def bootstrap_module(self):
        spec = importlib.util.spec_from_file_location("test_bootstrap_module", self.repo / "bin/bootstrap.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def adopt_with_confirmation(self, *, confirm=None, failpoint="", dry_run=False, during_install=None):
        module = self.bootstrap_module()
        output = io.StringIO()
        with mock.patch.dict(os.environ, {"HOME": str(self.home1),
                                          "AI_TOOLKIT_BOOTSTRAP_FAILPOINT": failpoint}):
            os.environ.pop("AI_TOOLKIT_CONFIG", None)
            with mock.patch.object(module, "confirm_adoption", side_effect=confirm) as confirmation:
                with mock.patch.object(module, "installation_failpoint",
                                       side_effect=during_install or module.installation_failpoint), \
                        contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                    result = module.install(self.repo.resolve(), self.home1.resolve(), dry_run, adopt=True)
        return result, output.getvalue(), confirmation

    def test_reordered_settings_and_source_redeploy_with_same_stamp(self) -> None:
        self.assertEqual(self.run_bootstrap(self.home1).returncode, 0)
        stamp = self.home1 / ".claude/.harness-stamp"
        before = stamp.read_bytes()
        settings = json.loads(self.settings_path().read_bytes())
        self.settings_path().write_text(json.dumps(settings, sort_keys=True, separators=(",", ":")))
        template = self.repo / "settings.json.template"
        template.write_text(json.dumps(json.loads(template.read_bytes()), sort_keys=True, indent=4))
        result = self.run_bootstrap(self.home1)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(stamp.read_bytes(), before)
        self.assertEqual(self.gate(), "allow")

    def test_all_reviewed_preferences_survive_redeploy_and_gate(self) -> None:
        overlay = self.repo / ".private/settings.json"
        overlay.parent.mkdir()
        overlay.write_text('{"model":"initial","theme":"dark"}')
        self.assertEqual(self.run_bootstrap(self.home1).returncode, 0)
        installed = json.loads(self.settings_path().read_bytes())
        wanted = dict.fromkeys(policy.BOOLEAN_PREFERENCES, True)
        wanted.update({"theme": "light", "effortLevel": "xhigh", "language": "English",
                       "preferredNotifChannel": "notifications_disabled", "editorMode": "vim",
                       "viewMode": "focus", "tui": "fullscreen",
                       "voice": {"enabled": True, "autoSubmit": False, "mode": "tap"},
                       "modelSettings": {"example-model": {"effortLevel": "low", "maxEffortLevel": "high",
                                                            "autoCompactWindow": "auto"}}})
        installed.pop("model")  # An intentional deletion must beat overlay defaults.
        installed.update(wanted)
        self.settings_path().write_text(json.dumps(installed))
        self.assertEqual(self.gate(), "allow")
        before_overlay = overlay.read_bytes()
        result = self.run_bootstrap(self.home1)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(policy.preferences(json.loads(self.settings_path().read_bytes())), wanted)
        self.assertEqual(overlay.read_bytes(), before_overlay)
        self.assertEqual(self.gate(), "allow")
        # Source preference additions, changes and removals also leave installed preferences alone.
        overlay.write_text('{"theme":"auto","model":"source-change","voiceEnabled":false}')
        result = self.run_bootstrap(self.home1)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(policy.preferences(json.loads(self.settings_path().read_bytes())), wanted)
        self.assertEqual(self.gate(), "allow")

    def test_controlled_source_update_uses_prior_managed_baseline(self) -> None:
        self.assertEqual(self.run_bootstrap(self.home1).returncode, 0)
        template = self.repo / "settings.json.template"
        settings = json.loads(template.read_bytes())
        settings["env"] = {"EXAMPLE": "source-value"}
        template.write_text(json.dumps(settings))
        self.assertEqual(self.gate(), "deny")
        before_settings = self.settings_path().read_bytes()
        dry = self.run_bootstrap(self.home1, "--dry-run")
        self.assertEqual(dry.returncode, 0, dry.stderr)
        self.assertIn('added: "env"', dry.stdout)
        self.assertNotIn("source-value", dry.stdout)
        self.assertEqual(self.settings_path().read_bytes(), before_settings)
        result = self.run_bootstrap(self.home1)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(self.settings_path().read_bytes())["env"], settings["env"])
        self.assertEqual(self.gate(), "allow")

    def test_controlled_drift_and_invalid_preferences_fail_before_mutation_or_adoption(self) -> None:
        self.assertEqual(self.run_bootstrap(self.home1).returncode, 0)
        original = self.settings_path().read_bytes()
        stamp = self.home1 / ".claude/.harness-stamp"
        before_stamp = stamp.read_bytes()
        cases = {"hooks": {}, "permissions": {}, "env": {"EXAMPLE": "hidden-value"},
                 "disableAllHooks": True, "enabledPlugins": {"example": True},
                 "extraKnownMarketplaces": {}, "sandbox": {}, "newUnknown": 1,
                 "skipDangerousModePermissionPrompt": "hidden-value", "skipAutoPermissionPrompt": True,
                 "voice": {"enabled": True, "command": "hidden-value"},
                 "modelSettings": {"example": {"autoCompactWindow": 99999}}, "verbose": 1}
        for key, value in cases.items():
            with self.subTest(key=key):
                settings = json.loads(original)
                settings.update({"theme": "light", key: value})
                self.settings_path().write_text(json.dumps(settings))
                before = self.settings_path().read_bytes()
                result = self.run_bootstrap(self.home1, "--dry-run")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(key, result.stderr)
                self.assertNotIn("hidden-value", result.stderr)
                adopted, output, confirmation = self.adopt_with_confirmation()
                self.assertEqual(adopted, 1)
                confirmation.assert_not_called()
                self.assertEqual(self.settings_path().read_bytes(), before)
                self.assertEqual(stamp.read_bytes(), before_stamp)

    def test_legacy_stamp_upgrade_does_not_authorize_controlled_drift(self) -> None:
        self.assertEqual(self.run_bootstrap(self.home1).returncode, 0)
        original = self.settings_path().read_bytes()
        stamp = self.home1 / ".claude/.harness-stamp"
        (self.home1 / ".claude/.harness-managed.json").unlink()
        stamp.write_text(hashlib.sha256(original).hexdigest())
        settings = json.loads(original)
        settings["theme"] = "light"
        self.settings_path().write_text(json.dumps(settings, sort_keys=True))
        self.assertEqual(self.gate(), "allow")
        upgraded = self.run_bootstrap(self.home1)
        self.assertEqual(upgraded.returncode, 0, upgraded.stderr)
        self.assertTrue(stamp.read_text().startswith("managed-v1:"))
        settings["disableAllHooks"] = True
        self.settings_path().write_text(json.dumps(settings))
        (self.home1 / ".claude/.harness-managed.json").unlink()
        stamp.write_text(hashlib.sha256(self.settings_path().read_bytes()).hexdigest())
        failed = self.run_bootstrap(self.home1)
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("disableAllHooks", failed.stderr)

    def test_adopt_preview_success_and_deletion_preserve_unrelated_overlay_fields(self) -> None:
        overlay = self.repo / ".private/settings.json"
        overlay.parent.mkdir()
        overlay.write_text('{"model":"initial","theme":"dark","env":{"EXAMPLE":"hidden-value"}}')
        self.assertEqual(self.run_bootstrap(self.home1).returncode, 0)
        installed = json.loads(self.settings_path().read_bytes())
        installed.pop("model")
        installed.update({"theme": "light", "voice": {"enabled": True}})
        self.settings_path().write_text(json.dumps(installed))
        before = {path: path.read_bytes() for path in (overlay, self.settings_path(), self.home1 / ".claude/.harness-stamp")}
        result, output, confirmation = self.adopt_with_confirmation(dry_run=True)
        self.assertEqual(result, 0, output)
        confirmation.assert_not_called()
        for category in ('added: "voice"', 'removed: "model"', 'changed: "theme"'):
            self.assertIn(category, output)
        self.assertNotIn("hidden-value", output)
        self.assertNotIn("initial", output)
        for path, payload in before.items():
            self.assertEqual(path.read_bytes(), payload)
        result, output, confirmation = self.adopt_with_confirmation()
        self.assertEqual(result, 0, output)
        confirmation.assert_called_once()
        self.assertEqual(json.loads(overlay.read_bytes()), {
            "theme": "light", "voice": {"enabled": True}, "env": {"EXAMPLE": "hidden-value"}})
        self.assertEqual(json.loads(self.settings_path().read_bytes()), installed)
        self.assertEqual(self.gate(), "allow")

    def test_adopt_refuses_unattended_and_declined_confirmation(self) -> None:
        self.assertEqual(self.run_bootstrap(self.home1).returncode, 0)
        before = self.settings_path().read_bytes()
        result = self.run_bootstrap(self.home1, "--adopt")
        self.assertEqual(result.returncode, 1)
        self.assertIn("controlling terminal", result.stderr)
        self.assertFalse((self.repo / ".private/settings.json").exists())
        result, output, _ = self.adopt_with_confirmation(confirm=policy.PolicyError("owner declined preference adoption"))
        self.assertEqual(result, 1)
        self.assertIn("declined", output)
        self.assertEqual(self.settings_path().read_bytes(), before)

    def test_adoption_keeps_rendered_controlled_source_semantics(self) -> None:
        overlay = self.repo / ".private/settings.json"
        overlay.parent.mkdir()
        overlay.write_text(json.dumps({
            "theme": "dark", "voice": {"enabled": False},
            "env": {"EXAMPLE": "__HOME__/synthetic"},
            "permissions": {"deny": ["Bash(example-one)", "Bash(example-two)"]},
            "enabledPlugins": {"synthetic@market": True},
            "controlledExample": {"flags": [True, 1, False, 0], "object": {"a": 1, "b": 2}},
        }))
        self.assertEqual(self.run_bootstrap(self.home1).returncode, 0)
        module = self.bootstrap_module()
        renderer = module.load_renderer(self.repo)
        before = policy.loads_object(renderer.render(self.repo / "settings.json.template", overlay, str(self.home1.resolve())))
        installed = json.loads(self.settings_path().read_bytes())
        installed.pop("theme")
        installed["voice"] = {"enabled": True, "mode": "tap"}
        self.settings_path().write_text(json.dumps(installed))
        result, output, _ = self.adopt_with_confirmation()
        self.assertEqual(result, 0, output)
        after = policy.loads_object(renderer.render(self.repo / "settings.json.template", overlay, str(self.home1.resolve())))
        self.assertEqual(policy.managed_stamp(before), policy.managed_stamp(after))
        self.assertEqual(self.gate(), "allow")

    def test_adoption_rejects_a_proposal_that_changes_controlled_source_before_confirmation(self) -> None:
        self.assertEqual(self.run_bootstrap(self.home1).returncode, 0)
        module = self.bootstrap_module()
        before = self.settings_path().read_bytes()
        proposals = [b'{"env":{"EXAMPLE":"changed"}}', json.dumps({"hooks": {"SyntheticEvent": [
            {"hooks": [{"type": "command", "command": "synthetic-not-a-preference"}]}]}}).encode()]
        for proposal in proposals:
            output = io.StringIO()
            with mock.patch.dict(os.environ, {"HOME": str(self.home1)}):
                os.environ.pop("AI_TOOLKIT_CONFIG", None)
                with mock.patch.object(module, "adoption_overlay", return_value=(proposal, "")), \
                        mock.patch.object(module, "confirm_adoption") as confirmation, \
                        contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                    result = module.install(self.repo.resolve(), self.home1.resolve(), False, adopt=True)
            self.assertEqual(result, 1, output.getvalue())
            self.assertIn("would change controlled source", output.getvalue())
            confirmation.assert_not_called()
            self.assertEqual(self.settings_path().read_bytes(), before)
            self.assertFalse((self.repo / ".private/settings.json").exists())

    def test_confirmation_checks_terminal_and_exact_answer(self) -> None:
        module = self.bootstrap_module()
        for tty, answer, accepted in [(True, b"adopt\n", True), (True, b"yes\n", False),
                                      (True, b"", False), (False, b"adopt\n", False)]:
            with self.subTest(tty=tty, answer=answer):
                terminal = mock.MagicMock()
                terminal.__enter__.return_value = terminal
                terminal.isatty.return_value = tty
                terminal.readline.return_value = answer
                with mock.patch("builtins.open", return_value=terminal) as opened:
                    if accepted:
                        module.confirm_adoption('changed: "theme"')
                    else:
                        with self.assertRaises(ValueError):
                            module.confirm_adoption('changed: "theme"')
                opened.assert_called_once_with("/dev/tty", "r+b", buffering=0)

    def test_actual_adoption_confirmation_on_controlling_pty(self) -> None:
        self.assertEqual(self.run_bootstrap(self.home1).returncode, 0)
        installed = json.loads(self.settings_path().read_bytes())
        installed["theme"] = "light"
        self.settings_path().write_text(json.dumps(installed))
        env = {**os.environ, "HOME": str(self.home1)}
        env.pop("AI_TOOLKIT_CONFIG", None)
        master, slave = pty.openpty()

        def attach_terminal():
            os.setsid()
            fcntl.ioctl(0, termios.TIOCSCTTY, 0)

        process = subprocess.Popen(["bash", str(self.repo / "bootstrap.sh"), "--adopt"],
                                   stdin=slave, stdout=slave, stderr=slave, env=env,
                                   preexec_fn=attach_terminal)
        os.close(slave)
        output = b""
        answered = False
        deadline = time.monotonic() + 10
        try:
            while time.monotonic() < deadline:
                if not select.select([master], [], [], 0.1)[0]:
                    continue
                try:
                    chunk = os.read(master, 65536)
                except OSError as exc:
                    if exc.errno != errno.EIO:
                        raise
                    break
                if not chunk:
                    break
                output += chunk
                if not answered and b"Type adopt to confirm: " in output:
                    os.write(master, b"adopt\n")
                    answered = True
            self.assertTrue(answered, output.decode())
            self.assertEqual(process.wait(timeout=2), 0, output.decode())
            self.assertEqual(json.loads((self.repo / ".private/settings.json").read_bytes())["theme"], "light")
        finally:
            os.close(master)
            if process.poll() is None:
                process.kill()
            process.wait()

    def test_adoption_late_failure_restores_overlay_settings_stamp_links_and_config(self) -> None:
        self.assertEqual(self.run_bootstrap(self.home1).returncode, 0)
        overlay = self.repo / ".private/settings.json"
        overlay.write_text('{"theme":"dark"}')
        installed = json.loads(self.settings_path().read_bytes())
        installed["theme"] = "light"
        self.settings_path().write_text(json.dumps(installed))
        paths = (overlay, self.settings_path(), self.home1 / ".claude/.harness-stamp", self.repo / ".git/config")
        before = {path: path.read_bytes() for path in paths}
        links = {path: os.readlink(path) for path in (self.home1 / ".claude").iterdir() if path.is_symlink()}
        result, output, _ = self.adopt_with_confirmation(failpoint="after-settings")
        self.assertEqual(result, 1, output)
        self.assertIn("rolled back", output)
        for path, payload in before.items():
            self.assertEqual(path.read_bytes(), payload)
        for path, target in links.items():
            self.assertEqual(os.readlink(path), target)

    def test_concurrent_settings_or_overlay_edit_during_confirmation_is_preserved(self) -> None:
        self.assertEqual(self.run_bootstrap(self.home1).returncode, 0)
        overlay = self.repo / ".private/settings.json"
        overlay.write_text('{}')
        for path in (self.settings_path(), overlay):
            with self.subTest(path=path.name):
                def edit(_):
                    settings = json.loads(path.read_bytes())
                    settings["theme"] = "light"
                    path.write_text(json.dumps(settings))
                result, output, _ = self.adopt_with_confirmation(confirm=edit)
                self.assertEqual(result, 1, output)
                self.assertIn("changed since preflight", output)
                self.assertEqual(json.loads(path.read_bytes())["theme"], "light")

    def test_configured_external_overlay_adoption_and_symlink_refusal(self) -> None:
        overlay = self.base / "external-settings.json"
        overlay.write_text('{"theme":"dark","env":{"EXAMPLE":"keep"}}')
        private = self.repo / ".private"
        private.mkdir()
        config = private / "config.json"
        config.write_text(json.dumps({"settings_overlay": str(overlay)}))
        self.assertEqual(self.run_bootstrap(self.home1).returncode, 0)
        installed = json.loads(self.settings_path().read_bytes())
        installed["theme"] = "light"
        self.settings_path().write_text(json.dumps(installed))
        result, output, _ = self.adopt_with_confirmation()
        self.assertEqual(result, 0, output)
        self.assertEqual(json.loads(overlay.read_bytes())["theme"], "light")
        link = private / "overlay-link.json"
        link.symlink_to(overlay)
        config.write_text(json.dumps({"settings_overlay": str(link)}))
        before = overlay.read_bytes()
        result, output, confirmation = self.adopt_with_confirmation()
        self.assertEqual(result, 1, output)
        self.assertIn("symlink", output)
        confirmation.assert_not_called()
        self.assertTrue(link.is_symlink())
        self.assertEqual(overlay.read_bytes(), before)

    def test_concurrent_edit_during_link_install_is_not_overwritten_by_deploy_or_rollback(self) -> None:
        self.assertEqual(self.run_bootstrap(self.home1).returncode, 0)
        overlay = self.repo / ".private/settings.json"
        overlay.write_text('{}')
        stamp = self.home1 / ".claude/.harness-stamp"
        before_stamp = stamp.read_bytes()
        for path in (self.settings_path(), overlay):
            with self.subTest(path=path):
                def edit(name):
                    if name == "after-links":
                        settings = json.loads(path.read_bytes())
                        settings["theme"] = "light"
                        path.write_text(json.dumps(settings))
                result, output, _ = self.adopt_with_confirmation(during_install=edit)
                self.assertEqual(result, 1, output)
                self.assertIn("changed since preflight", output)
                self.assertEqual(json.loads(path.read_bytes())["theme"], "light")
                self.assertEqual(stamp.read_bytes(), before_stamp)

    def test_adoption_rollback_removes_new_overlay(self) -> None:
        self.assertEqual(self.run_bootstrap(self.home1).returncode, 0)
        overlay = self.repo / ".private/settings.json"
        result, output, _ = self.adopt_with_confirmation(failpoint="after-settings")
        self.assertEqual(result, 1, output)
        self.assertFalse(overlay.exists())

    def test_malformed_settings_overlay_or_config_fails_without_writes(self) -> None:
        self.assertEqual(self.run_bootstrap(self.home1).returncode, 0)
        original = self.settings_path().read_bytes()
        stamp = self.home1 / ".claude/.harness-stamp"
        before_stamp = stamp.read_bytes()
        overlay = self.repo / ".private/settings.json"
        config = self.repo / ".private/config.json"
        for path in (self.settings_path(), overlay, config):
            for payload in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}', '{"x":1e999}'):
                with self.subTest(path=path.name, payload=payload):
                    self.settings_path().write_bytes(original)
                    path.write_text(payload)
                    result = self.run_bootstrap(self.home1)
                    self.assertEqual(result.returncode, 1)
                    self.assertEqual(path.read_text(), payload)
                    self.assertEqual(stamp.read_bytes(), before_stamp)
                    if path != self.settings_path():
                        self.assertEqual(self.settings_path().read_bytes(), original)
                        path.unlink()

    def test_separate_installer_add_update_delete_coexists_with_repeat_dry_run_and_adopt(self) -> None:
        overlay = self.repo / ".private/settings.json"
        overlay.parent.mkdir()
        overlay.write_text('{"model":"source-default","env":{"EXAMPLE":"keep"}}')
        self.assertEqual(self.run_bootstrap(self.home1).returncode, 0)
        stamp = self.home1 / ".claude/.harness-stamp"
        source_stamp = stamp.read_bytes()
        source_baseline = self.baseline_path().read_bytes()
        self.assertEqual(self.baseline_path().stat().st_mode & 0o777, 0o600)
        for action in ("append", "update", "delete"):
            with self.subTest(action=action):
                self.independent_installer(action)
                before = self.settings_path().read_bytes()
                wanted = json.loads(before)
                self.assertEqual(self.gate(), "allow")
                dry = self.run_bootstrap(self.home1, "--dry-run")
                self.assertEqual(dry.returncode, 0, dry.stderr)
                if action != "delete":
                    self.assertIn('hooks event "PermissionRequest": preserve 1 additional entries', dry.stdout)
                    self.assertIn("independently trusted", dry.stdout)
                self.assertNotIn("synthetic-independent", dry.stdout)
                self.assertEqual(self.settings_path().read_bytes(), before)
                self.assertEqual(self.baseline_path().read_bytes(), source_baseline)
                result = self.run_bootstrap(self.home1)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(self.settings_path().read_bytes()), wanted)
                repeated = self.settings_path().read_bytes()
                self.assertEqual(self.run_bootstrap(self.home1).returncode, 0)
                self.assertEqual(self.settings_path().read_bytes(), repeated)
                result, output, confirmation = self.adopt_with_confirmation()
                self.assertEqual(result, 0, output)
                confirmation.assert_called_once()
                self.assertEqual(json.loads(self.settings_path().read_bytes()), wanted)
                adopted = json.loads(overlay.read_bytes())
                self.assertEqual(adopted, {"theme": "light", "env": {"EXAMPLE": "keep"}})
                self.assertEqual(stamp.read_bytes(), source_stamp)
                self.assertEqual(self.baseline_path().read_bytes(), source_baseline)

    def test_baseline_updates_only_old_owned_entries_preserving_independent_content(self) -> None:
        overlay = self.repo / ".private/settings.json"
        overlay.parent.mkdir()
        overlay.write_text(json.dumps({"hooks": {"Stop": [{"hooks": [
            {"type": "command", "command": "synthetic-private-owned-old"}]}]}}))
        self.assertEqual(self.run_bootstrap(self.home1).returncode, 0)
        self.independent_installer()
        installed_before = json.loads(self.settings_path().read_bytes())
        old_stamp = (self.home1 / ".claude/.harness-stamp").read_bytes()
        template = self.repo / "settings.json.template"
        source = json.loads(template.read_bytes())
        source["hooks"]["PreToolUse"][0]["hooks"][0]["command"] = "synthetic-owned-renamed"
        source["hooks"]["PreToolUse"].pop(1)
        source["hooks"]["PreToolUse"].append({"matcher": "Read", "hooks": [
            {"type": "command", "command": "synthetic-owned-added", "timeout": 17}]})
        del source["hooks"]["SessionStart"]
        source["hooks"]["NewSyntheticEvent"] = [{"hooks": [{"type": "command", "command": "synthetic-owned-new-event"}]}]
        source["env"] = {"EXAMPLE": "reviewed-source-update"}
        template.write_text(json.dumps(source))
        private = json.loads(overlay.read_bytes())
        private["hooks"]["Stop"][0]["hooks"][0]["command"] = "synthetic-private-owned-new"
        overlay.write_text(json.dumps(private))
        self.assertEqual(self.gate(), "deny")
        dry = self.run_bootstrap(self.home1, "--dry-run")
        self.assertEqual(dry.returncode, 0, dry.stderr)
        self.assertIn('hooks event "PreToolUse" source entry 1 changed', dry.stdout)
        self.assertNotIn("synthetic-owned-renamed", dry.stdout)
        self.assertEqual(json.loads(self.settings_path().read_bytes()), installed_before)
        result = self.run_bootstrap(self.home1)
        self.assertEqual(result.returncode, 0, result.stderr)
        installed = json.loads(self.settings_path().read_bytes())
        self.assertEqual(installed["hooks"]["PermissionRequest"], installed_before["hooks"]["PermissionRequest"])
        self.assertEqual(installed["hooks"]["PreToolUse"][-1], installed_before["hooks"]["PreToolUse"][-1])
        residual = next(group for group in installed["hooks"]["PreToolUse"]
                        if group["hooks"] == [installed_before["hooks"]["PreToolUse"][0]["hooks"][-1]])
        self.assertEqual({key: value for key, value in residual.items() if key != "hooks"},
                         {key: value for key, value in installed_before["hooks"]["PreToolUse"][0].items() if key != "hooks"})
        self.assertEqual(installed["hooks"]["SessionStart"], [])
        self.assertEqual(installed["hooks"]["Stop"][0]["hooks"][0]["command"], "synthetic-private-owned-new")
        self.assertEqual(installed["env"], {"EXAMPLE": "reviewed-source-update"})
        self.assertEqual(policy.preferences(installed), policy.preferences(installed_before))
        record = json.loads(self.baseline_path().read_bytes())
        self.assertEqual(record["version"], 1)
        self.assertNotIn("synthetic-independent", self.baseline_path().read_text())
        self.assertNotEqual((self.home1 / ".claude/.harness-stamp").read_bytes(), old_stamp)
        self.assertTrue(policy.matches_expected(installed, record["controlled"]))
        self.assertEqual(self.gate(), "allow")
        before_repeat = self.settings_path().read_bytes()
        self.assertEqual(self.run_bootstrap(self.home1).returncode, 0)
        self.assertEqual(self.settings_path().read_bytes(), before_repeat)

    def test_missing_old_owned_entry_cannot_be_hidden_by_removing_it_from_new_source(self) -> None:
        self.assertEqual(self.run_bootstrap(self.home1).returncode, 0)
        self.independent_installer()
        installed = json.loads(self.settings_path().read_bytes())
        installed["hooks"]["PreToolUse"].pop(1)
        self.settings_path().write_text(json.dumps(installed))
        template = self.repo / "settings.json.template"
        source = json.loads(template.read_bytes())
        source["hooks"]["PreToolUse"].pop(1)
        template.write_text(json.dumps(source))
        before = {path: path.read_bytes() for path in (self.settings_path(), self.baseline_path(), self.home1 / ".claude/.harness-stamp")}
        result, output, confirmation = self.adopt_with_confirmation(dry_run=True)
        self.assertEqual(result, 1, output)
        self.assertIn('hooks event "PreToolUse" source entry 2', output)
        confirmation.assert_not_called()
        for path, payload in before.items():
            self.assertEqual(path.read_bytes(), payload)

    def test_source_update_cannot_claim_an_identical_independent_hook(self) -> None:
        self.assertEqual(self.run_bootstrap(self.home1).returncode, 0)
        self.independent_installer()
        installed = json.loads(self.settings_path().read_bytes())
        template = self.repo / "settings.json.template"
        source = json.loads(template.read_bytes())
        source["hooks"]["PermissionRequest"] = installed["hooks"]["PermissionRequest"]
        template.write_text(json.dumps(source))
        before = {path: path.read_bytes() for path in (self.settings_path(), self.baseline_path(), self.home1 / ".claude/.harness-stamp")}
        result, output, confirmation = self.adopt_with_confirmation()
        self.assertEqual(result, 1, output)
        self.assertIn('hooks event "PermissionRequest" source entry 1 has ambiguous duplicate ownership', output)
        confirmation.assert_not_called()
        for path, payload in before.items():
            self.assertEqual(path.read_bytes(), payload)

    def test_nonhook_drift_remains_controlled_with_external_entries(self) -> None:
        self.assertEqual(self.run_bootstrap(self.home1).returncode, 0)
        self.independent_installer()
        original = json.loads(self.settings_path().read_bytes())
        for key, value in {"permissions": {}, "env": {"EXAMPLE": "hidden-value"},
                           "disableAllHooks": True, "enabledPlugins": {}, "unknown": True}.items():
            with self.subTest(key=key):
                installed = copy.deepcopy(original)
                installed[key] = value
                self.settings_path().write_text(json.dumps(installed))
                result, output, confirmation = self.adopt_with_confirmation()
                self.assertEqual(result, 1, output)
                confirmation.assert_not_called()
                self.assertIn(json.dumps(key), output)
                self.assertNotIn("hidden-value", output)

    def test_no_baseline_upgrade_with_independent_hooks_accepts_current_source_only(self) -> None:
        self.assertEqual(self.run_bootstrap(self.home1).returncode, 0)
        renderer = self.bootstrap_module().load_renderer(self.repo)
        source_bytes = renderer.render(self.repo / "settings.json.template", None, str(self.home1.resolve()))
        stamp = self.home1 / ".claude/.harness-stamp"
        self.independent_installer()
        wanted = json.loads(self.settings_path().read_bytes())
        for value in (hashlib.sha256(source_bytes).hexdigest(), policy.managed_stamp(policy.loads_object(source_bytes))):
            with self.subTest(stamp=value[:12]):
                self.baseline_path().unlink()
                stamp.write_text(value)
                self.assertEqual(self.gate(), "allow")
                result = self.run_bootstrap(self.home1)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(self.settings_path().read_bytes()), wanted)
                record = json.loads(self.baseline_path().read_bytes())
                self.assertEqual(record["controlled"], policy.controlled(policy.loads_object(source_bytes)))
        self.baseline_path().unlink()
        template = self.repo / "settings.json.template"
        source = json.loads(template.read_bytes())
        source["hooks"]["PreToolUse"][0]["hooks"][0]["command"] = "synthetic-pending-source-update"
        template.write_text(json.dumps(source))
        for value in (hashlib.sha256(source_bytes).hexdigest(), policy.managed_stamp(policy.loads_object(source_bytes)), "f" * 64):
            stamp.write_text(value)
            result = self.run_bootstrap(self.home1)
            self.assertEqual(result.returncode, 1)
            self.assertIn("no managed source baseline", result.stderr)
            self.assertEqual(json.loads(self.settings_path().read_bytes()), wanted)
            self.assertFalse(self.baseline_path().exists())

    def test_old_full_managed_hash_without_additions_can_upgrade_during_source_update(self) -> None:
        self.assertEqual(self.run_bootstrap(self.home1).returncode, 0)
        self.baseline_path().unlink()
        template = self.repo / "settings.json.template"
        source = json.loads(template.read_bytes())
        source["hooks"]["PreToolUse"][0]["hooks"][0]["command"] = "synthetic-new-owned"
        source["env"] = {"EXAMPLE": "updated-source"}
        template.write_text(json.dumps(source))
        result = self.run_bootstrap(self.home1)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.baseline_path().is_file())
        self.assertEqual(self.gate(), "allow")

    def test_invalid_or_unbound_baselines_fail_even_when_current_source_matches(self) -> None:
        self.assertEqual(self.run_bootstrap(self.home1).returncode, 0)
        self.independent_installer()
        record = json.loads(self.baseline_path().read_bytes())
        corrupt = copy.deepcopy(record)
        corrupt["controlled"]["hooks"]["PreToolUse"][0]["hooks"][0]["command"] = "hidden-private-command"
        invalid = ["not-json", "[]", '{"version":1,"version":1,"controlled":{}}', '{"version":NaN}',
                   json.dumps({**record, "version": 2}), json.dumps({**record, "version": True}),
                   json.dumps({**record, "extra": True}), json.dumps(corrupt),
                   json.dumps({"version": 1, "controlled": {"model": "hidden-model-id"}}),
                   json.dumps({"version": 1, "controlled": {"hooks": {"PreToolUse": [{}]}}})]
        settings_before = self.settings_path().read_bytes()
        stamp = self.home1 / ".claude/.harness-stamp"
        stamp_before = stamp.read_bytes()
        for text in invalid:
            self.baseline_path().write_text(text)
            result, output, confirmation = self.adopt_with_confirmation()
            self.assertEqual(result, 1, output)
            self.assertIn("managed source baseline", output)
            self.assertNotIn("hidden-private-command", output)
            self.assertNotIn("hidden-model-id", output)
            confirmation.assert_not_called()
            self.assertEqual(self.baseline_path().read_text(), text)
            self.assertEqual(self.settings_path().read_bytes(), settings_before)
            self.assertEqual(stamp.read_bytes(), stamp_before)

    def test_formerly_controlled_dialog_baseline_upgrades_without_changing_installed_choice(self) -> None:
        overlay = self.repo / ".private/settings.json"
        overlay.parent.mkdir()
        overlay.write_text('{"skipDangerousModePermissionPrompt":true}')
        self.assertEqual(self.run_bootstrap(self.home1).returncode, 0)
        old_source = json.loads(self.baseline_path().read_bytes())["controlled"]
        old_source["skipDangerousModePermissionPrompt"] = True
        old_stamp = "managed-v1:" + hashlib.sha256(policy.canonical(old_source)).hexdigest()
        self.independent_installer()
        original = json.loads(self.settings_path().read_bytes())
        overlay_before = overlay.read_bytes()
        stamp = self.home1 / ".claude/.harness-stamp"
        for value in (True, False, None):
            with self.subTest(value=value):
                installed = copy.deepcopy(original)
                if value is None:
                    installed.pop("skipDangerousModePermissionPrompt")
                else:
                    installed["skipDangerousModePermissionPrompt"] = value
                self.settings_path().write_text(json.dumps(installed))
                self.baseline_path().write_text(json.dumps({"version": 1, "controlled": old_source}))
                stamp.write_text(old_stamp)
                before = self.settings_path().read_bytes()
                preview = self.run_bootstrap(self.home1, "--dry-run")
                self.assertEqual(preview.returncode, 0, preview.stderr)
                self.assertEqual(self.settings_path().read_bytes(), before)
                result = self.run_bootstrap(self.home1)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(self.settings_path().read_bytes()), installed)
                self.assertEqual(overlay.read_bytes(), overlay_before)
                record = json.loads(self.baseline_path().read_bytes())
                self.assertNotIn("skipDangerousModePermissionPrompt", record["controlled"])
                self.assertEqual(stamp.read_text().strip(), policy.managed_stamp(record["controlled"]))
                self.assertEqual(self.gate(), "allow")

    def test_former_dialog_baseline_still_requires_original_binding_and_boolean_shape(self) -> None:
        self.assertEqual(self.run_bootstrap(self.home1).returncode, 0)
        source = json.loads(self.baseline_path().read_bytes())["controlled"]
        stamp = self.home1 / ".claude/.harness-stamp"
        settings_before = self.settings_path().read_bytes()
        cases = [({**source, "skipDangerousModePermissionPrompt": True}, policy.managed_stamp(source))]
        for value in (None, 0, 1, "true", {}, []):
            bad = {**source, "skipDangerousModePermissionPrompt": value}
            cases.append((bad, "managed-v1:" + hashlib.sha256(policy.canonical(bad)).hexdigest()))
        other_preference = {**source, "skipDangerousModePermissionPrompt": True, "theme": "dark"}
        cases.append((other_preference, "managed-v1:" + hashlib.sha256(policy.canonical(other_preference)).hexdigest()))
        for record, saved_stamp in cases:
            with self.subTest(record_keys=record.keys()):
                text = json.dumps({"version": 1, "controlled": record})
                self.baseline_path().write_text(text)
                stamp.write_text(saved_stamp)
                failed = self.run_bootstrap(self.home1)
                self.assertEqual(failed.returncode, 1)
                self.assertIn("managed source baseline", failed.stderr)
                self.assertEqual(self.settings_path().read_bytes(), settings_before)
                self.assertEqual(self.baseline_path().read_text(), text)
                self.assertEqual(stamp.read_text(), saved_stamp)

    def test_baseline_symlink_directory_and_legacy_stamp_binding_are_refused(self) -> None:
        self.assertEqual(self.run_bootstrap(self.home1).returncode, 0)
        baseline = self.baseline_path().read_bytes()
        external = self.base / "external-baseline.json"
        external.write_bytes(baseline)
        self.baseline_path().unlink()
        self.baseline_path().symlink_to(external)
        failed = self.run_bootstrap(self.home1)
        self.assertEqual(failed.returncode, 1)
        self.assertIn("regular file", failed.stderr)
        self.assertTrue(self.baseline_path().is_symlink())
        self.assertEqual(external.read_bytes(), baseline)
        self.baseline_path().unlink()
        self.baseline_path().mkdir()
        self.assertEqual(self.run_bootstrap(self.home1).returncode, 1)
        self.baseline_path().rmdir()
        self.baseline_path().write_bytes(baseline)
        (self.home1 / ".claude/.harness-stamp").write_text("f" * 64)
        failed = self.run_bootstrap(self.home1)
        self.assertEqual(failed.returncode, 1)
        self.assertIn("not bound", failed.stderr)

    def test_source_update_rollback_restores_baseline_settings_stamp_overlay_and_links(self) -> None:
        self.assertEqual(self.run_bootstrap(self.home1).returncode, 0)
        self.independent_installer()
        overlay = self.repo / ".private/settings.json"
        overlay.write_text('{"theme":"dark"}')
        template = self.repo / "settings.json.template"
        source = json.loads(template.read_bytes())
        source["env"] = {"EXAMPLE": "new-source"}
        source["hooks"]["PreToolUse"][0]["hooks"][0]["command"] = "synthetic-owned-new"
        template.write_text(json.dumps(source))
        paths = (self.settings_path(), self.baseline_path(), self.home1 / ".claude/.harness-stamp", overlay, self.repo / ".git/config")
        before = {path: path.read_bytes() for path in paths}
        links = {path: os.readlink(path) for path in (self.home1 / ".claude").iterdir() if path.is_symlink()}
        for adopt in (False, True):
            with self.subTest(adopt=adopt):
                if adopt:
                    result, output, _ = self.adopt_with_confirmation(failpoint="after-settings")
                else:
                    process = self.run_bootstrap(self.home1, env_extra={"AI_TOOLKIT_BOOTSTRAP_FAILPOINT": "after-settings"})
                    result, output = process.returncode, process.stderr
                self.assertEqual(result, 1, output)
                self.assertIn("rolled back", output)
                for path, payload in before.items():
                    self.assertEqual(path.read_bytes(), payload, str(path))
                for path, target in links.items():
                    self.assertEqual(os.readlink(path), target)
                self.assertEqual(self.baseline_path().stat().st_mode & 0o777, 0o600)

    def test_concurrent_independent_installer_edit_during_confirmation_or_links_is_preserved(self) -> None:
        self.assertEqual(self.run_bootstrap(self.home1).returncode, 0)
        original = self.settings_path().read_bytes()
        baseline_before = self.baseline_path().read_bytes()
        for stage in ("confirmation", "after-links"):
            with self.subTest(stage=stage):
                self.settings_path().write_bytes(original)
                def append(_):
                    self.independent_installer()
                def after_links(name):
                    if name == "after-links":
                        append(name)
                result, output, _ = self.adopt_with_confirmation(
                    confirm=append if stage == "confirmation" else None,
                    during_install=after_links if stage == "after-links" else None)
                self.assertEqual(result, 1, output)
                self.assertIn("changed since preflight", output)
                wanted = json.loads(self.settings_path().read_bytes())
                self.assertIn("PermissionRequest", wanted["hooks"])
                self.assertEqual(self.baseline_path().read_bytes(), baseline_before)
                self.assertEqual(self.gate(), "allow")
                self.assertEqual(self.run_bootstrap(self.home1).returncode, 0)
                self.assertEqual(json.loads(self.settings_path().read_bytes()), wanted)

    def test_concurrent_baseline_edit_is_detected_and_not_rolled_back_over(self) -> None:
        self.assertEqual(self.run_bootstrap(self.home1).returncode, 0)
        settings_before = self.settings_path().read_bytes()
        baseline_before = self.baseline_path().read_bytes()
        for stage in ("confirmation", "after-links"):
            self.baseline_path().write_bytes(baseline_before)
            def edit(_):
                self.baseline_path().write_bytes(baseline_before + b"\n")
            def after_links(name):
                if name == "after-links":
                    edit(name)
            result, output, _ = self.adopt_with_confirmation(
                confirm=edit if stage == "confirmation" else None,
                during_install=after_links if stage == "after-links" else None)
            self.assertEqual(result, 1, output)
            self.assertIn(".harness-managed.json", output)
            self.assertEqual(self.baseline_path().read_bytes(), baseline_before + b"\n")
            self.assertEqual(self.settings_path().read_bytes(), settings_before)

    def test_fresh_install_failure_removes_new_baseline(self) -> None:
        result = self.run_bootstrap(self.home1, env_extra={"AI_TOOLKIT_BOOTSTRAP_FAILPOINT": "after-settings"})
        self.assertEqual(result.returncode, 1)
        self.assertFalse(self.baseline_path().exists())
        self.assertFalse(self.settings_path().exists())


if __name__ == "__main__":
    unittest.main()
