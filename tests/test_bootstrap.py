#!/usr/bin/env python3
"""Isolated installer acceptance fixtures; never targets the real user HOME."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


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
                              capture_output=True, text=True, env=env, check=False)

    def test_empty_home_install_and_repeat_are_idempotent(self) -> None:
        result = self.run_bootstrap(self.home1)
        self.assertEqual(result.returncode, 0, result.stderr)
        claude = self.home1 / ".claude"
        for name in ("CLAUDE.md", "agents", "hooks", "skills", "commands", "statusline-command.sh", "memory"):
            self.assertTrue((claude / name).is_symlink(), name)
        settings = claude / "settings.json"
        stamp = claude / ".harness-stamp"
        self.assertEqual(hashlib.sha256(settings.read_bytes()).hexdigest(), stamp.read_text().strip())
        self.assertTrue((self.repo / ".private" / "rules.md").is_file())
        first = settings.read_bytes()
        again = self.run_bootstrap(self.home1)
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertEqual(settings.read_bytes(), first)
        self.assertEqual(hashlib.sha256(settings.read_bytes()).hexdigest(), stamp.read_text().strip())

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


if __name__ == "__main__":
    unittest.main()
