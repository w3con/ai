#!/usr/bin/env python3
"""Isolated migration acceptance fixtures using local bare repositories only."""

from __future__ import annotations

import hashlib
import io
import json
import os
import runpy
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
MIGRATOR = ROOT / "bin" / "migrate-public-release"


def legacy_style_heading() -> str:
    return "".join(chr(codepoint) for codepoint in (0x0421, 0x0442, 0x0438, 0x043B, 0x044C))


def cmd(argv: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None,
        check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True, check=False)
    if check and result.returncode:
        raise AssertionError(f"command failed: {argv[0]} {argv[1:]}\n{result.stderr}\n{result.stdout}")
    return result


def init_repo(path: Path, *, bare: bool = False) -> None:
    args = ["git", "init", "--quiet"]
    if bare:
        args.append("--bare")
    else:
        args.extend(["--initial-branch=main"])
    args.append(str(path))
    cmd(args)


def migration_test_environment(home: Path) -> dict[str, str]:
    """Isolate HOME without smuggling a scanner path through GITLEAKS_BIN."""
    env = dict(os.environ)
    env.pop("GITLEAKS_BIN", None)
    env["HOME"] = str(home)
    return env


def write_test_gitleaks(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/usr/bin/env python3\n"
                    "import json, re, subprocess, sys\n"
                    "from pathlib import Path\n"
                    "if len(sys.argv) > 1 and sys.argv[1] == 'version':\n"
                    "    print('8.24.3'); raise SystemExit(0)\n"
                    "if len(sys.argv) < 2 or sys.argv[1] != 'detect': raise SystemExit(2)\n"
                    "args=sys.argv[2:]; source=None; report=None; history=False\n"
                    "for i,arg in enumerate(args):\n"
                    "    if arg == '--source' and i+1 < len(args): source=args[i+1]\n"
                    "    if arg == '--report-path' and i+1 < len(args): report=args[i+1]\n"
                    "    if arg.startswith('--log-opts='): history=True\n"
                    "if not source or not report: raise SystemExit(2)\n"
                    "if history:\n"
                    "    proc=subprocess.run(['git','-C',source,'log','-p','--all'],capture_output=True,text=True)\n"
                    "    data=proc.stdout.splitlines()\n"
                    "    filename=source\n"
                    "else:\n"
                    "    data=[]; filename=source\n"
                    "    for item in Path(source).rglob('*'):\n"
                    "        if item.is_file():\n"
                    "            try: data.extend(item.read_text(encoding='utf-8',errors='ignore').splitlines())\n"
                    "            except OSError: pass\n"
                    "            filename=str(item)\n"
                    "pattern=re.compile(r\"(?:api_key|secret)\\s*=\\s*['\\\"]SYNTHETIC_(?:TOKEN_A{32}|HISTORY_B{32})\",re.I)\n"
                    "findings=[{'File':filename,'StartLine':n,'RuleID':'synthetic-test-secret'} for n,line in enumerate(data,1) if pattern.search(line)]\n"
                    "Path(report).write_text(json.dumps(findings),encoding='utf-8')\n"
                    "raise SystemExit(1 if findings else 0)\n", encoding="utf-8")
    path.chmod(0o700)


class MigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="toolkit-migration-test-")
        self.base = Path(self.temp.name)
        self.target = self.base / "checkout"
        self.outer = self.base / "checkout-alias"
        self.home = self.base / "home"
        self.bare = self.base / "release.git"
        self.release = self.base / "release-work"
        self.home.mkdir()
        write_test_gitleaks(self.home / ".cache/ai-toolkit/public-check/gitleaks-8.24.3/gitleaks")
        self.make_old_checkout()
        self.make_release()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def make_old_checkout(self) -> None:
        init_repo(self.target)
        (self.target / "bin").mkdir()
        (self.target / "hooks").mkdir()
        (self.target / "skills").mkdir()
        (self.target / ".private").mkdir()
        (self.target / ".gitignore").write_text(".env\n.private/\n", encoding="utf-8")
        (self.target / "tracked.txt").write_text("baseline\n", encoding="utf-8")
        (self.target / "settings.json.template").write_text(
            json.dumps({"tone": "neutral", "hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "hooks/git-sync-notice.sh"}]}]}}),
            encoding="utf-8")
        (self.target / ".private" / "settings.json").write_text(
            json.dumps({"tone": "neutral"}), encoding="utf-8")
        legacy_style_heading = "## How " + "you write"
        (self.target / "CLAUDE.md").write_text(
            "# Old configuration\n\n" + legacy_style_heading + "\n\nObsolete display preference.\n\n"
            "## Operations\n\nPreserve the user's local memory.\n@STYLE.md\n@.private/rules.md\n",
            encoding="utf-8")
        (self.target / ".private" / "rules.md").write_text(
            "# Local rules\n\n## Operations\n\nKeep the local data available.\n@STYLE.md\n",
            encoding="utf-8")
        (self.target / "hooks" / "git-sync-notice.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        (self.target / "hooks" / "local-hook.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        memory = self.target / "memory"
        memory.mkdir()
        (memory / "durable.md").write_text("synthetic memory\n", encoding="utf-8")
        private_tool = self.target / "bin" / "private-tool"
        private_tool.write_text("#!/bin/sh\nprintf synthetic\\n\n", encoding="utf-8")
        private_tool.chmod(0o700)
        private_skill = self.target / "skills" / "private-skill"
        private_skill.mkdir()
        (private_skill / "SKILL.md").write_text("synthetic skill\n", encoding="utf-8")
        (self.target / ".env").write_text("SYNTHETIC_LOCAL_VALUE=not-a-secret\n", encoding="utf-8")
        mapping = {
            "mappings": [
                {"source": "memory", "destination": "memory", "kind": "directory"},
                {"source": "bin/private-tool", "destination": "bin/private-tool", "kind": "file"},
                {"source": "skills/private-skill", "destination": "skills/private-skill", "kind": "directory"},
                {"source": "hooks/local-hook.sh", "destination": "hooks/local-hook.sh", "kind": "file"},
            ]
        }
        (self.target / ".private" / "migration-map.json").write_text(json.dumps(mapping), encoding="utf-8")
        cmd(["git", "-C", str(self.target), "add", ".gitignore", "tracked.txt", "settings.json.template",
             "CLAUDE.md", "hooks/git-sync-notice.sh"])
        cmd(["git", "-C", str(self.target), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
             "commit", "--quiet", "-m", "old baseline"])
        cmd(["git", "-C", str(self.target), "switch", "--quiet", "-c", "old-side"])
        (self.target / "old-side-only.txt").write_text("old branch recovery fixture\n", encoding="utf-8")
        cmd(["git", "-C", str(self.target), "add", "old-side-only.txt"])
        cmd(["git", "-C", str(self.target), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
             "commit", "--quiet", "-m", "old side fixture"])
        self.old_side_revision = cmd(["git", "-C", str(self.target), "rev-parse", "HEAD"]).stdout.strip()
        cmd(["git", "-C", str(self.target), "switch", "--quiet", "main"])
        self.old_revision = cmd(["git", "-C", str(self.target), "rev-parse", "HEAD"]).stdout.strip()
        (self.target / "tracked.txt").write_text("local modified content\n", encoding="utf-8")
        (self.target / "notes.txt").write_text("untracked local note\n", encoding="utf-8")
        home_claude = self.home / ".claude"
        home_claude.mkdir()
        old_settings = {
            "model": "synthetic-machine-model",
            "tone": "neutral",
            "enabledPlugins": ["synthetic-plugin"],
            "hooks": {"SessionStart": [{"hooks": [
                {"type": "command", "command": "bash " + str(self.target / "hooks/git-sync-notice.sh")},
                {"type": "command", "command": "bash /synthetic/custom-hook.sh"},
                {"type": "command", "command": "bash /synthetic/second-custom-hook.sh"},
            ]}]},
        }
        self.original_settings = (json.dumps(old_settings, sort_keys=True, indent=2) + "\n").encode()
        (home_claude / "settings.json").write_bytes(self.original_settings)
        self.original_stamp = b"synthetic-old-stamp\n"
        (home_claude / ".harness-stamp").write_bytes(self.original_stamp)
        for name in ("CLAUDE.md", "agents", "hooks", "skills", "commands", "statusline-command.sh"):
            source = self.target / name
            if source.exists():
                (home_claude / name).symlink_to(source, target_is_directory=source.is_dir())
        (home_claude / "memory").symlink_to(memory, target_is_directory=True)
        project_memory = home_claude / "projects" / "synthetic-project" / "memory"
        project_memory.mkdir(parents=True)
        (project_memory / "keep.md").write_text("synthetic project memory\n", encoding="utf-8")
        (home_claude / "projects" / "empty-project").mkdir()
        self.outer.symlink_to(self.target, target_is_directory=True)

    def make_release(self) -> None:
        self.release.mkdir()
        init_repo(self.release)
        (self.release / "bin").mkdir()
        (self.release / "hooks").mkdir()
        (self.release / "agents").mkdir()
        (self.release / "skills").mkdir()
        (self.release / "commands").mkdir()
        (self.release / "tests").mkdir()
        (self.release / ".gitignore").write_text(".env\n.private/\n__pycache__/\n", encoding="utf-8")
        (self.release / "tracked.txt").write_text("public baseline\n", encoding="utf-8")
        (self.release / "settings.json.template").write_text(json.dumps({
            "tone": "new-default",
            "hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "git-sync-notice.sh"}]}]},
            "permissions": {"allow": ["WebSearch"]},
        }), encoding="utf-8")
        (self.release / "bootstrap.sh").write_text("#!/bin/sh\nexec python3 bin/bootstrap.py --root \"$(pwd -P)\"\n", encoding="utf-8")
        (self.release / "CLAUDE.md").write_text("@STYLE.md\n@.private/rules.md\n", encoding="utf-8")
        (self.release / "STYLE.md").write_text("public style rules\n", encoding="utf-8")
        (self.release / "agents" / "sample.md").write_text("agent\n", encoding="utf-8")
        (self.release / "skills" / "sample.md").write_text("skill\n", encoding="utf-8")
        (self.release / "commands" / "sample.md").write_text("command\n", encoding="utf-8")
        (self.release / "statusline-command.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        (self.release / "hooks" / "workspace-root-notice.sh").write_text(
            "#!/bin/sh\nexit 0\n", encoding="utf-8")
        fake_bootstrap = r'''#!/usr/bin/env python3
import hashlib, json, os, sys
from pathlib import Path
root = Path(sys.argv[sys.argv.index("--root") + 1]).resolve()
home = Path.home()
if os.environ.get("TOOLKIT_FAIL_BOOTSTRAP_HOME") == str(home):
    raise SystemExit(71)
private = root / ".private"
private.mkdir(exist_ok=True)
rules = private / "rules.md"
if not rules.exists():
    rules.write_text("", encoding="utf-8")
config_path = Path(os.environ.get("AI_TOOLKIT_CONFIG", private / "config.json"))
config = json.loads(config_path.read_text()) if config_path.is_file() else {}
if os.environ.get("AI_TOOLKIT_CONFIG"):
    stored = private / "config.json"
    if stored.exists() or stored.is_symlink():
        if stored.is_symlink(): stored.unlink()
        else: stored.unlink()
    stored.symlink_to(config_path.resolve())
overlay = private / "settings.json"
base = json.loads((root / "settings.json.template").read_text())
if overlay.is_file():
    base.update(json.loads(overlay.read_text()))
base["home"] = str(home)
claude = home / ".claude"
claude.mkdir(parents=True, exist_ok=True)
settings = claude / "settings.json"
settings.write_text(json.dumps(base, sort_keys=True), encoding="utf-8")
(claude / ".harness-stamp").write_text(hashlib.sha256(settings.read_bytes()).hexdigest() + "\n")
for name in ("CLAUDE.md", "agents", "hooks", "skills", "commands", "statusline-command.sh"):
    source, target = root / name, claude / name
    if source.exists() or source.is_symlink():
        if target.is_symlink(): target.unlink()
        elif target.exists():
            if target.is_dir(): raise SystemExit("unexpected real directory")
            target.unlink()
        target.symlink_to(source, target_is_directory=source.is_dir())
for legacy, source in config.get("extensions", {}).items():
    target = root / legacy
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink(): target.unlink()
    source_path = Path(source)
    if not source_path.is_absolute(): source_path = root / source_path
    target.symlink_to(source_path, target_is_directory=source_path.is_dir())
memory = claude / "memory"
memory_root = Path(config.get("memory_root", home / ".local/share/ai-toolkit/memory"))
if memory.exists() or memory.is_symlink():
    if not memory.is_symlink() and memory.is_dir():
        pass
    else:
        memory.unlink()
        memory_root.mkdir(parents=True, exist_ok=True)
        memory.symlink_to(memory_root, target_is_directory=True)
else:
    memory_root.mkdir(parents=True, exist_ok=True)
    memory.symlink_to(memory_root, target_is_directory=True)
projects = claude / "projects"
if projects.is_dir():
    for project in projects.iterdir():
        p = project / "memory"
        if p.exists() and not p.is_symlink():
            raise SystemExit("non-empty project memory directory")
        if p.is_symlink(): p.unlink()
        p.symlink_to(memory_root, target_is_directory=True)
'''
        (self.release / "bin" / "bootstrap.py").write_text(fake_bootstrap, encoding="utf-8")
        (self.release / "bin" / "style-check").write_text(
            "def scan(roots):\n    return []\n", encoding="utf-8")
        (self.release / "hooks" / "git-sync-notice.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        (self.release / "tests" / "test_release.py").write_text(
            "import unittest\n\nclass ReleaseSmoke(unittest.TestCase):\n    def test_layout(self):\n        self.assertTrue(True)\n",
            encoding="utf-8")
        cmd(["git", "-C", str(self.release), "add", "."])
        cmd(["git", "-C", str(self.release), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
             "commit", "--quiet", "-m", "public release"])
        self.revision = cmd(["git", "-C", str(self.release), "rev-parse", "HEAD"]).stdout.strip()
        init_repo(self.bare, bare=True)
        cmd(["git", "-C", str(self.release), "remote", "add", "origin", str(self.bare)])
        cmd(["git", "-C", str(self.release), "push", "--quiet", "-u", "origin", "main"])

    def migrate(self, *, extra: list[str] | None = None,
                env_extra: dict[str, str] | None = None,
                target: Path | None = None) -> subprocess.CompletedProcess[str]:
        env = migration_test_environment(self.home)
        if env_extra:
            env.update(env_extra)
        args = [sys.executable, str(MIGRATOR), "--target", str(target or self.outer),
                "--repository", str(self.bare), "--revision", self.revision]
        if extra:
            args.extend(extra)
        return subprocess.run(args, env=env, capture_output=True, text=True, check=False)

    def signature(self, root: Path) -> tuple:
        result = []
        for path in sorted(root.rglob("*")):
            rel = path.relative_to(root).as_posix()
            st = path.lstat()
            if path.is_symlink():
                value = ("link", os.readlink(path), st.st_mtime_ns)
            elif path.is_file():
                value = ("file", hashlib.sha256(path.read_bytes()).hexdigest(), st.st_mode, st.st_mtime_ns)
            else:
                value = ("dir", st.st_mode, st.st_mtime_ns)
            result.append((rel, value))
        return tuple(result)

    def test_dry_run_performs_no_writes(self) -> None:
        before = self.signature(self.target)
        settings_before = self.original_settings
        result = self.migrate(extra=["--dry-run"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("no files, settings, lock, or recovery state will be written", result.stdout)
        self.assertEqual(self.signature(self.target), before)
        self.assertEqual((self.home / ".claude/settings.json").read_bytes(), settings_before)
        self.assertFalse((self.base / ".checkout.migration").exists())
        self.assertTrue(self.outer.is_symlink())

    def test_default_public_checks_run_in_an_isolated_home(self) -> None:
        env = migration_test_environment(self.home)
        self.assertNotIn("GITLEAKS_BIN", env)
        args = [sys.executable, str(MIGRATOR), "--target", str(self.outer),
                "--repository", str(self.bare), "--revision", self.revision]
        result = subprocess.run(args, env=env, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        preflight_home = self.base / ".checkout.migration/preflight-home"
        self.assertTrue((preflight_home / ".claude/settings.json").is_file())
        self.assertNotEqual(preflight_home.resolve(), self.home.resolve())
        self.assertFalse((preflight_home / ".cache/ai-toolkit/public-check/gitleaks-8.24.3/gitleaks").exists(),
                         "a verified original-home cache binary should be propagated, not reinstalled")

    def test_preflight_installs_pinned_scanner_into_isolated_home_when_no_cache_exists(self) -> None:
        module = runpy.run_path(str(MIGRATOR))
        stage = self.base / "installer-stage"
        (stage / "bin").mkdir(parents=True)
        script = stage / "bin/public-check"
        script.write_text("#!/usr/bin/env python3\n"
                          "import os, pathlib, sys\n"
                          "if sys.argv[1:] != ['install-gitleaks']: raise SystemExit(21)\n"
                          "home = pathlib.Path(os.environ['HOME'])\n"
                          "dest = home / '.cache/ai-toolkit/public-check/gitleaks-8.24.3/gitleaks'\n"
                          "dest.parent.mkdir(parents=True, exist_ok=True)\n"
                          "dest.write_text(\"#!/bin/sh\\nprintf '8.24.3\\\\n'\\n\")\n"
                          "dest.chmod(0o700)\n"
                          "(home / 'installer-called').write_text('yes')\n", encoding="utf-8")
        script.chmod(0o700)
        source_home = self.base / "no-scanner-home"
        check_home = self.base / "isolated-installer-home"
        source_home.mkdir()
        check_home.mkdir()
        source_env = migration_test_environment(source_home)
        isolated_env = dict(source_env, HOME=str(check_home))

        scanner = module["ensure_preflight_gitleaks"](stage, check_home, source_env, isolated_env)
        expected = check_home / ".cache/ai-toolkit/public-check/gitleaks-8.24.3/gitleaks"
        self.assertEqual(scanner, expected.resolve())
        self.assertTrue((check_home / "installer-called").is_file())
        self.assertEqual(subprocess.run([str(scanner), "version"], capture_output=True,
                                        text=True, check=True).stdout.strip(),
                         "8.24.3")

    def test_preflight_accepts_exact_gitleaks_version_and_rejects_neighbor_version(self) -> None:
        module = runpy.run_path(str(MIGRATOR))
        binary = self.base / "versioned-gitleaks"
        binary.write_text("#!/bin/sh\nprintf '8.24.3\\n'\n", encoding="utf-8")
        binary.chmod(0o700)
        source_env = {"HOME": str(self.home), "GITLEAKS_BIN": str(binary)}
        isolated_env = dict(source_env, HOME=str(self.base / "preflight-home"))
        stage = self.base / "unneeded-stage"
        check_home = self.base / "preflight-home"
        self.assertEqual(module["ensure_preflight_gitleaks"](
            stage, check_home, source_env, isolated_env), binary.resolve())

        binary.write_text("#!/bin/sh\nprintf '8.24.30\\n'\n", encoding="utf-8")
        binary.chmod(0o700)
        with self.assertRaisesRegex(module["MigrationError"], "GITLEAKS_BIN must identify"):
            module["ensure_preflight_gitleaks"](stage, check_home, source_env, isolated_env)

    def test_preflight_stops_when_pinned_scanner_installation_fails(self) -> None:
        module = runpy.run_path(str(MIGRATOR))
        stage = self.base / "failed-installer-stage"
        (stage / "bin").mkdir(parents=True)
        script = stage / "bin/public-check"
        script.write_text("#!/usr/bin/env python3\nraise SystemExit(17)\n", encoding="utf-8")
        script.chmod(0o700)
        source_home = self.base / "no-scanner-home-failure"
        check_home = self.base / "isolated-installer-failure"
        source_home.mkdir()
        check_home.mkdir()
        source_env = migration_test_environment(source_home)
        isolated_env = dict(source_env, HOME=str(check_home))

        with self.assertRaisesRegex(module["MigrationError"], "command failed"):
            module["ensure_preflight_gitleaks"](stage, check_home, source_env, isolated_env)
        self.assertFalse((check_home / ".cache/ai-toolkit/public-check/gitleaks-8.24.3/gitleaks").exists())
        self.assertFalse((source_home / ".cache").exists())

    @unittest.skipIf(os.environ.get("AI_TOOLKIT_MIGRATION_PREFLIGHT") == "1",
                     "the migrator preflight already runs the candidate test suite")
    def test_real_candidate_snapshot_installs_and_migrates_with_real_bootstrap(self) -> None:
        release_root = self.base / "actual-candidate"
        shutil.copytree(ROOT, release_root, symlinks=True,
                        ignore=shutil.ignore_patterns(".git", ".private", "__pycache__", "*.pyc"))
        init_repo(release_root)
        cmd(["git", "-C", str(release_root), "add", "--all"])
        cmd(["git", "-C", str(release_root), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
             "commit", "--quiet", "-m", "actual candidate snapshot"])
        actual_bare = self.base / "actual-candidate.git"
        init_repo(actual_bare, bare=True)
        cmd(["git", "-C", str(release_root), "remote", "add", "origin", str(actual_bare)])
        cmd(["git", "-C", str(release_root), "push", "--quiet", "-u", "origin", "main"])
        actual_revision = cmd(["git", "-C", str(release_root), "rev-parse", "HEAD"]).stdout.strip()

        env = migration_test_environment(self.home)
        self.assertNotIn("GITLEAKS_BIN", env)
        result = subprocess.run([
            sys.executable, str(MIGRATOR), "--target", str(self.outer),
            "--repository", str(actual_bare), "--revision", actual_revision,
        ], env=env, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        preflight_home = self.base / ".checkout.migration/preflight-home"
        self.assertFalse((preflight_home / ".cache/ai-toolkit/public-check/gitleaks-8.24.3/gitleaks").exists(),
                         "real-candidate CLI must use the only available default original-home cache")
        self.assertEqual(cmd(["git", "-C", str(self.target), "rev-parse", "HEAD"]).stdout.strip(), actual_revision)
        self.assertTrue((self.target / "commands/.gitkeep").is_file())
        self.assertEqual((self.home / ".claude/commands").resolve(), (self.target / "commands").resolve())
        self.assertEqual((self.target / "memory/durable.md").read_text(), "synthetic memory\n")
        self.assertEqual((self.target / "bin/private-tool").read_text(), "#!/bin/sh\nprintf synthetic\\n\n")
        self.assertTrue((self.target / "skills/private-skill/SKILL.md").is_file())
        self.assertTrue((self.target / "hooks/local-hook.sh").is_symlink())
        self.assertIn("Preserve the user's local memory.", (self.target / ".private/rules.md").read_text())
        settings = self.home / ".claude/settings.json"
        stamp = self.home / ".claude/.harness-stamp"
        self.assertEqual(hashlib.sha256(settings.read_bytes()).hexdigest(), stamp.read_text().strip())
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "git status"}})
        gate = subprocess.run(["bash", str(self.home / ".claude/hooks/harness-stamp-gate.sh")],
                              input=payload, text=True, capture_output=True, env=env, check=False)
        self.assertEqual(gate.returncode, 0, gate.stderr)
        gate_output = json.loads(gate.stdout)["hookSpecificOutput"]
        self.assertEqual(gate_output["permissionDecision"], "allow", gate_output.get("permissionDecisionReason"))

    def test_migration_preserves_local_data_settings_aliases_and_outer_symlink(self) -> None:
        result = self.migrate()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.outer.is_symlink())
        self.assertEqual(os.path.realpath(self.outer), os.path.realpath(self.target))
        self.assertEqual(cmd(["git", "-C", str(self.target), "rev-parse", "HEAD"]).stdout.strip(), self.revision)
        self.assertEqual((self.target / "tracked.txt").read_text(), "public baseline\n")
        self.assertEqual((self.target / ".env").read_text(), "SYNTHETIC_LOCAL_VALUE=not-a-secret\n")
        self.assertEqual((self.target / "memory/durable.md").read_text(), "synthetic memory\n")
        self.assertEqual((self.target / "bin/private-tool").read_text(), "#!/bin/sh\nprintf synthetic\\n\n")
        self.assertTrue((self.target / "skills/private-skill/SKILL.md").is_file())
        local_hook = self.target / "hooks/local-hook.sh"
        self.assertTrue(local_hook.is_symlink())
        self.assertEqual(local_hook.read_text(), "#!/bin/sh\nexit 0\n")
        self.assertTrue((self.target / ".git/info/exclude").is_file())
        self.assertTrue((self.target / ".private/rules.md").is_file())
        private_rules = (self.target / ".private/rules.md").read_text()
        self.assertIn("Preserve the user's local memory.", private_rules)
        self.assertIn("Keep the local data available.", private_rules)
        self.assertNotIn("@STYLE.md", private_rules)
        self.assertNotIn("short replies", private_rules)
        settings = json.loads((self.home / ".claude/settings.json").read_text())
        self.assertEqual(settings["model"], "synthetic-machine-model")
        self.assertEqual(settings["tone"], "neutral")
        self.assertEqual(settings["enabledPlugins"], ["synthetic-plugin"])
        self.assertEqual(settings["home"], os.path.realpath(self.home))
        session_hooks = [hook for entry in settings["hooks"]["SessionStart"]
                         for hook in entry.get("hooks", [])]
        session_commands = [hook.get("command", "") for hook in session_hooks]
        self.assertEqual(session_commands[0], "git-sync-notice.sh")
        self.assertEqual(session_commands[-2:], ["bash /synthetic/custom-hook.sh",
                                                 "bash /synthetic/second-custom-hook.sh"])
        self.assertTrue((self.home / ".claude/.harness-stamp").is_file())
        project_memory = self.home / ".claude/projects/synthetic-project/memory"
        self.assertTrue(project_memory.is_dir())
        self.assertEqual((project_memory / "keep.md").read_text(), "synthetic project memory\n")
        self.assertTrue((self.home / ".claude/projects/empty-project/memory").is_symlink())
        recovery = self.base / ".checkout.migration" / "old-checkout"
        self.assertEqual((recovery / "tracked.txt").read_text(), "local modified content\n")
        self.assertEqual((recovery / "notes.txt").read_text(), "untracked local note\n")
        self.assertEqual((recovery / ".env").read_text(), "SYNTHETIC_LOCAL_VALUE=not-a-secret\n")
        self.assertTrue((recovery / ".private/migration-map.json").is_file())
        self.assertIn("old-side", cmd(["git", "-C", str(recovery), "branch", "--list"]).stdout)
        self.assertEqual(cmd(["git", "-C", str(recovery), "show", "old-side:old-side-only.txt"]).stdout,
                         "old branch recovery fixture\n")
        state_dir = self.base / ".checkout.migration"
        self.assertEqual(state_dir.stat().st_mode & 0o777, 0o700)
        self.assertEqual((state_dir / "state.json").stat().st_mode & 0o777, 0o600)
        self.assertEqual((state_dir / "installed-settings.original").stat().st_mode & 0o777, 0o600)
        old_objects = cmd(["git", "-C", str(self.target), "cat-file", "-e", self.old_revision], check=False)
        self.assertNotEqual(old_objects.returncode, 0, "old repository objects leaked into the fresh clone")
        old_side_objects = cmd(["git", "-C", str(self.target), "cat-file", "-e", self.old_side_revision], check=False)
        self.assertNotEqual(old_side_objects.returncode, 0, "an old branch commit leaked into the fresh clone")
        self.assertEqual(cmd(["git", "-C", str(self.target), "check-ignore", "-q", ".env"], check=False).returncode, 0)
        self.assertEqual(cmd(["git", "-C", str(self.target), "check-ignore", "-q", "memory"], check=False).returncode, 0)

    def test_repeat_is_idempotent_and_does_not_create_second_recovery(self) -> None:
        first = self.migrate()
        self.assertEqual(first.returncode, 0, first.stderr)
        recovery = self.base / ".checkout.migration" / "old-checkout"
        original_stat = recovery.stat().st_ino
        second = self.migrate()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("already installed", second.stdout)
        self.assertEqual(recovery.stat().st_ino, original_stat)
        self.assertFalse((self.base / ".checkout.migration" / "failed-checkout").exists())

    def test_new_run_after_rollback_archives_prior_recovery(self) -> None:
        first = self.migrate()
        self.assertEqual(first.returncode, 0, first.stderr)
        rollback = subprocess.run([sys.executable, str(MIGRATOR), "--target", str(self.outer), "--rollback"],
                                  env={**os.environ, "HOME": str(self.home)}, capture_output=True, text=True)
        self.assertEqual(rollback.returncode, 0, rollback.stderr)
        previous = self.base / ".checkout.migration"
        old_state = json.loads((previous / "state.json").read_text())
        second = self.migrate()
        self.assertEqual(second.returncode, 0, second.stderr)
        archive = self.base / f".checkout.migration.history-{old_state['run_id']}"
        self.assertTrue((archive / "state.json").is_file())
        self.assertTrue((archive / f"failed-checkout-{old_state['run_id']}").is_dir())

    def test_next_public_release_preserves_active_private_aliases_and_prior_clean_history(self) -> None:
        first = self.migrate()
        self.assertEqual(first.returncode, 0, first.stderr)
        first_state = json.loads((self.base / ".checkout.migration/state.json").read_text())
        previous_public = self.revision
        (self.release / "release-note.txt").write_text("second synthetic release\n", encoding="utf-8")
        cmd(["git", "-C", str(self.release), "add", "release-note.txt"])
        cmd(["git", "-C", str(self.release), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
             "commit", "--quiet", "-m", "second public release"])
        cmd(["git", "-C", str(self.release), "push", "--quiet", "origin", "main"])
        self.revision = cmd(["git", "-C", str(self.release), "rev-parse", "HEAD"]).stdout.strip()
        interrupted = self.migrate(env_extra={"AI_TOOLKIT_MIGRATION_FAILPOINT": "after_terminal_archive"})
        self.assertEqual(interrupted.returncode, 86)
        self.assertTrue((self.base / ".checkout.migration/pending-upgrade.json").is_file())
        second = self.migrate()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(cmd(["git", "-C", str(self.target), "rev-parse", "HEAD"]).stdout.strip(), self.revision)
        self.assertEqual((self.target / "memory/durable.md").read_text(), "synthetic memory\n")
        self.assertEqual((self.target / "bin/private-tool").read_text(), "#!/bin/sh\nprintf synthetic\\n\n")
        self.assertTrue((self.target / "skills/private-skill/SKILL.md").is_file())
        self.assertTrue((self.target / "hooks/local-hook.sh").is_symlink())
        self.assertNotEqual(cmd(["git", "-C", str(self.target), "cat-file", "-e", self.old_revision], check=False).returncode, 0)
        archive = self.base / f".checkout.migration.history-{first_state['run_id']}"
        self.assertTrue((archive / "old-checkout/.private/migration-map.json").is_file())
        self.assertEqual(cmd(["git", "-C", str(self.target), "cat-file", "-e", previous_public], check=False).returncode, 0)

    def test_explicit_rollback_restores_old_checkout_settings_and_links(self) -> None:
        first = self.migrate()
        self.assertEqual(first.returncode, 0, first.stderr)
        result = subprocess.run([sys.executable, str(MIGRATOR), "--target", str(self.outer), "--rollback"],
                                env={**os.environ, "HOME": str(self.home)}, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.target / "tracked.txt").read_text(), "local modified content\n")
        self.assertEqual((self.target / "notes.txt").read_text(), "untracked local note\n")
        self.assertEqual((self.home / ".claude/settings.json").read_bytes(), self.original_settings)
        self.assertEqual((self.home / ".claude/.harness-stamp").read_bytes(), self.original_stamp)
        self.assertEqual(os.readlink(self.home / ".claude/hooks"), str(self.target / "hooks"))
        self.assertFalse((self.home / ".claude/projects/empty-project/memory").exists())
        self.assertFalse((self.base / ".checkout.migration" / "sync.paused").exists())
        self.assertEqual(len(list((self.base / ".checkout.migration").glob("failed-checkout-*"))), 1)

    def test_rollback_resumes_between_directory_renames(self) -> None:
        for point in ("after_rollback_new_move", "after_rollback_old_move"):
            with self.subTest(point=point):
                self.tearDown()
                self.setUp()
                migrated = self.migrate()
                self.assertEqual(migrated.returncode, 0, migrated.stderr)
                env = {**os.environ, "HOME": str(self.home), "AI_TOOLKIT_MIGRATION_FAILPOINT": point}
                interrupted = subprocess.run([sys.executable, str(MIGRATOR), "--target", str(self.outer), "--rollback"],
                                              env=env, capture_output=True, text=True)
                self.assertEqual(interrupted.returncode, 86)
                resumed = subprocess.run([sys.executable, str(MIGRATOR), "--target", str(self.outer), "--rollback"],
                                          env={**os.environ, "HOME": str(self.home)},
                                          capture_output=True, text=True)
                self.assertEqual(resumed.returncode, 0, resumed.stderr)
                self.assertEqual((self.target / "tracked.txt").read_text(), "local modified content\n")
                self.assertEqual((self.home / ".claude/settings.json").read_bytes(), self.original_settings)
                self.assertEqual((self.home / ".claude/.harness-stamp").read_bytes(), self.original_stamp)

    def test_failed_live_bootstrap_automatically_restores_old_installation(self) -> None:
        original = self.original_settings
        result = self.migrate(env_extra={"TOOLKIT_FAIL_BOOTSTRAP_HOME": os.path.realpath(self.home)})
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Rollback complete", result.stdout)
        self.assertEqual((self.target / "tracked.txt").read_text(), "local modified content\n")
        self.assertEqual((self.home / ".claude/settings.json").read_bytes(), original)
        self.assertEqual((self.home / ".claude/.harness-stamp").read_bytes(), self.original_stamp)
        failed = list((self.base / ".checkout.migration").glob("failed-checkout-*"))
        self.assertEqual(len(failed), 1)
        self.assertEqual((failed[0] / "tracked.txt").read_text(), "public baseline\n")
        self.assertFalse((self.base / ".checkout.migration" / "sync.paused").exists())

    def test_explicit_external_private_config_is_updated_and_restored_on_rollback(self) -> None:
        external = self.base / "private-config.json"
        original = json.dumps({
            "external_roots": ["/synthetic/private-root"],
            "sync": {"repositories": [str(self.target)], "pull_repositories": [str(self.target)]},
        }, sort_keys=True, indent=2).encode() + b"\n"
        external.write_bytes(original)
        result = self.migrate(env_extra={"AI_TOOLKIT_CONFIG": str(external)})
        self.assertEqual(result.returncode, 0, result.stderr)
        migrated = json.loads(external.read_text())
        self.assertEqual(migrated["external_roots"], ["/synthetic/private-root"])
        self.assertEqual(migrated["sync"]["pull_repositories"], [])
        self.assertTrue((self.target / ".private/config.json").is_symlink())
        self.assertEqual((self.target / ".private/config.json").resolve(), external.resolve())
        rollback = subprocess.run([sys.executable, str(MIGRATOR), "--target", str(self.outer), "--rollback"],
                                  env={**os.environ, "HOME": str(self.home)},
                                  capture_output=True, text=True, check=False)
        self.assertEqual(rollback.returncode, 0, rollback.stderr)
        self.assertEqual(external.read_bytes(), original)

    def test_external_private_profile_keeps_public_extension_and_mapped_memory(self) -> None:
        unavailable_memory = self.base / "unavailable-memory-root"
        external = self.base / "legacy-profile.json"
        external.write_text(json.dumps({
            "memory_root": str(unavailable_memory),
            "extensions": {"hooks/legacy-workspace-start.sh": "hooks/workspace-root-notice.sh"},
            "required_extensions": ["hooks/legacy-workspace-start.sh"],
            "sync": {"pull_repositories": [str(self.target)]},
        }), encoding="utf-8")
        result = self.migrate(env_extra={"AI_TOOLKIT_CONFIG": str(external)})
        self.assertEqual(result.returncode, 0, result.stderr)
        migrated = json.loads(external.read_text(encoding="utf-8"))
        self.assertEqual(migrated["sync"]["pull_repositories"], [])
        self.assertTrue(Path(migrated["memory_root"]).is_dir())
        self.assertEqual((Path(migrated["memory_root"]) / "durable.md").read_text(),
                         "synthetic memory\n")
        self.assertFalse(unavailable_memory.exists())
        self.assertEqual(migrated["extensions"]["hooks/legacy-workspace-start.sh"],
                         "hooks/workspace-root-notice.sh")
        self.assertTrue(Path(migrated["extensions"]["hooks/local-hook.sh"]).is_file())
        alias = self.target / "hooks/legacy-workspace-start.sh"
        self.assertTrue(alias.is_symlink())
        self.assertEqual(alias.resolve(), (self.target / "hooks/workspace-root-notice.sh").resolve())

    def test_required_private_extension_missing_generic_target_stops_before_switch(self) -> None:
        external = self.base / "legacy-profile.json"
        external.write_text(json.dumps({
            "extensions": {"hooks/legacy-workspace-start.sh": "hooks/not-in-release.sh"},
            "required_extensions": ["hooks/legacy-workspace-start.sh"],
        }), encoding="utf-8")
        result = self.migrate(env_extra={"AI_TOOLKIT_CONFIG": str(external)})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("required private extension", result.stderr)
        self.assertEqual((self.target / "tracked.txt").read_text(), "local modified content\n")
        self.assertFalse((self.base / ".checkout.migration/sync.paused").exists())

    def test_unmapped_unknown_extension_stays_in_recovery_and_is_not_reactivated(self) -> None:
        unknown_source = self.target / "hooks" / "unknown-local-hook.sh"
        unknown_source.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        external = self.base / "legacy-profile.json"
        external.write_text(json.dumps({
            "extensions": {"hooks/legacy-unknown-hook.sh": "hooks/unknown-local-hook.sh"},
        }), encoding="utf-8")
        result = self.migrate(env_extra={"AI_TOOLKIT_CONFIG": str(external)})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.target / "hooks/legacy-unknown-hook.sh").exists())
        recovery = self.base / ".checkout.migration" / "old-checkout"
        self.assertEqual((recovery / "hooks/unknown-local-hook.sh").read_text(),
                         "#!/bin/sh\nexit 0\n")
        state = json.loads((self.base / ".checkout.migration/state.json").read_text())
        self.assertEqual(state["unmapped_extensions"], [{
            "legacy": "hooks/legacy-unknown-hook.sh",
            "source": "hooks/unknown-local-hook.sh",
        }])

    def test_separate_installed_memory_root_is_preserved(self) -> None:
        external_memory = self.base / "separate-memory"
        external_memory.mkdir()
        (external_memory / "external.md").write_text("synthetic external store\n", encoding="utf-8")
        installed_memory = self.home / ".claude/memory"
        installed_memory.unlink()
        installed_memory.symlink_to(external_memory, target_is_directory=True)
        result = self.migrate()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(installed_memory.resolve(), external_memory.resolve())
        self.assertEqual((external_memory / "external.md").read_text(), "synthetic external store\n")
        local_config = json.loads((self.target / ".private/config.json").read_text())
        self.assertEqual(Path(local_config["memory_root"]).resolve(), external_memory.resolve())
        self.assertEqual((self.target / "memory/durable.md").read_text(), "synthetic memory\n")

    def test_recovery_resumes_after_each_directory_switch_interruption(self) -> None:
        for point in ("after_old_move", "after_new_move", "after_bootstrap"):
            with self.subTest(point=point):
                # Use a fresh fixture per interruption phase.
                self.tearDown()
                self.setUp()
                interrupted = self.migrate(env_extra={"AI_TOOLKIT_MIGRATION_FAILPOINT": point})
                self.assertEqual(interrupted.returncode, 86)
                if point == "after_old_move":
                    paused = json.loads((self.home / ".claude/settings.json").read_text())
                    session = paused.get("hooks", {}).get("SessionStart", [])
                    commands = [hook.get("command", "") for entry in session
                                for hook in entry.get("hooks", [])]
                    self.assertFalse(any("git-sync-notice.sh" in command for command in commands))
                    self.assertEqual((self.base / ".checkout.migration/installed-settings.original").read_bytes(),
                                     self.original_settings)
                    self.assertTrue((self.base / ".checkout.migration/sync.paused").is_file())
                resumed = self.migrate()
                self.assertEqual(resumed.returncode, 0, resumed.stderr)
                self.assertEqual(cmd(["git", "-C", str(self.target), "rev-parse", "HEAD"]).stdout.strip(), self.revision)
                self.assertEqual((self.target / "memory/durable.md").read_text(), "synthetic memory\n")

    def test_new_sync_hook_honors_external_migration_pause_marker(self) -> None:
        root = self.base / "sync-fixture"
        (root / "hooks").mkdir(parents=True)
        shutil.copyfile(ROOT / "hooks" / "git-sync-notice.sh", root / "hooks" / "git-sync-notice.sh")
        marker = self.base / ".sync-fixture.migration" / "sync.paused"
        marker.parent.mkdir()
        marker.write_text("pause\n", encoding="utf-8")
        state = self.base / "sync-state"
        result = subprocess.run(["bash", str(root / "hooks" / "git-sync-notice.sh")],
                                input="{}", text=True, capture_output=True,
                                env={**os.environ, "HOME": str(self.home),
                                     "GIT_SYNC_NOTICE_STATE_DIR": str(state)})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertFalse(state.exists(), "paused hook must not start background fetch work")

    def test_active_automatic_updater_is_detected(self) -> None:
        module = runpy.run_path(str(MIGRATOR))
        process_list = subprocess.CompletedProcess(
            ["ps"], 0, stdout=" 4242 /bin/bash /synthetic/hooks/git-sync-notice.sh\n", stderr="")
        with mock.patch("subprocess.run", return_value=process_list):
            self.assertEqual(module["active_updaters"](self.target), ["sync hook process"])

    def test_sanitizer_removes_synthetic_legacy_style_heading(self) -> None:
        module = runpy.run_path(str(MIGRATOR))
        text = "# Configuration\n\n## " + legacy_style_heading() + "\n\nOld style text.\n\n## Operations\nKeep data.\n"
        sanitized = module["sanitize_private_rules"](text)
        self.assertNotIn(legacy_style_heading(), sanitized)
        self.assertIn("## Operations", sanitized)

    def test_external_private_mapping_cannot_replace_a_tracked_public_file(self) -> None:
        mapping = self.target / ".private" / "bad-map.json"
        mapping.write_text(json.dumps({"mappings": [
            {"source": "bin/private-tool", "destination": "tracked.txt", "kind": "file"},
        ]}), encoding="utf-8")
        result = self.migrate(extra=["--private-map", str(mapping)])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("tracked public path", result.stderr)
        self.assertEqual((self.target / "tracked.txt").read_text(), "local modified content\n")

    def test_repository_credentials_are_rejected_without_echoing_them(self) -> None:
        result = subprocess.run([
            sys.executable, str(MIGRATOR), "--target", str(self.outer),
            "--repository", "https://synthetic-user:synthetic-token@example.invalid/toolkit.git",
            "--revision", self.revision,
        ], env={**os.environ, "HOME": str(self.home)}, capture_output=True, text=True, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("do not embed credentials", result.stderr)
        self.assertNotIn("synthetic-token", result.stderr)
        self.assertFalse((self.base / ".checkout.migration").exists())

    def test_resumption_refuses_a_changed_private_mapping(self) -> None:
        interrupted = self.migrate(env_extra={"AI_TOOLKIT_MIGRATION_FAILPOINT": "after_clone_verified"})
        self.assertEqual(interrupted.returncode, 86)
        mapping = self.target / ".private/migration-map.json"
        data = json.loads(mapping.read_text())
        data["mappings"].reverse()
        mapping.write_text(json.dumps(data), encoding="utf-8")
        resumed = self.migrate()
        self.assertNotEqual(resumed.returncode, 0)
        self.assertIn("private migration map changed", resumed.stderr)
        self.assertEqual((self.target / "tracked.txt").read_text(), "local modified content\n")
        self.assertFalse((self.base / ".checkout.migration/sync.paused").exists())

    def test_launcher_is_pinned_and_checks_hash_before_execution(self) -> None:
        revision = "a" * 40
        digest = "0" * 64
        result = subprocess.run([
            sys.executable, str(MIGRATOR), "--target", "$HOME/path/to/checkout",
            "--repository", "https://github.com/example/toolkit.git", "--revision", revision,
            "--migrator-sha256", digest, "--print-launcher",
        ], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("raw.githubusercontent.com/example/toolkit/" + revision + "/bin/migrate-public-release", result.stdout)
        self.assertIn(digest, result.stdout)
        self.assertIn("$HOME/path/to/checkout", result.stdout)
        self.assertLess(result.stdout.index("actual.lower() != expected.lower()"),
                        result.stdout.index("subprocess.run([sys.executable, path"))
        self.assertNotIn("curl", result.stdout.lower())
        command = shlex.split(result.stdout.split("\n", 1)[1].strip())
        code = command[2]
        payload = b"synthetic migrator source"
        sys_args = ["-c", command[3], command[4], command[5], command[6], command[7]]
        response = io.BytesIO(payload)
        with mock.patch.object(sys, "argv", sys_args), \
             mock.patch("urllib.request.urlopen", return_value=response), \
             mock.patch("subprocess.run") as invoke:
            with self.assertRaises(SystemExit):
                exec(compile(code, "pinned-launcher", "exec"), {"__name__": "__main__"})
        invoke.assert_not_called()
        digest = hashlib.sha256(payload).hexdigest()
        sys_args[3] = digest
        response = io.BytesIO(payload)
        with mock.patch.object(sys, "argv", sys_args), \
             mock.patch("urllib.request.urlopen", return_value=response), \
             mock.patch("subprocess.run", return_value=subprocess.CompletedProcess([], 0)) as invoke:
            with self.assertRaises(SystemExit) as exit_code:
                exec(compile(code, "pinned-launcher", "exec"), {"__name__": "__main__"})
        self.assertEqual(exit_code.exception.code, 0)
        invoke.assert_called_once()


if __name__ == "__main__":
    unittest.main()
